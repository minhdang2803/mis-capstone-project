import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.settings import settings
from app.models.state import AgentState
from app.services.geocoding_service import HCMC_STREET_GAZETTEER, geocode_street


# class schemas về thông tin của các địa điểm ngập lụt được Gemini tổng hợp từ internet
class FloodHazardEntity(BaseModel):
    street: str = Field(
        description="Tên tuyến đường bị ngập lụt tại TP.HCM (ví dụ: 'Trần Xuân Soạn', 'Quốc Hương')"
    )
    ward: Optional[str] = Field(
        default=None,
        description="Phường hoặc Xã nơi xảy ra ngập (ví dụ: 'Thảo Điền', 'Linh Đông', 'Hiệp Bình Chánh')",
    )
    district: Optional[str] = Field(
        default=None,
        description="Quận, Huyện hoặc Thành phố trực thuộc (ví dụ: 'Quận 7', 'Gò Vấp', 'TP Thủ Đức', 'Nhà Bè')",
    )
    location_description: Optional[str] = Field(
        default=None,
        description="Đoạn đường hoặc giao lộ cụ thể bị ngập (ví dụ: 'ngã tư Nguyễn Văn Khối - Lê Văn Thọ', 'trước chợ Thủ Đức')",
    )
    depth_cm: Optional[float] = Field(
        default=None, description="Độ sâu ngập ước tính theo cm (nếu có)"
    )
    time_window: Optional[str] = Field(
        default=None,
        description="Khung giờ hoặc thời điểm xảy ra ngập (ví dụ: '17h30', 'chiều 19/10', 'giờ tan tầm')",
    )
    severity: Optional[str] = Field(
        default="ngập",
        description="Mức độ ngập (ví dụ: 'ngập sâu', 'ngập nửa bánh xe', 'ngập nhẹ')",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Nguyên nhân gây ngập (ví dụ: 'triều cường', 'mưa lớn kéo dài')",
    )


# Class data schemas để Gemini trả về các thông tin theo yêu cầu từ propmt
# trong đó:
# - hazards là danh sách các địa điểm ngập lụt
# - FloodHazardEntity là class schema về thông tin của các địa điểm ngập lụt (được định nghĩa ở trên)
class FloodNewsExtraction(BaseModel):
    hazards: List[FloodHazardEntity] = Field(
        default_factory=list,
        description="Danh sách các điểm/tuyến đường bị ngập trích xuất được từ bản tin",
    )


def traffic_perception_agent(state: AgentState) -> AgentState:
    """
    Traffic Perception Agent (Master/Perception Agent):
    Uses Gemini LLM (gemini-2.5-flash) with structured entity extraction to parse unstructured
    Vietnamese news text, extract flood hazards (street, ward, district, depth, time), and geocode them into spatial avoid_points.
    """
    logs = state.get("logs", [])
    logs.append("[1. Perception Agent] Parsing news_context with Gemini Flash...")

    news_text = state["news_context"]
    detected_hazards: List[Dict[str, Any]] = []
    llm_succeeded = False

    # 1. Attempt LLM Structured Extraction via Gemini Flash
    if settings.GOOGLE_API_KEY:
        try:
            model = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=0.0,
                google_api_key=settings.GOOGLE_API_KEY,
                max_retries=2,
            )
            structured_extractor = model.with_structured_output(FloodNewsExtraction)
            prompt = (
                "Bạn là Tác tử Cảm nhận Giao thông (Traffic Perception Agent) trong Hệ thống Định tuyến Đa tác tử TP.HCM (Thành phố Hồ Chí Minh - Việt Nam).\n"
                "Hãy đọc bản tin/thông tin giao thông ngập lụt sau đây (từ VnExpress, Tuổi Trẻ, mạng xã hội...) và trích xuất danh sách tất cả các điểm ngập lụt với các thuộc tính cụ thể:\n"
                "- street: Tên đầy đủ của tuyến đường bị ngập (ví dụ: 'Trần Xuân Soạn', 'Quốc Hương', 'Nguyễn Văn Khối'). Không viết tắt.\n"
                "- ward: Tên phường hoặc xã nơi con đường tọa lạc nếu bài viết có nêu (ví dụ: 'Thảo Điền', 'Linh Đông', 'Hiệp Bình Chánh').\n"
                "- district: Tên quận, huyện hoặc TP trực thuộc nếu bài viết có nêu (ví dụ: 'Quận 7', 'Gò Vấp', 'TP Thủ Đức', 'Nhà Bè').\n"
                "- location_description: Đoạn đường hoặc giao lộ cụ thể bị ngập nếu có (ví dụ: 'ngã tư Lê Văn Thọ', 'đoạn chân cầu', 'trước cổng chợ').\n"
                "- depth_cm: Độ sâu ngập ước tính theo cm dưới dạng số (ví dụ: 'ngập 40cm' -> 40, 'nửa mét' -> 50; nếu không có số đo thì để null).\n"
                "- time_window: Khung giờ, buổi hoặc ngày xảy ra ngập (ví dụ: '17h30', 'chiều 19/10', 'giờ cao điểm tan tầm').\n"
                "- severity: Mức độ ngập ('ngập sâu', 'ngập nửa bánh xe', 'ngập nhẹ', 'tê liệt').\n"
                "- reason: Nguyên nhân ngập nếu có ('triều cường dâng cao', 'mưa lớn kéo dài').\n\n"
                "Hãy đảm bảo rằng những thông tin bạn đọc có nguồn gốc và có đường link có thể truy cập được.\n\n"
                "Lưu ý: Chỉ trích xuất thông tin có thực trong văn bản, không tự bịa thêm tên đường hay số đo.\n\n"
                f"--- BẢN TIN NGẬP LỤT ---\n{news_text}\n------------------------\n"
            )
            extraction_result: FloodNewsExtraction = structured_extractor.invoke(prompt)

            for item in extraction_result.hazards:
                geo_info = geocode_street(item.street, ward=item.ward, district=item.district)
                if geo_info and not any(
                    h["street"].lower() == geo_info["street"].lower()
                    for h in detected_hazards
                ):
                    geo_info["ward"] = item.ward
                    geo_info["district"] = item.district
                    geo_info["location_description"] = item.location_description
                    geo_info["depth_cm"] = item.depth_cm
                    geo_info["time_window"] = item.time_window
                    geo_info["severity"] = item.severity
                    geo_info["reason"] = item.reason
                    detected_hazards.append(geo_info)
                    logs.append(
                        f"  -> [Gemini NLP] Extracted Hazard: '{geo_info['street']}' "
                        f"(Phường: {item.ward or '-'}, Quận: {item.district or '-'}) at "
                        f"({geo_info['lat']}, {geo_info['lon']}), radius={geo_info['radius_m']}m "
                        f"(depth={item.depth_cm}cm, time={item.time_window}, severity={item.severity}, reason={item.reason or '-'})"
                    )
            llm_succeeded = True
        except Exception as e:
            logs.append(
                f"  [!] Gemini LLM extraction error: {e}. Falling back to HCMC gazetteer matching..."
            )

    # 2. Gazetteer / Rule-based Fallback if LLM failed or is not available
    if not llm_succeeded and not detected_hazards:
        news_lower = news_text.lower()
        for street_key in HCMC_STREET_GAZETTEER.keys():
            if street_key in news_lower:
                geo_info = geocode_street(street_key)
                if geo_info and not any(
                    h["street"].lower() == geo_info["street"].lower()
                    for h in detected_hazards
                ):
                    detected_hazards.append(geo_info)
                    logs.append(
                        f"  -> [Gazetteer Fallback] Extracted Hazard: '{geo_info['street']}' at ({geo_info['lat']}, {geo_info['lon']})"
                    )

    state["perceived_hazards"] = detected_hazards
    state["avoid_points"] = detected_hazards

    # 3. Compute Extraction Accuracy
    if detected_hazards:
        state["extraction_accuracy"] = 1.0
        logs.append(
            f"  [✓] Perception Complete: {len(detected_hazards)} hazard zones mapped to avoid_points."
        )
    else:
        state["extraction_accuracy"] = 0.0
        logs.append("  [!] Warning: No specific street hazard extracted from context.")

    return state
