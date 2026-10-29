from app.agents import reasoning, reflector
from app.core.geometry import from_local_xy
from app.core.settings import settings
from app.services.geocoding_service import HCMC_STREET_GAZETTEER
from app.services.workflow_service import run_langgraph_workflow

STREET = next(iter(HCMC_STREET_GAZETTEER))
HAZ = HCMC_STREET_GAZETTEER[STREET]


def line(offset_north_m, ref=HAZ):
    return [list(from_local_xy(x, offset_north_m, ref["lat"], ref["lon"])) for x in (-1500, 1500)]


def fake_route(origin, destination, waypoints=None):
    """A detour waypoint clears the zone; the plain route runs 10 m north of its centre."""
    coords = line(10) if not waypoints else line(HAZ["radius_m"] + 400)
    return {"coordinates": coords, "distance_m": 3000.0 + 100 * len(waypoints or []), "duration_s": 300.0}


def test_graph_loops_until_safe(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")  # gazetteer perception, no network
    monkeypatch.setattr(reflector, "snap_to_road", lambda p: {"point": p, "snap_distance_m": 1.0})
    calls = []

    def reasoning_route(origin, destination, waypoints=None):
        calls.append(list(waypoints or []))
        return fake_route(origin, destination, waypoints)

    monkeypatch.setattr(reasoning, "calculate_route_osrm", reasoning_route)
    monkeypatch.setattr(reasoning, "calculate_routes_osrm",
                        lambda o, d, waypoints=None, alternatives=False: [reasoning_route(o, d, waypoints)])
    monkeypatch.setattr(reflector, "calculate_route_osrm", fake_route)
    res = run_langgraph_workflow("q", f"Đường {STREET} ngập sâu", [10.7, 106.6], [10.9, 106.8])
    assert res["is_safe"] and res["reflection_count"] == 1
    assert calls[0] == [] and len(calls[1]) == 1
    assert res["perception_source"] == "gazetteer_fallback"


def test_reflection_disabled_routes_once(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    n = []
    monkeypatch.setattr(reasoning, "calculate_routes_osrm",
                        lambda o, d, waypoints=None, alternatives=False: n.append(1) or [fake_route(o, d, waypoints)])
    res = run_langgraph_workflow("q", f"Đường {STREET} ngập", [10.7, 106.6], [10.9, 106.8], enable_reflection=False)
    assert len(n) == 1 and not res["is_safe"] and res["reflection_count"] == 0


def test_reasoning_prefers_the_alternative_that_avoids_the_hazard(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    crossing = {"coordinates": line(10), "distance_m": 3000.0, "duration_s": 300.0}
    clear = {"coordinates": line(HAZ["radius_m"] + 400), "distance_m": 4200.0, "duration_s": 400.0}
    monkeypatch.setattr(reasoning, "calculate_routes_osrm",
                        lambda o, d, waypoints=None, alternatives=False: [crossing, clear])
    res = run_langgraph_workflow("q", f"Đường {STREET} ngập", [10.7, 106.6], [10.9, 106.8])
    assert res["is_safe"] and res["reflection_count"] == 0
    assert res["current_route"] is clear  # the longer route wins because it clears the zone
