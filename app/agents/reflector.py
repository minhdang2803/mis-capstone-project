from app.models.state import AgentState
from app.core.geometry import haversine_distance

def reflector_agent(state: AgentState) -> AgentState:
    """
    Reflector Agent (Failure-Aware Verifier):
    Inspects polyline coordinates against avoid_points.
    Triggers Reflection Loop with detour waypoint if safety constraint is violated.
    """
    logs = state["logs"]
    logs.append("[3. Reflector Agent] Inspecting route polyline against hazard zones...")
    
    route_coords = state["current_route"]["coordinates"]
    hazards = state["avoid_points"]
    violations = []
    
    for hazard in hazards:
        h_lat, h_lon, h_rad = hazard["lat"], hazard["lon"], hazard["radius_m"]
        min_dist = float("inf")
        
        for pt in route_coords:
            d = haversine_distance(pt[0], pt[1], h_lat, h_lon)
            if d < min_dist:
                min_dist = d
                
        if min_dist < h_rad:
            msg = f"Intersection with hazard street '{hazard['street']}' (min dist: {min_dist:.1f}m < threshold {h_rad}m)"
            violations.append(msg)
            logs.append(f"  [X] VIOLATION: {msg}")
            
    if not violations:
        state["is_safe"] = True
        state["violations"] = []
        logs.append("  [OK] SUCCESS: Route is verified 100% safe from flood hazard zones!")
    else:
        state["is_safe"] = False
        state["violations"] = violations
        state["reflection_count"] += 1
        
        if state["reflection_count"] <= state["max_reflections"]:
            logs.append(f"  [!] Triggering Reflector Loop ({state['reflection_count']}/{state['max_reflections']}) -> Generating Detour Waypoint...")
            # Generate detour waypoint by offsetting from the first violated hazard
            h_lat = hazards[0]["lat"]
            h_lon = hazards[0]["lon"]
            detour_point = [round(h_lat + 0.008, 5), round(h_lon - 0.008, 5)]
            state["waypoints"] = [detour_point]
            logs.append(f"  -> Generated Detour Waypoint: {detour_point}")
        else:
            logs.append("  [!] Max reflections reached. Terminating with safety warning.")
            
    return state
