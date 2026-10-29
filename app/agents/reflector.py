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
from app.services.osrm_service import OSRMError, calculate_route_osrm, snap_to_road


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


def _ring_candidates(hazard: Dict[str, Any], offset_m: float, bearings: int) -> List[List[float]]:
    """Evenly spaced points on a circle of radius hazard.radius_m + offset_m around the zone centre."""
    radius = hazard["radius_m"] + offset_m
    points = []
    for k in range(bearings):
        angle = 2.0 * math.pi * k / bearings
        points.append(list(from_local_xy(radius * math.cos(angle), radius * math.sin(angle), hazard["lat"], hazard["lon"])))
    return points


def _snap_candidate(point: List[float], hazards: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Snapped road point, or None when it sits too far from a road or inside a hazard zone."""
    snapped = snap_to_road(point)
    p = snapped["point"]
    if snapped["snap_distance_m"] > settings.MAX_SNAP_DISTANCE_M:
        return None
    if any(haversine_distance(p[0], p[1], z["lat"], z["lon"]) < z["radius_m"] for z in hazards):
        return None
    return snapped


def search_detour_waypoint(
    state: AgentState, violations: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Ring search for a detour waypoint (Reflector v2).

    Places candidate waypoints on rings around every violated hazard, routes through each one
    together with the waypoints already placed, and scores the *whole* resulting route against
    *all* hazards. Rings are searched innermost first and the search stops after the first ring
    that yields a fully safe route, so a short detour beats a long one.

    Unlike the perpendicular placement in `compute_detour_waypoint`, the direction is not fixed:
    when the only way round a zone is a different street rather than the same street pushed
    sideways, a ring candidate can find it.

    Returns the best candidate, or None when no candidate lands on a usable road.
    """
    hazards = state["avoid_points"]
    origin, destination = state["origin"], state["destination"]
    placed = [d for d in state["detours"].values() if "waypoint" in d]
    best: Optional[Dict[str, Any]] = None
    seen = set()
    routes_tried = 0

    for offset_m in settings.DETOUR_RING_OFFSETS_M:
        for violation in violations:
            for point in _ring_candidates(violation["hazard"], offset_m, settings.DETOUR_BEARINGS):
                snapped = _snap_candidate(point, hazards)
                if snapped is None:
                    continue
                # many bearings snap onto the same stretch of road; route each road point once
                key = (round(snapped["point"][0], 5), round(snapped["point"][1], 5))
                if key in seen:
                    continue
                seen.add(key)

                order = _origin_destination_position(snapped["point"], origin, destination)
                candidate = {"waypoint": snapped["point"], "order": order}
                waypoints = [d["waypoint"] for d in sorted(placed + [candidate], key=lambda d: d["order"])]
                try:
                    route = calculate_route_osrm(origin, destination, waypoints)
                except OSRMError:
                    continue
                routes_tried += 1

                route_violations = find_violations(route["coordinates"], hazards)
                score = (len(route_violations), _penetration_m(route_violations), route["distance_m"])
                if best is None or score < best["score"]:
                    best = {
                        "waypoint": snapped["point"],
                        "order": order,
                        "street": violation["hazard"]["street"],
                        "route": route,
                        "violations": route_violations,
                        "score": score,
                        "offset_m": round(offset_m),
                        "snap_distance_m": snapped["snap_distance_m"],
                    }
        if best is not None and not best["violations"]:
            break  # an inner ring already works; no need to search further out

    if best is not None:
        best["routes_tried"] = routes_tried
    return best


def _reflect_with_ring_search(state: AgentState, violations: List[Dict[str, Any]], attempt: Dict[str, Any]) -> bool:
    """Searches for a detour waypoint and records it. Returns True when the route improved."""
    logs = state["logs"]
    best = search_detour_waypoint(state, violations)
    if best is None:
        logs.append("  -> No candidate waypoint landed on a usable road.")
        return False
    if best["score"] >= attempt["score"]:
        logs.append(
            f"  -> Best of {best['routes_tried']} candidate route(s) is no better than the current one; "
            "stopping reflection."
        )
        return False

    state["detours"][f"{best['street']}#{state['reflection_count']}"] = {
        "tries": 1, "waypoint": best["waypoint"], "order": best["order"],
    }
    logs.append(
        f"  -> Detour via '{best['street']}' ring at {best['offset_m']}m: waypoint {best['waypoint']} "
        f"[{best['routes_tried']} candidate route(s) tried, snapped {best['snap_distance_m']}m to road, "
        f"{len(best['violations'])} violation(s) left]"
    )
    return True


def _reflect_with_perpendicular(state: AgentState, violations: List[Dict[str, Any]]) -> bool:
    """Reflector v1: one perpendicular waypoint per violation. Returns True when a waypoint was placed."""
    logs = state["logs"]
    changed = False
    coords = state["current_route"]["coordinates"]
    for v in violations:
        key = v["hazard"]["street"]
        tries = state["detours"].get(key, {}).get("tries", 0) + 1
        detour = compute_detour_waypoint(v, coords, state["avoid_points"], tries)
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
    return changed


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
    strategy = state.get("detour_strategy", "ring")
    logs.append(
        f"  [!] Reflection {state['reflection_count']}/{state['max_reflections']}: "
        f"computing detour waypoints ({strategy})..."
    )
    if strategy == "perpendicular":
        changed = _reflect_with_perpendicular(state, violations)
    else:
        changed = _reflect_with_ring_search(state, violations, attempt)

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
