from fastapi.testclient import TestClient

from app.api.v1.endpoints import routing
from app.main import app
from app.services.osrm_service import OSRMError

client = TestClient(app)
BODY = {"user_query": "q", "news_context": "n", "origin": {"lat": 10.8, "lon": 106.7}, "destination": {"lat": 10.81, "lon": 106.71}}


def test_osrm_outage_returns_503(monkeypatch):
    def boom(**kwargs):
        raise OSRMError("down")

    monkeypatch.setattr(routing, "run_langgraph_workflow", boom)
    resp = client.post("/api/v1/route/", json=BODY)
    assert resp.status_code == 503 and "unavailable" in resp.json()["detail"]


def test_unknown_scenario_is_404():
    assert client.post("/api/v1/route/scenario/99999").status_code == 404
