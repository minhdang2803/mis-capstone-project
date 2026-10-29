import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.agents.perception import PerceptionError
from app.api.v1.endpoints.scenarios import load_scenarios_db
from app.models.schemas import HazardZone, RouteRequest, RouteResponse
from app.services.osrm_service import OSRMError
from app.services.workflow_service import run_langgraph_workflow

router = APIRouter()


def _run(scenario_id: Optional[int], **kwargs) -> RouteResponse:
    """Runs the workflow and maps it to the API schema; upstream outages become 503, not a crash."""
    start_time = time.time()
    try:
        res = run_langgraph_workflow(scenario_id=scenario_id, **kwargs)
    except OSRMError as e:
        raise HTTPException(status_code=503, detail=f"Routing engine unavailable: {e}")
    except PerceptionError as e:
        raise HTTPException(status_code=503, detail=f"Perception unavailable: {e}")

    hazards = [
        HazardZone(street=h["street"], lat=h["lat"], lon=h["lon"], radius_m=h["radius_m"])
        for h in res["perceived_hazards"]
    ]
    route_info: Dict[str, Any] = res["current_route"] or {"distance_m": 0, "duration_s": 0, "coordinates": []}
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
        perception_source=res["perception_source"],
        execution_time_ms=round((time.time() - start_time) * 1000.0, 2),
    )


@router.post("/", response_model=RouteResponse)
def compute_route(req: RouteRequest):
    """Computes flood-aware route using Multi-Agent LangGraph Workflow."""
    return _run(
        None,
        user_query=req.user_query,
        news_context=req.news_context,
        origin=[req.origin.lat, req.origin.lon],
        destination=[req.destination.lat, req.destination.lon],
        max_reflections=req.max_reflections or 2,
    )


@router.post("/scenario/{scenario_id}", response_model=RouteResponse)
def compute_scenario_route(scenario_id: int):
    """Executes multi-agent routing directly for a given benchmark scenario ID."""
    sc = next((s for s in load_scenarios_db() if s.get("id") == scenario_id), None)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario #{scenario_id} not found")
    return _run(
        sc["id"],
        user_query=sc["user_query"],
        news_context=sc["news_context"],
        origin=[sc["origin"]["lat"], sc["origin"]["lon"]],
        destination=[sc["destination"]["lat"], sc["destination"]["lon"]],
        max_reflections=2,
    )
