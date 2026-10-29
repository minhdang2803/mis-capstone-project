import pytest

from app.agents import reflector
from app.agents.reflector import find_violations, reflector_agent
from app.core.geometry import from_local_xy, haversine_distance

LAT, LON = 10.80, 106.70
HAZ = {"street": "Quốc Hương", "lat": LAT, "lon": LON, "radius_m": 300.0}


def pt(dx, dy):
    return list(from_local_xy(dx, dy, LAT, LON))


def route(*points, distance=1000.0):
    return {"coordinates": [pt(*p) for p in points], "distance_m": distance, "duration_s": 100.0}


def make_state(current_route, hazards=(HAZ,), max_reflections=2, detour_strategy="ring"):
    return {
        "origin": pt(-1000, 0), "destination": pt(1000, 0), "avoid_points": list(hazards),
        "current_route": current_route, "reflection_count": 0, "max_reflections": max_reflections,
        "is_safe": False, "violations": [], "waypoints": [], "logs": [], "should_retry": False,
        "detours": {}, "history": [], "best_attempt": None, "detour_strategy": detour_strategy,
    }


@pytest.fixture(autouse=True)
def fake_snap(monkeypatch):
    """Snapping returns the point unchanged, 5 m from the road."""
    monkeypatch.setattr(reflector, "snap_to_road", lambda p: {"point": [round(p[0], 5), round(p[1], 5)], "snap_distance_m": 5.0})


@pytest.fixture(autouse=True)
def fake_router(monkeypatch):
    """Routes straight from point to point, so a waypoint bends the polyline around it."""

    def route_through(origin, destination, waypoints=None):
        coords = [origin] + list(waypoints or []) + [destination]
        distance = sum(
            haversine_distance(a[0], a[1], b[0], b[1]) for a, b in zip(coords, coords[1:])
        )
        return {"coordinates": coords, "distance_m": distance, "duration_s": distance / 8.0}

    monkeypatch.setattr(reflector, "calculate_route_osrm", route_through)
    return route_through


def test_detects_crossing_between_far_apart_vertices():
    assert len(find_violations(route((-900, 40), (900, 40))["coordinates"], [HAZ])) == 1


def test_safe_route_ends_the_loop():
    state = reflector_agent(make_state(route((-900, 600), (900, 600))))
    assert state["is_safe"] and not state["should_retry"] and state["reflection_count"] == 0


def test_ring_search_returns_a_waypoint_whose_whole_route_clears_the_zone(fake_router):
    state = reflector_agent(make_state(route((-900, 80), (900, 80))))  # route passes 80 m north of centre
    assert not state["is_safe"] and state["should_retry"] and state["reflection_count"] == 1
    (wp,) = state["waypoints"]
    assert haversine_distance(wp[0], wp[1], LAT, LON) >= HAZ["radius_m"]
    detoured = fake_router(state["origin"], state["destination"], state["waypoints"])
    assert find_violations(detoured["coordinates"], [HAZ]) == []


def test_ring_search_prefers_the_innermost_ring_that_works():
    state = reflector_agent(make_state(route((-900, 80), (900, 80))))
    (wp,) = state["waypoints"]
    offset = haversine_distance(wp[0], wp[1], LAT, LON) - HAZ["radius_m"]
    assert offset == pytest.approx(150.0, abs=1.0)  # the first ring, not 300/600/1000


def test_ring_search_stops_when_no_candidate_improves(monkeypatch):
    """Every candidate route still crosses the zone, so there is nothing to hand back."""
    monkeypatch.setattr(reflector, "calculate_route_osrm",
                        lambda o, d, waypoints=None: route((-900, 10), (900, 10), distance=9000.0))
    state = reflector_agent(make_state(route((-900, 80), (900, 80))))
    assert not state["should_retry"] and not state["is_safe"]


def test_perpendicular_strategy_tries_the_opposite_side_on_the_second_attempt():
    state = make_state(route((-900, 80), (900, 80)), detour_strategy="perpendicular")
    reflector_agent(state)
    first = state["waypoints"][0]
    assert first[0] > LAT  # pushed to the north, the side the route already used
    state["current_route"] = route((-900, 80), (900, 80))
    reflector_agent(state)
    assert state["waypoints"][0][0] < LAT < first[0]


def test_reflection_count_never_exceeds_budget_and_best_route_is_returned():
    bad = route((-900, 10), (900, 10), distance=1000)       # 290 m penetration
    better = route((-900, 200), (900, 200), distance=1500)  # 100 m penetration
    state = make_state(bad, max_reflections=1)
    reflector_agent(state)                                   # reflection 1, retry
    state["current_route"] = better
    reflector_agent(state)                                   # budget exhausted
    assert state["reflection_count"] == 1
    assert not state["should_retry"] and not state["is_safe"]
    assert state["current_route"] is better and len(state["history"]) == 2


def test_no_retry_when_reflection_disabled():
    state = reflector_agent(make_state(route((-900, 80), (900, 80)), max_reflections=0))
    assert not state["should_retry"] and state["reflection_count"] == 0 and not state["is_safe"]


def test_stops_when_no_valid_detour_exists(monkeypatch):
    monkeypatch.setattr(reflector, "snap_to_road", lambda p: {"point": p, "snap_distance_m": 999.0})
    state = reflector_agent(make_state(route((-900, 80), (900, 80))))
    assert not state["should_retry"] and not state["is_safe"]


def test_waypoint_rejected_when_it_lands_inside_another_zone(monkeypatch):
    blocker = {"street": "Blocker", "lat": pt(0, 450)[0], "lon": pt(0, 450)[1], "radius_m": 400.0}
    state = reflector_agent(make_state(route((-900, 80), (900, 80)), hazards=(HAZ, blocker)))
    for wp in state["waypoints"]:
        assert haversine_distance(wp[0], wp[1], blocker["lat"], blocker["lon"]) >= blocker["radius_m"]


def test_waypoints_are_ordered_from_origin_to_destination():
    a = {"street": "A", "lat": pt(-600, 0)[0], "lon": pt(-600, 0)[1], "radius_m": 150.0}
    b = {"street": "B", "lat": pt(600, 0)[0], "lon": pt(600, 0)[1], "radius_m": 150.0}
    state = make_state(route((-900, 20), (900, 20)), hazards=(b, a), detour_strategy="perpendicular")
    reflector_agent(state)  # hazards listed out of order
    assert len(state["waypoints"]) == 2
    assert state["waypoints"][0][1] < state["waypoints"][1][1]  # west before east
