import math
from typing import Any, Dict, List, Tuple

EARTH_RADIUS_M = 6371000.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great circle distance in meters between two lat/lon points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def to_local_xy(lat: float, lon: float, ref_lat: float, ref_lon: float) -> Tuple[float, float]:
    """Equirectangular projection to metres (x = east, y = north) around a reference point.
    The error is negligible at city scale."""
    x = math.radians(lon - ref_lon) * EARTH_RADIUS_M * math.cos(math.radians(ref_lat))
    y = math.radians(lat - ref_lat) * EARTH_RADIUS_M
    return x, y


def from_local_xy(x: float, y: float, ref_lat: float, ref_lon: float) -> Tuple[float, float]:
    """Inverse of `to_local_xy`; returns (lat, lon)."""
    lat = ref_lat + math.degrees(y / EARTH_RADIUS_M)
    lon = ref_lon + math.degrees(x / (EARTH_RADIUS_M * math.cos(math.radians(ref_lat))))
    return lat, lon


def point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> Tuple[float, float, float, float]:
    """Distance from point P to segment AB in a planar frame.
    Returns (distance, closest_x, closest_y, t) with t in [0, 1] along AB."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    t = 0.0 if seg_len_sq == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), cx, cy, t


def distance_to_polyline(coords: List[List[float]], lat: float, lon: float) -> Dict[str, Any]:
    """
    Minimum distance (m) from a point to a polyline, measured to the *segments* between
    vertices rather than to the vertices only. A route can cross a hazard zone between two
    far-apart vertices while every vertex stays outside it.

    Returns {distance_m, segment_index, closest_point [lat, lon], t}; segment_index i refers
    to the segment coords[i] -> coords[i+1].
    """
    if not coords:
        return {"distance_m": float("inf"), "segment_index": -1, "closest_point": None, "t": 0.0}
    if len(coords) == 1:
        return {
            "distance_m": haversine_distance(coords[0][0], coords[0][1], lat, lon),
            "segment_index": 0,
            "closest_point": list(coords[0]),
            "t": 0.0,
        }

    best = {"distance_m": float("inf"), "segment_index": 0, "closest_point": None, "t": 0.0}
    for i in range(len(coords) - 1):
        ax, ay = to_local_xy(coords[i][0], coords[i][1], lat, lon)
        bx, by = to_local_xy(coords[i + 1][0], coords[i + 1][1], lat, lon)
        dist, cx, cy, t = point_segment_distance(0.0, 0.0, ax, ay, bx, by)
        if dist < best["distance_m"]:
            c_lat, c_lon = from_local_xy(cx, cy, lat, lon)
            best = {"distance_m": dist, "segment_index": i, "closest_point": [c_lat, c_lon], "t": t}
    return best


def calculate_min_distance_to_hazard(coords: List[List[float]], hazard_lat: float, hazard_lon: float) -> float:
    """Calculates minimum distance in meters from route polyline to a hazard point."""
    return distance_to_polyline(coords, hazard_lat, hazard_lon)["distance_m"]
