from app.agents import reasoning, reflector
from app.core.geometry import from_local_xy
from app.core.settings import settings
from app.services.geocoding_service import HCMC_STREET_GAZETTEER
from app.services.workflow_service import run_langgraph_workflow

STREET = next(iter(HCMC_STREET_GAZETTEER))
HAZ = HCMC_STREET_GAZETTEER[STREET]


def line(offset_north_m, ref=HAZ):
    return [list(from_local_xy(x, offset_north_m, ref["lat"], ref["lon"])) for x in (-1500, 1500)]


def test_graph_loops_until_safe(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")  # gazetteer perception, no network
    monkeypatch.setattr(reflector, "snap_to_road", lambda p: {"point": p, "snap_distance_m": 1.0})
    calls = []

    def fake_route(origin, destination, waypoints=None):
        calls.append(list(waypoints or []))
        coords = line(10) if not waypoints else line(HAZ["radius_m"] + 400)  # detour waypoint clears the zone
        return {"coordinates": coords, "distance_m": 3000.0 + 100 * len(calls), "duration_s": 300.0}

    monkeypatch.setattr(reasoning, "calculate_route_osrm", fake_route)
    res = run_langgraph_workflow("q", f"Đường {STREET} ngập sâu", [10.7, 106.6], [10.9, 106.8])
    assert res["is_safe"] and res["reflection_count"] == 1
    assert calls[0] == [] and len(calls[1]) == 1
    assert res["perception_source"] == "gazetteer_fallback"


def test_reflection_disabled_routes_once(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    n = []
    monkeypatch.setattr(reasoning, "calculate_route_osrm",
                        lambda o, d, waypoints=None: n.append(1) or {"coordinates": line(10), "distance_m": 3000.0, "duration_s": 300.0})
    res = run_langgraph_workflow("q", f"Đường {STREET} ngập", [10.7, 106.6], [10.9, 106.8], enable_reflection=False)
    assert len(n) == 1 and not res["is_safe"] and res["reflection_count"] == 0
