from langchain_core.messages import AIMessage

from app.agents import single_agent


class ScriptedModel:
    """Stands in for the Gemini chat model: replays a fixed list of AI messages."""
    def __init__(self, script):
        self.script = list(script)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return self.script.pop(0)


def test_single_agent_geocodes_then_routes(monkeypatch):
    monkeypatch.setattr(single_agent, "geocode_street", lambda s, ward=None, district=None: {"street": s, "lat": 10.8, "lon": 106.7, "radius_m": 350.0})
    route = {"distance_m": 900.0, "duration_s": 100.0, "coordinates": [[10.8, 106.7], [10.81, 106.71]]}
    monkeypatch.setattr(single_agent, "calculate_route_osrm", lambda o, d, waypoints=None: route)
    model = ScriptedModel([
        AIMessage(content="", tool_calls=[{"name": "geocode_street", "args": {"street": "Quốc Hương"}, "id": "1"}]),
        AIMessage(content="", tool_calls=[{"name": "get_route", "args": {"waypoints": [[10.81, 106.72]]}, "id": "2"}]),
        AIMessage(content="Xong."),
    ])
    out = single_agent.run_single_agent("q", "Quốc Hương ngập", [10.7, 106.6], [10.9, 106.8], model=model)
    assert out["current_route"] == route
    assert [h["street"] for h in out["perceived_hazards"]] == ["Quốc Hương"]
    assert out["tool_calls"] == 2


def test_single_agent_without_a_route_reports_none(monkeypatch):
    out = single_agent.run_single_agent("q", "news", [10.7, 106.6], [10.9, 106.8], model=ScriptedModel([AIMessage(content="Không biết.")]))
    assert out["current_route"] is None and out["tool_calls"] == 0
