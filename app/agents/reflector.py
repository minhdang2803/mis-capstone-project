import math
from typing import Any, Dict, List, Optional

from app.core.geometry import (
    distance_to_polyline,
    from_local_xy,
    haversine_distance,
    to_local_xy,
)
from app.core.settings import settings
from app.models.state import AgentState
from app.services.osrm_service import snap_to_road


def find_violations(coords: List[List[float]], hazards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hazards whose zone the polyline enters, measured against route *segments*."""
    violations = []
    for hazard in hazards:
        hit = distance_to_polyline(coords, hazard["lat"], hazard["lon"])
        if hit["distance_m"] < hazard["radius_m"]:
            violations.append({"hazard": hazard, **hit})
    return violations


def _penetration_m(violations: List[Dict[str, Any]]) -> float:
    return sum(v["hazard"]["radius_m"] - v["distance_m"] for v in violations)


def _violation_message(v: Dict[str, Any]) -> str:
    return (
        f"Intersection with hazard street '{v['hazard']['street']}' "
        f"(min dist: {v['distance_m']:.1f}m < threshold {v['hazard']['radius_m']}m)"
    )


def _origin_destination_position(point: List[float], origin: List[float], destination: List[float]) -> float:
    """Projection of a point on the origin->destination line (0 at origin, 1 at destination)."""
    ox, oy = 0.0, 0.0
    dx, dy = to_local_xy(destination[0], destination[1], origin[0], origin[1])
    px, py = to_local_xy(point[0], point[1], origin[0], origin[1])
    denom = dx * dx + dy * dy
    return 0.0 if denom == 0 else ((px - ox) * dx + (py - oy) * dy) / denom


def compute_detour_waypoint(
    violation: Dict[str, Any],
    coords: List[List[float]],
    hazards: List[Dict[str, Any]],
    attempt: int,
) -> Optional[Dict[str, Any]]:
    """
    Places a waypoint perpendicular to the route, beyond the hazard zone, snapped to the road network.

    attempt 1 pushes the route further to the side it already passes on; attempt 2 tries the
    opposite side; later attempts repeat both sides with a larger margin. Returns None when no
    candidate lands on a road outside every hazard zone.
    """
    h = violation["hazard"]
    i = violation["segment_index"]
    ax, ay = to_local_xy(coords[i][0], coords[i][1], h["lat"], h["lon"])
    bx, by = to_local_xy(coords[min(i + 1, len(coords) - 1)][0], coords[min(i + 1, len(coords) - 1)][1], h["lat"], h["lon"])
    dx, dy = bx - ax, by - ay
    norm = math.hypot(dx, dy)
    if norm == 0:
        dx, dy, norm = 1.0, 0.0, 1.0
    nx, ny = -dy / norm, dx / norm  # unit normal to the route direction

    cx, cy = to_local_xy(violation["closest_point"][0], violation["closest_point"][1], h["lat"], h["lon"])
    side = 1 if (cx * nx + cy * ny) >= 0 else -1
    idx = attempt - 1
    if idx % 2 == 1:
        side = -side
    scale = 1 + idx // 2

    for stretch in (1.0, 1.5, 2.0):
        offset = h["radius_m"] + settings.DETOUR_MARGIN_M * scale * stretch
        lat, lon = from_local_xy(side * nx * offset, side * ny * offset, h["lat"], h["lon"])
        snapped = snap_to_road([lat, lon])
        point = snapped["point"]
        if snapped["snap_distance_m"] > settings.MAX_SNAP_DISTANCE_M:
            continue
        if all(haversine_distance(point[0], point[1], z["lat"], z["lon"]) >= z["radius_m"] for z in hazards):
            return {"waypoint": point, "snap_distance_m": snapped["snap_distance_m"], "side": side, "offset_m": round(offset)}
    return None


def reflector_agent(state: AgentState) -> AgentState:
    """
    Reflector Agent (Failure-Aware Verifier):
    Checks the route polyline segments against avoid_points. On violation it reasons about the
    failure (where the route enters the zone, which side to push it to) and hands detour
    waypoints back to the Reasoning Agent. If the reflection budget runs out, the least-violating
    route seen so far is returned with is_safe=False.
    """
    logs = state["logs"]
    logs.append("[3. Reflector Agent] Inspecting route polyline against hazard zones...")

    route = state["current_route"]
    coords = route["coordinates"]
    hazards = state["avoid_points"]
    violations = find_violations(coords, hazards)

    attempt = {
        "iteration": len(state["history"]),
        "route": route,
        "waypoints": list(state["waypoints"]),
        "violations": violations,
        "messages": [_violation_message(v) for v in violations],
        "score": (len(violations), _penetration_m(violations), route["distance_m"]),
    }
    state["history"].append(attempt)
    if state["best_attempt"] is None or attempt["score"] < state["best_attempt"]["score"]:
        state["best_attempt"] = attempt

    state["should_retry"] = False
    if not violations:
        state["is_safe"] = True
        state["violations"] = []
        logs.append("  [OK] SUCCESS: Route is verified safe from flood hazard zones!")
        return state

    state["is_safe"] = False
    state["violations"] = attempt["messages"]
    for msg in attempt["messages"]:
        logs.append(f"  [X] VIOLATION: {msg}")

    if state["reflection_count"] >= state["max_reflections"]:
        best = state["best_attempt"]
        state["current_route"] = best["route"]
        state["waypoints"] = best["waypoints"]
        state["violations"] = best["messages"]
        state["is_safe"] = not best["violations"]
        logs.append(
            f"  [!] Reflection budget exhausted ({state['reflection_count']}/{state['max_reflections']}). "
            f"Returning least-violating route ({len(best['violations'])} violation(s))."
        )
        return state

    state["reflection_count"] += 1
    logs.append(f"  [!] Reflection {state['reflection_count']}/{state['max_reflections']}: computing detour waypoints...")
    changed = False
    for v in violations:
        key = v["hazard"]["street"]
        tries = state["detours"].get(key, {}).get("tries", 0) + 1
        detour = compute_detour_waypoint(v, coords, hazards, tries)
        if detour is None:
            logs.append(f"  -> No valid detour waypoint for '{key}' (try {tries}).")
            state["detours"].setdefault(key, {"tries": 0})["tries"] = tries
            continue
        state["detours"][key] = {
            "tries": tries,
            "waypoint": detour["waypoint"],
            "order": _origin_destination_position(detour["waypoint"], state["origin"], state["destination"]),
        }
        changed = True
        logs.append(
            f"  -> Detour for '{key}' (try {tries}): waypoint {detour['waypoint']} "
            f"[side {'+' if detour['side'] > 0 else '-'}, {detour['offset_m']}m from zone centre, "
            f"snapped {detour['snap_distance_m']}m to road]"
        )

    placed = sorted(
        (d for d in state["detours"].values() if "waypoint" in d), key=lambda d: d["order"]
    )
    state["waypoints"] = [d["waypoint"] for d in placed]
    state["should_retry"] = changed
    if not changed:
        logs.append("  [!] No detour could be computed; stopping reflection.")
        best = state["best_attempt"]
        state["current_route"] = best["route"]
        state["waypoints"] = best["waypoints"]
        state["violations"] = best["messages"]
        state["is_safe"] = not best["violations"]
    return state
