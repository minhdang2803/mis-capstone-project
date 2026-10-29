from app.services import geocoding_service as gs


def test_name_in_text_is_whole_word():
    assert gs.name_in_text("bình chiểu", "Mưa lớn ở đường Bình Chiểu hôm nay")
    assert not gs.name_in_text("uốc", "đường Quốc Hương ngập")  # no substring-inside-a-word matches


def test_gazetteer_prefers_exact_then_longest(monkeypatch):
    monkeypatch.setattr(gs, "HCMC_STREET_GAZETTEER", {
        "bình": {"lat": 1.0, "lon": 1.0},
        "bình chiểu": {"lat": 2.0, "lon": 2.0},
    })
    assert gs._lookup_gazetteer("bình chiểu")["key"] == "bình chiểu"
    assert gs._lookup_gazetteer("đường bình chiểu cũ")["key"] == "bình chiểu"
    assert gs._lookup_gazetteer("hậu giang") is None


# ---- remote fallback (Nominatim / Photon): validation and agreement ----
import pytest
import requests


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p


@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setattr(gs, "HCMC_STREET_GAZETTEER", {})  # force the Nominatim/Photon path whatever the real gazetteer holds
    gs._remote_geocode.cache_clear()
    monkeypatch.setattr(gs.time, "sleep", lambda s: None)
    yield
    gs._remote_geocode.cache_clear()


def nom_item(name, lat, lon, category="highway"):
    return {"lat": str(lat), "lon": str(lon), "category": category, "name": name}


def photon_item(name, lat, lon, key="highway"):
    return {"geometry": {"coordinates": [lon, lat]}, "properties": {"name": name, "osm_key": key}}


def patch_services(monkeypatch, nominatim=(), photon=()):
    def fake_get(url, params=None, headers=None, timeout=None):
        if "nominatim" in url:
            return FakeResp(list(nominatim))
        return FakeResp({"features": list(photon)})

    monkeypatch.setattr(requests, "get", fake_get)


def test_agreeing_services_are_trusted(remote, monkeypatch):
    patch_services(monkeypatch, [nom_item("Đường Phạm Đức Sơn", 10.7197, 106.6224)], [photon_item("Đường Phạm Đức Sơn", 10.7213, 106.6225)])
    r = gs.geocode_street("Phạm Đức Sơn")
    assert r["geocode_source"] == "nominatim+photon" and r["geocode_confidence"] == "agreed"
    assert r["radius_m"] == gs.settings.DEFAULT_HAZARD_RADIUS_M


def test_single_valid_source_is_accepted_but_marked(remote, monkeypatch):
    patch_services(monkeypatch, [], [photon_item("Hoàng Quốc Việt", 10.7138, 106.7342)])
    r = gs.geocode_street("Hoàng Quốc Việt")
    assert r["geocode_source"] == "photon" and r["geocode_confidence"] == "single_source"


def test_non_road_features_are_rejected(remote, monkeypatch):
    patch_services(monkeypatch, [nom_item("Đường Lê Cơ", 10.76, 106.60, category="office")], [photon_item("Lê Cơ", 10.76, 106.60, key="amenity")])
    assert gs.geocode_street("Lê Cơ") is None


def test_name_must_match_the_queried_street(remote, monkeypatch):
    patch_services(monkeypatch, [nom_item("Đường Láng Le Bàu Cò", 10.74, 106.54)], [photon_item("Trường THCS Bình Hưng Hòa", 10.8152, 106.6000)])
    assert gs.geocode_street("Lê Cơ") is None


def test_results_outside_hcmc_are_rejected(remote, monkeypatch):
    patch_services(monkeypatch, [nom_item("Đường Hùng Vương Test", 16.46, 107.59)], [])  # Huế, not HCMC
    assert gs.geocode_street("Hùng Vương Test") is None


def test_disagreeing_services_yield_none(remote, monkeypatch):
    patch_services(monkeypatch, [nom_item("Đường Nguyễn Trãi", 10.75, 106.66)], [photon_item("Nguyễn Trãi", 10.90, 106.80)])
    assert gs.geocode_street("Nguyễn Trãi") is None


def test_service_errors_yield_none(remote, monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "get", boom)
    assert gs.geocode_street("Đường Không Tồn Tại") is None


def test_remote_results_are_cached(remote, monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        return FakeResp([nom_item("Đường Abc", 10.8, 106.7)] if "nominatim" in url else {"features": []})

    monkeypatch.setattr(requests, "get", fake_get)
    gs.geocode_street("Abc")
    gs.geocode_street("Abc")
    assert len(calls) == 2  # one Nominatim + one Photon call, the repeat is served from cache
