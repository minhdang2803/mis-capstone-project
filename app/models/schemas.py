from pydantic import BaseModel
from typing import List, Optional

class LocationPoint(BaseModel):
    name: Optional[str] = None
    lat: float
    lon: float

class HazardZone(BaseModel):
    street: str
    lat: float
    lon: float
    radius_m: float = 350.0
    risk_level: Optional[str] = "HIGH"

class RouteRequest(BaseModel):
    user_query: str
    news_context: str
    origin: LocationPoint
    destination: LocationPoint
    max_reflections: Optional[int] = 2

class RouteResponse(BaseModel):
    scenario_id: Optional[int] = None
    is_safe: bool
    reflection_count: int
    total_distance_km: float
    total_duration_min: float
    perceived_hazards: List[HazardZone]
    violations: List[str]
    coordinates: List[List[float]]
    logs: List[str]
    execution_time_ms: float
