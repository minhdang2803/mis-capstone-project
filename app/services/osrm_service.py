import hashlib
import json
import os
from typing import Any, Dict, List, Optional

import requests

from app.core.settings import settings


class OSRMError(RuntimeError):
    """Raised when the OSRM server is unreachable or returns no usable route."""


_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            max_retries=requests.adapters.Retry(
                total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504)
            )
        )
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
    return _session


def _coord_path(points: List[List[float]]) -> str:
    # OSRM expects lon,lat order
    return ";".join(f"{p[1]:.6f},{p[0]:.6f}" for p in points)


def _cache_file(url: str, params: Dict[str, Any]) -> str:
    key = hashlib.sha256(
        (settings.OSRM_SERVER_URL + url + json.dumps(params, sort_keys=True)).encode()
    ).hexdigest()
    return os.path.join(settings.ROUTE_CACHE_DIR, f"{key}.json")


def _get_json(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """GET against the OSRM server with retries and an optional on-disk cache."""
    cache_path = _cache_file(path, params) if settings.OSRM_CACHE_ENABLED else None
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    url = f"{settings.OSRM_SERVER_URL.rstrip('/')}{path}"
    try:
        resp = _get_session().get(url, params=params, timeout=settings.OSRM_TIMEOUT_S)
    except requests.RequestException as e:
        raise OSRMError(f"OSRM request failed ({settings.OSRM_SERVER_URL}): {e}") from e

    try:
        data = resp.json()
    except ValueError:
        raise OSRMError(f"OSRM returned non-JSON (HTTP {resp.status_code}) from {url}")
    if resp.status_code != 200 or data.get("code") != "Ok":
        raise OSRMError(f"OSRM error (HTTP {resp.status_code}): {data.get('code')} {data.get('message', '')}")

    if cache_path:
        os.makedirs(settings.ROUTE_CACHE_DIR, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    return data


def _to_route(osrm_route: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "distance_m": round(osrm_route["distance"], 2),
        "duration_s": round(osrm_route["duration"], 1),
        # GeoJSON is [lon, lat]; the rest of the code base uses [lat, lon]
        "coordinates": [[round(lat, 5), round(lon, 5)] for lon, lat in osrm_route["geometry"]["coordinates"]],
        "engine": "OSRM",
    }


def calculate_routes_osrm(
    origin: List[float],
    destination: List[float],
    waypoints: Optional[List[List[float]]] = None,
    alternatives: bool = False,
) -> List[Dict[str, Any]]:
    """
    Routes origin -> waypoints -> destination through the real OSRM server.
    Returns the primary route first, followed by any alternatives OSRM found.
    """
    pts = [origin] + (waypoints or []) + [destination]
    data = _get_json(
        f"/route/v1/driving/{_coord_path(pts)}",
        {
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
            # OSRM only supports alternatives for two-point requests
            "alternatives": "true" if alternatives and len(pts) == 2 else "false",
        },
    )
    routes = data.get("routes") or []
    if not routes:
        raise OSRMError("OSRM returned no route")
    return [_to_route(r) for r in routes]


def calculate_route_osrm(
    origin: List[float], destination: List[float], waypoints: Optional[List[List[float]]] = None
) -> Dict[str, Any]:
    """Primary route along origin -> waypoints -> destination via the real OSRM server."""
    return calculate_routes_osrm(origin, destination, waypoints)[0]


def snap_to_road(point: List[float]) -> Dict[str, Any]:
    """Snaps [lat, lon] to the nearest road via OSRM /nearest. Returns the point and snap distance."""
    data = _get_json(f"/nearest/v1/driving/{_coord_path([point])}", {"number": 1})
    wp = data["waypoints"][0]
    lon, lat = wp["location"]
    return {"point": [round(lat, 5), round(lon, 5)], "snap_distance_m": round(wp["distance"], 1)}
