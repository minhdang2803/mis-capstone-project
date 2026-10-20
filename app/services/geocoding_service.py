import os
import json
import re
from typing import Dict, Any, Optional
import requests
from app.core.settings import settings

# TODO: Tập dữ liệu benchmark cần được thay thế thành một cronjob trong tương lai để lấy dữ liệu near realtime.
# Đường dẫn tới tệp dữ liệu điểm đen ngập lụt chuẩn hóa tại TP.HCM
BLACKSPOTS_DATASET_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../data/hcmc_flood_blackspots.json")
    if "app" not in os.path.dirname(__file__)
    else os.path.join(os.path.dirname(__file__), "../../data/hcmc_flood_blackspots.json")
)

def _load_gazetteer() -> Dict[str, Dict[str, Any]]:
    """
    Tự động đọc danh mục điểm đen ngập lụt từ tệp chuẩn hóa `data/hcmc_flood_blackspots.json`.
    Khởi tạo bảng băm (hash index) để phục vụ tra cứu tức thì (~0ms) cho Perception Agent.
    """
    index: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(BLACKSPOTS_DATASET_PATH):
        try:
            with open(BLACKSPOTS_DATASET_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("blackspots", []):
                    key = item["street"].lower().strip()
                    # Loại bỏ tiền tố đường nếu có
                    for prefix in ["đường ", "phố ", "tuyến "]:
                        if key.startswith(prefix):
                            key = key[len(prefix):].strip()
                    index[key] = {
                        "street": item["street"],
                        "lat": item["lat"],
                        "lon": item["lon"],
                        "radius_m": item.get("radius_m", settings.DEFAULT_HAZARD_RADIUS_M),
                        "district": item.get("district"),
                        "ward": item.get("ward"),
                        "landmark": item.get("landmark"),
                        "cause": item.get("cause")
                    }
        except Exception as e:
            print(f"[!] Warning: Lỗi nạp tệp {BLACKSPOTS_DATASET_PATH}: {e}")
    return index

HCMC_STREET_GAZETTEER: Dict[str, Dict[str, Any]] = _load_gazetteer()

def geocode_street(street_name: str, ward: Optional[str] = None, district: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Look up coordinates for a given HCMC street name:
    1. First checks fast local HCMC Gazetteer cache.
    2. Falls back to OpenStreetMap Nominatim Geocoding API with ward/district context.
    3. Falls back to Photon OSM Geocoding API.
    """
    clean_name = street_name.lower().strip()
    for prefix in ["đường ", "phố ", "tuyến "]:
        if clean_name.startswith(prefix):
            clean_name = clean_name[len(prefix):].strip()

    for key, data in HCMC_STREET_GAZETTEER.items():
        if key in clean_name or clean_name in key:
            return {
                "street": key.title(),
                "lat": data["lat"],
                "lon": data["lon"],
                "radius_m": data.get("radius_m", settings.DEFAULT_HAZARD_RADIUS_M)
            }

    # Build contextual query
    addr_parts = [f"Đường {street_name}"]
    if ward:
        addr_parts.append(f"Phường {ward}" if not ward.lower().startswith("phường") else ward)
    if district:
        addr_parts.append(district)
    addr_parts.append("Thành phố Hồ Chí Minh, Việt Nam")
    query_str = ", ".join(addr_parts)

    # Fallback 1: OpenStreetMap Nominatim
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query_str,
                "format": "json",
                "limit": 1
            },
            headers={"User-Agent": "MAS4POI-Capstone/2.0"},
            timeout=4.0
        )
        if resp.status_code == 200:
            results = resp.json()
            if results and len(results) > 0:
                return {
                    "street": street_name.title(),
                    "lat": round(float(results[0]["lat"]), 5),
                    "lon": round(float(results[0]["lon"]), 5),
                    "radius_m": settings.DEFAULT_HAZARD_RADIUS_M
                }
    except Exception:
        pass

    # Fallback 2: Photon API (Komoot OSM)
    try:
        photon_q = f"{street_name} {ward or ''} {district or ''} Ho Chi Minh".strip()
        resp = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": photon_q, "limit": 1},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=4.0
        )

        if resp.status_code == 200:
            features = resp.json().get("features", [])
            if features:
                coords = features[0]["geometry"]["coordinates"]  # [lon, lat]
                return {
                    "street": street_name.title(),
                    "lat": round(float(coords[1]), 5),
                    "lon": round(float(coords[0]), 5),
                    "radius_m": settings.DEFAULT_HAZARD_RADIUS_M
                }
    except Exception:
        pass

    return None


