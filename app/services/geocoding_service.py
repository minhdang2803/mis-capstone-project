import functools
import json
import logging
import os
import re
import time
from typing import Dict, Any, List, Optional
import requests
from app.core.geometry import haversine_distance
from app.core.settings import settings
from app.services.evaluation import normalize_name

logger = logging.getLogger(__name__)

# HCMC and surroundings (min_lat, min_lon, max_lat, max_lon): anything outside is rejected
HCMC_BBOX = (10.35, 106.35, 11.20, 107.05)
# Two independent geocoders must land within this distance to count as agreeing
GEOCODE_AGREE_M = 2000.0
NOMINATIM_MIN_INTERVAL_S = 1.1  # public Nominatim policy: at most ~1 request per second
_last_nominatim_call = {"t": 0.0}

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

def name_in_text(name: str, text: str) -> bool:
    """Whole-word containment (case-insensitive), so 'bình' does not match 'bình thạnh' or 'bình chiểu'."""
    return re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", text.lower()) is not None


def _lookup_gazetteer(clean_name: str) -> Optional[Dict[str, Any]]:
    """Exact key first, then whole-word containment, preferring the longest (most specific) key."""
    if clean_name in HCMC_STREET_GAZETTEER:
        return {"key": clean_name, **HCMC_STREET_GAZETTEER[clean_name]}
    candidates = [
        k for k in HCMC_STREET_GAZETTEER if name_in_text(k, clean_name) or name_in_text(clean_name, k)
    ]
    if not candidates:
        return None
    key = max(candidates, key=len)
    return {"key": key, **HCMC_STREET_GAZETTEER[key]}


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

    entry = _lookup_gazetteer(clean_name)
    if entry:
        return {
            "street": entry["key"].title(),
            "lat": entry["lat"],
            "lon": entry["lon"],
            "radius_m": entry.get("radius_m", settings.DEFAULT_HAZARD_RADIUS_M),
            "geocode_source": "gazetteer",
        }

    result = _remote_geocode(street_name, ward, district)
    if result is None:
        logger.warning("geocode: no trustworthy coordinates for '%s'", street_name)
        return None
    return {**result, "radius_m": settings.DEFAULT_HAZARD_RADIUS_M}


def _in_hcmc(lat: float, lon: float) -> bool:
    return HCMC_BBOX[0] <= lat <= HCMC_BBOX[2] and HCMC_BBOX[1] <= lon <= HCMC_BBOX[3]


def _street_name_matches(query: str, found: Optional[str]) -> bool:
    """The returned feature must carry the queried street name, not just resemble it."""
    if not found:
        return False
    q, f = normalize_name(query), normalize_name(found)
    return q == f or re.search(rf"(?<!\w){re.escape(q)}(?!\w)", f) is not None


def _nominatim_candidates(street_name: str, ward: Optional[str], district: Optional[str]) -> List[Dict[str, float]]:
    parts = [f"Đường {street_name}"]
    if ward:
        parts.append(f"Phường {ward}" if not ward.lower().startswith("phường") else ward)
    if district:
        parts.append(district)
    parts.append("Thành phố Hồ Chí Minh, Việt Nam")

    gap = NOMINATIM_MIN_INTERVAL_S - (time.monotonic() - _last_nominatim_call["t"])
    if gap > 0:
        time.sleep(gap)
    _last_nominatim_call["t"] = time.monotonic()
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": ", ".join(parts), "format": "jsonv2", "limit": 5, "countrycodes": "vn",
                "viewbox": f"{HCMC_BBOX[1]},{HCMC_BBOX[2]},{HCMC_BBOX[3]},{HCMC_BBOX[0]}", "bounded": 1,
            },
            headers={"User-Agent": "MAS4POI-Capstone/2.0"},
            timeout=6.0,
        )
        items = resp.json() if resp.status_code == 200 else []
    except Exception:
        return []
    out = []
    for it in items:
        lat, lon = float(it["lat"]), float(it["lon"])
        # must be a road whose own name matches, and lie inside HCMC
        if it.get("category") == "highway" and _street_name_matches(street_name, it.get("name")) and _in_hcmc(lat, lon):
            out.append({"lat": lat, "lon": lon, "hint": ", ".join(str(it.get("display_name", "")).split(", ")[:4])})
    return out


def _photon_candidates(street_name: str, ward: Optional[str], district: Optional[str]) -> List[Dict[str, float]]:
    try:
        resp = requests.get(
            "https://photon.komoot.io/api/",
            params={
                "q": f"{street_name} {ward or ''} {district or ''} Ho Chi Minh".strip(), "limit": 5,
                "bbox": f"{HCMC_BBOX[1]},{HCMC_BBOX[0]},{HCMC_BBOX[3]},{HCMC_BBOX[2]}", "osm_tag": "highway",
            },
            headers={"User-Agent": "MAS4POI-Capstone/2.0"},
            timeout=6.0,
        )
        features = resp.json().get("features", []) if resp.status_code == 200 else []
    except Exception:
        return []
    out = []
    for f in features:
        props = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"]
        if props.get("osm_key") == "highway" and _street_name_matches(street_name, props.get("name")) and _in_hcmc(lat, lon):
            hint = ", ".join(str(props[k]) for k in ("district", "locality", "city", "state") if props.get(k))
            out.append({"lat": lat, "lon": lon, "hint": hint})
    return out


@functools.lru_cache(maxsize=1024)
def _remote_geocode(street_name: str, ward: Optional[str], district: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Geocodes through Nominatim and Photon and only trusts a result that is a road with the queried
    name inside HCMC. When both services answer they must agree (within GEOCODE_AGREE_M); a
    disagreement or no valid answer yields None rather than a guessed coordinate.
    """
    nom = _nominatim_candidates(street_name, ward, district)
    pho = _photon_candidates(street_name, ward, district)

    best = None
    for n in nom:
        for p in pho:
            d = haversine_distance(n["lat"], n["lon"], p["lat"], p["lon"])
            if d <= GEOCODE_AGREE_M and (best is None or d < best[0]):
                best = (d, n, p)
    if best:
        _, n, _ = best
        return {"street": street_name.title(), "lat": round(n["lat"], 5), "lon": round(n["lon"], 5),
                "geocode_source": "nominatim+photon", "geocode_confidence": "agreed", "address_hint": n.get("hint", "")}
    if nom and pho:
        logger.warning("geocode: Nominatim and Photon disagree for '%s'; refusing to guess", street_name)
        return None
    src, cand = ("nominatim", nom[0]) if nom else (("photon", pho[0]) if pho else (None, None))
    if cand is None:
        return None
    return {"street": street_name.title(), "lat": round(cand["lat"], 5), "lon": round(cand["lon"], 5),
            "geocode_source": src, "geocode_confidence": "single_source", "address_hint": cand.get("hint", "")}
