import time
from typing import List, Optional

# pyrefly: ignore[missing-import]
from langgraph.graph import END, StateGraph

from app.agents.perception import traffic_perception_agent
from app.agents.reasoning import route_reasoning_agent
from app.agents.reflector import reflector_agent
from app.models.state import AgentState


def _after_reflector(state: AgentState) -> str:
    return "reasoning" if state["should_retry"] else END


def build_workflow():
    """Perception -> Reasoning -> Reflector, looping back to Reasoning while the Reflector asks for a retry."""
    graph = StateGraph(AgentState)
    graph.add_node("perception", traffic_perception_agent)
    graph.add_node("reasoning", route_reasoning_agent)
    graph.add_node("reflector", reflector_agent)
    graph.set_entry_point("perception")
    graph.add_edge("perception", "reasoning")
    graph.add_edge("reasoning", "reflector")
    graph.add_conditional_edges("reflector", _after_reflector, {"reasoning": "reasoning", END: END})
    return graph.compile()


_WORKFLOW = build_workflow()


def run_langgraph_workflow(
    user_query: str,
    news_context: str,
    origin: List[float],
    destination: List[float],
    scenario_id: Optional[int] = None,
    max_reflections: int = 2,
    enable_reflection: bool = True,
    strict_perception: bool = False,
) -> AgentState:
    """
    Executes the Multi-Agent LangGraph StateGraph workflow.
    With enable_reflection=False the Reflector still verifies the route but never triggers a retry.
    With strict_perception=True a Gemini failure raises instead of silently using the gazetteer.
    """
    start_time = time.time()

    state: AgentState = {
        "scenario_id": scenario_id,
        "user_query": user_query,
        "news_context": news_context,
        "origin": origin,
        "destination": destination,
        "perceived_hazards": [],
        "avoid_points": [],
        "current_route": None,
        "reflection_count": 0,
        "max_reflections": max_reflections if enable_reflection else 0,
        "is_safe": False,
        "violations": [],
        "waypoints": [],
        "logs": [],
        "should_retry": False,
        "detours": {},
        "history": [],
        "best_attempt": None,
        "perception_source": "none",
        "strict_perception": strict_perception,
    }

    state = _WORKFLOW.invoke(state)

    elapsed_ms = (time.time() - start_time) * 1000.0
    state["logs"].append(
        f"\n[Execution Summary] Total Latency: {elapsed_ms:.2f} ms | Safe: {state['is_safe']} | "
        f"Reflection Loops: {state['reflection_count']} | Perception: {state['perception_source']}"
    )
    return state
