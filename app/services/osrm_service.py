import math
from typing import Dict, List, Any
from app.core.geometry import haversine_distance

def calculate_route_osrm(origin: List[float], destination: List[float], waypoints: List[List[float]] = None) -> Dict[str, Any]:
    """
    Computes route polyline along origin -> waypoints -> destination.
    Simulates OSRM routing engine response with interpolated step coordinates.
    """
    pts = [origin] + (waypoints if waypoints else []) + [destination]
    coords = []
    
    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i+1]
        steps = 15
        for s in range(steps):
            ratio = s / steps
            lat = p1[0] + (p2[0] - p1[0]) * ratio
            lon = p1[1] + (p2[1] - p1[1]) * ratio
            coords.append([round(lat, 5), round(lon, 5)])
    coords.append([round(pts[-1][0], 5), round(pts[-1][1], 5)])
    
    total_dist = 0.0
    for k in range(len(coords) - 1):
        total_dist += haversine_distance(coords[k][0], coords[k][1], coords[k+1][0], coords[k+1][1])
        
    return {
        "distance_m": round(total_dist, 2),
        "duration_s": round(total_dist / 8.33, 1), # ~30km/h average speed
        "coordinates": coords,
        "engine": "OSRM_v5.24"
    }
