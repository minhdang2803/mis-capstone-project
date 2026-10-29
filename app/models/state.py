from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    scenario_id: Optional[int]
    user_query: str
    news_context: str
    origin: List[float]       # [lat, lon]
    destination: List[float]  # [lat, lon]
    perceived_hazards: List[Dict[str, Any]]
    avoid_points: List[Dict[str, Any]]
    current_route: Optional[Dict[str, Any]]
    reflection_count: int     # reflection attempts actually performed (never exceeds max_reflections)
    max_reflections: int
    is_safe: bool
    violations: List[str]
    waypoints: List[List[float]]
    logs: List[str]
    should_retry: bool        # set by the Reflector; routes the graph back to the Reasoning Agent
    detours: Dict[str, Dict[str, Any]]    # per-hazard detour waypoint + number of tries
    history: List[Dict[str, Any]]         # one entry per routed iteration
    best_attempt: Optional[Dict[str, Any]]
    perception_source: str    # "gemini" | "gazetteer_fallback" | "none"
    strict_perception: bool   # raise instead of silently falling back to the gazetteer
