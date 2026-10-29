from typing import Any, Dict, List

from app.agents.perception import traffic_perception_agent
from app.agents.reflector import find_violations
from app.services.osrm_service import calculate_route_osrm, calculate_routes_osrm


def osrm_baseline(origin: List[float], destination: List[float]) -> Dict[str, Any]:
    """Baseline 1: plain OSRM shortest route, no knowledge of flooding."""
    return {"current_route": calculate_route_osrm(origin, destination), "perceived_hazards": []}


def osrm_alternatives_ablation(
    news_context: str, origin: List[float], destination: List[float], strict_perception: bool = False
) -> Dict[str, Any]:
    """
    Ablation B1+: Perception (so hazards are known) + OSRM's own alternative routes. The shortest
    alternative that avoids every perceived hazard wins; if none does, the least-violating one.
    There is no Reflector reasoning and no detour waypoints, which isolates what the reflection
    loop adds on top of OSRM's built-in alternatives.
    """
    state = {
        "news_context": news_context, "logs": [], "strict_perception": strict_perception,
        "perceived_hazards": [], "avoid_points": [], "perception_source": "none",
    }
    state = traffic_perception_agent(state)
    routes = calculate_routes_osrm(origin, destination, alternatives=True)

    def score(route):
        v = find_violations(route["coordinates"], state["avoid_points"])
        return (len(v), sum(x["hazard"]["radius_m"] - x["distance_m"] for x in v), route["distance_m"])

    best = min(routes, key=score)
    return {
        "current_route": best,
        "perceived_hazards": state["perceived_hazards"],
        "perception_source": state["perception_source"],
        "alternatives_considered": len(routes),
        "logs": state["logs"],
    }
