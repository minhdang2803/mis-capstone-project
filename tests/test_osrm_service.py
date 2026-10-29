import pytest
import requests

from app.core.settings import settings
from app.services import osrm_service
from app.services.osrm_service import OSRMError, calculate_route_osrm, calculate_routes_osrm, snap_to_road

ORIGIN = [10.8034, 106.7381]
DEST = [10.8040, 106.7320]

FAKE_ROUTE = {
    "distance": 850.4,
    "duration": 120.2,
    "geometry": {"coordinates": [[106.7381, 10.8034], [106.7350, 10.8037], [106.7320, 10.8040]]},
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ROUTE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(settings, "OSRM_CACHE_ENABLED", True)
    monkeypatch.setattr(osrm_service, "_session", None)


def patch_get(monkeypatch, payload, status=200, calls=None):
    def fake_get(self, url, params=None, timeout=None):
        if calls is not None:
            calls.append((url, params))
        return FakeResponse(payload, status)

    monkeypatch.setattr(requests.Session, "get", fake_get)


def test_route_converts_geojson_to_lat_lon(monkeypatch):
    calls = []
    patch_get(monkeypatch, {"code": "Ok", "routes": [FAKE_ROUTE]}, calls=calls)
    route = calculate_route_osrm(ORIGIN, DEST)
    assert route["coordinates"][0] == [10.8034, 106.7381]
    assert route["distance_m"] == 850.4 and route["duration_s"] == 120.2
    # OSRM URL must use lon,lat order
    assert "106.738100,10.803400;106.732000,10.804000" in calls[0][0]


def test_alternatives_only_for_two_point_requests(monkeypatch):
    calls = []
    patch_get(monkeypatch, {"code": "Ok", "routes": [FAKE_ROUTE, FAKE_ROUTE]}, calls=calls)
    assert len(calculate_routes_osrm(ORIGIN, DEST, alternatives=True)) == 2
    assert calls[0][1]["alternatives"] == "true"
    calculate_routes_osrm(ORIGIN, DEST, waypoints=[[10.81, 106.73]], alternatives=True)
    assert calls[1][1]["alternatives"] == "false"


def test_responses_are_cached(monkeypatch):
    calls = []
    patch_get(monkeypatch, {"code": "Ok", "routes": [FAKE_ROUTE]}, calls=calls)
    calculate_route_osrm(ORIGIN, DEST)
    calculate_route_osrm(ORIGIN, DEST)
    assert len(calls) == 1


def test_osrm_error_code_raises(monkeypatch):
    patch_get(monkeypatch, {"code": "NoRoute", "message": "no route"}, status=200)
    with pytest.raises(OSRMError):
        calculate_route_osrm(ORIGIN, DEST)


def test_unreachable_server_raises(monkeypatch):
    def boom(self, *a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests.Session, "get", boom)
    with pytest.raises(OSRMError):
        calculate_route_osrm(ORIGIN, DEST)


def test_snap_to_road(monkeypatch):
    patch_get(monkeypatch, {"code": "Ok", "waypoints": [{"location": [106.735281, 10.804145], "distance": 10.16}]})
    snapped = snap_to_road([10.8041, 106.7352])
    assert snapped == {"point": [10.80415, 106.73528], "snap_distance_m": 10.2}
