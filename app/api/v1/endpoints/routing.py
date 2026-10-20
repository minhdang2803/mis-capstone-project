import time
from fastapi import APIRouter, HTTPException
from app.models.schemas import RouteRequest, RouteResponse, HazardZone
from app.services.workflow_service import run_langgraph_workflow
from app.api.v1.endpoints.scenarios import load_scenarios_db

router = APIRouter()

@router.post("/", response_model=RouteResponse)
def compute_route(req: RouteRequest):
    """Computes flood-aware route using Multi-Agent LangGraph Workflow."""
    start_time = time.time()
    
    res = run_langgraph_workflow(
        user_query=req.user_query,
        news_context=req.news_context,
        origin=[req.origin.lat, req.origin.lon],
        destination=[req.destination.lat, req.destination.lon],
        max_reflections=req.max_reflections or 2
    )
    
    elapsed_ms = (time.time() - start_time) * 1000.0
    
    hazards = [
        HazardZone(
            street=h["street"],
            lat=h["lat"],
            lon=h["lon"],
            radius_m=h["radius_m"]
        ) for h in res["perceived_hazards"]
    ]
    
    route_info = res["current_route"] or {"distance_m": 0, "duration_s": 0, "coordinates": []}
    
    return RouteResponse(
        scenario_id=res["scenario_id"],
        is_safe=res["is_safe"],
        reflection_count=res["reflection_count"],
        total_distance_km=round(route_info["distance_m"] / 1000.0, 2),
        total_duration_min=round(route_info["duration_s"] / 60.0, 1),
        perceived_hazards=hazards,
        violations=res["violations"],
        coordinates=route_info["coordinates"],
        logs=res["logs"],
        execution_time_ms=round(elapsed_ms, 2)
    )

@router.post("/scenario/{scenario_id}", response_model=RouteResponse)
def compute_scenario_route(scenario_id: int):
    """Executes multi-agent routing directly for a given benchmark scenario ID."""
    scenarios = load_scenarios_db()
    sc = next((s for s in scenarios if s.get("id") == scenario_id), None)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario #{scenario_id} not found")
        
    start_time = time.time()
    res = run_langgraph_workflow(
        user_query=sc["user_query"],
        news_context=sc["news_context"],
        origin=[sc["origin"]["lat"], sc["origin"]["lon"]],
        destination=[sc["destination"]["lat"], sc["destination"]["lon"]],
        scenario_id=sc["id"],
        max_reflections=2
    )
    
    elapsed_ms = (time.time() - start_time) * 1000.0
    
    hazards = [
        HazardZone(
            street=h["street"],
            lat=h["lat"],
            lon=h["lon"],
            radius_m=h["radius_m"]
        ) for h in res["perceived_hazards"]
    ]
    
    route_info = res["current_route"] or {"distance_m": 0, "duration_s": 0, "coordinates": []}
    
    return RouteResponse(
        scenario_id=sc["id"],
        is_safe=res["is_safe"],
        reflection_count=res["reflection_count"],
        total_distance_km=round(route_info["distance_m"] / 1000.0, 2),
        total_duration_min=round(route_info["duration_s"] / 60.0, 1),
        perceived_hazards=hazards,
        violations=res["violations"],
        coordinates=route_info["coordinates"],
        logs=res["logs"],
        execution_time_ms=round(elapsed_ms, 2)
    )
