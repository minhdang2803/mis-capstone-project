import math
from typing import List

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great circle distance in meters between two lat/lon points."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_min_distance_to_hazard(coords: List[List[float]], hazard_lat: float, hazard_lon: float) -> float:
    """Calculates minimum distance in meters from route polyline to a hazard point."""
    if not coords:
        return float("inf")
    min_dist = float("inf")
    for pt in coords:
        d = haversine_distance(pt[0], pt[1], hazard_lat, hazard_lon)
        if d < min_dist:
            min_dist = d
    return min_dist
