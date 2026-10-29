import json
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.settings import settings
from app.services.geocoding_service import geocode_street
from app.services.llm import invoke_with_retry
from app.services.osrm_service import OSRMError, calculate_route_osrm

SYSTEM_PROMPT = (
    "Bạn là trợ lý định tuyến giao thông TP.HCM. Đọc bản tin ngập lụt, tìm tọa độ các tuyến đường bị ngập "
    "bằng công cụ geocode_street, rồi dùng công cụ get_route để lấy lộ trình từ điểm đi đến điểm đến. "
    "Nếu cần né vùng ngập, truyền các điểm đi vòng (waypoints) dạng [lat, lon] vào get_route. "
    "Khi đã có lộ trình bạn hài lòng, trả lời ngắn gọn và dừng lại. Chỉ dùng tên đường có trong bản tin."
)


class PerceptionLLMError(RuntimeError):
    pass


def run_single_agent(
    user_query: str,
    news_context: str,
    origin: List[float],
    destination: List[float],
    model: Optional[Any] = None,
    max_steps: int = 6,
) -> Dict[str, Any]:
    """
    Baseline 2: one monolithic LLM that reads the news and calls geocoding and routing tools itself.
    No role separation and no verifier / reflection loop, so it never checks its own route.
    `model` is injectable for tests; by default it is Gemini with tool calling.
    """
    start = time.time()
    perceived: List[Dict[str, Any]] = []
    routes: List[Dict[str, Any]] = []
    logs: List[str] = ["[Single-Agent] Start"]

    def geocode_tool(street: str, ward: str = "", district: str = "") -> Dict[str, Any]:
        """Geocode a flooded HCMC street name to coordinates (lat, lon) and a risk radius in metres."""
        geo = geocode_street(street, ward=ward or None, district=district or None)
        if geo is None:
            return {"error": f"cannot geocode '{street}'"}
        if not any(p["street"] == geo["street"] for p in perceived):
            perceived.append(geo)
        return geo

    def route_tool(waypoints: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        """Route from the trip origin to the destination through optional [lat, lon] waypoints."""
        try:
            route = calculate_route_osrm(origin, destination, waypoints=waypoints or [])
        except OSRMError as e:
            return {"error": str(e)}
        routes.append(route)
        return {"distance_m": route["distance_m"], "duration_s": route["duration_s"], "n_vertices": len(route["coordinates"])}

    tools = [
        StructuredTool.from_function(geocode_tool, name="geocode_street"),
        StructuredTool.from_function(route_tool, name="get_route"),
    ]
    by_name = {t.name: t for t in tools}

    if model is None:
        if not settings.GOOGLE_API_KEY:
            raise PerceptionLLMError("single-agent baseline requires GOOGLE_API_KEY / GEMINI_API_KEY")
        model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL, temperature=0.0, google_api_key=settings.GOOGLE_API_KEY, max_retries=2
        )
    llm = model.bind_tools(tools)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Yêu cầu: {user_query}\nĐiểm đi: {origin}\nĐiểm đến: {destination}\n\n"
            f"--- BẢN TIN NGẬP LỤT ---\n{news_context}\n------------------------"
        )),
    ]
    tool_calls = 0
    for _ in range(max_steps):
        ai = invoke_with_retry(llm.invoke, messages)
        messages.append(ai)
        if not ai.tool_calls:
            break
        for call in ai.tool_calls:
            tool_calls += 1
            tool = by_name.get(call["name"])
            result = tool.invoke(call["args"]) if tool else {"error": f"unknown tool {call['name']}"}
            logs.append(f"  tool {call['name']}({json.dumps(call['args'], ensure_ascii=False)}) -> {str(result)[:120]}")
            messages.append(ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call["id"]))

    logs.append(f"[Single-Agent] Done: {tool_calls} tool call(s), {len(routes)} route(s)")
    return {
        # The agent's final answer is the last route it computed; none means it failed to route
        "current_route": routes[-1] if routes else None,
        "perceived_hazards": perceived,
        "tool_calls": tool_calls,
        "logs": logs,
        "latency_ms": (time.time() - start) * 1000.0,
    }
