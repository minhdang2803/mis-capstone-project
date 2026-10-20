import json
import os
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter()

def load_scenarios_db() -> List[Dict[str, Any]]:
    path = os.path.join(os.path.dirname(__file__), "../../../../data/scenarios.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@router.get("/", response_model=List[Dict[str, Any]])
def get_scenarios():
    """Retrieve all benchmark scenarios in HCMC."""
    return load_scenarios_db()

@router.get("/{scenario_id}", response_model=Dict[str, Any])
def get_scenario(scenario_id: int):
    """Retrieve a specific scenario by ID."""
    scenarios = load_scenarios_db()
    for sc in scenarios:
        if sc.get("id") == scenario_id:
            return sc
    raise HTTPException(status_code=404, detail="Scenario not found")
