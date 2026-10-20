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
    reflection_count: int
    max_reflections: int
    is_safe: bool
    violations: List[str]
    waypoints: List[List[float]]
    logs: List[str]
    extraction_accuracy: float
