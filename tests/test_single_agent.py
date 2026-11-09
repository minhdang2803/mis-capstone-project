import json

from langchain_core.messages import AIMessage, ToolMessage

from app.agents import single_agent

HAZARD = {"street": "Quốc Hương", "lat": 10.8, "lon": 106.7, "radius_m": 350.0}
# Passes straight through HAZARD's centre
THROUGH = {"distance_m": 900.0, "duration_s": 100.0, "coordinates": [[10.79, 106.7], [10.81, 106.7]]}
# Same trip pushed ~1.1 km east of HAZARD, longer
AROUND = {"distance_m": 1500.0, "duration_s": 160.0, "coordinates": [[10.79, 106.71], [10.81, 106.71]]}


class ScriptedModel:
    """Stands in for the Gemini chat model: replays a fixed list of AI messages."""
    def __init__(self, script):
        self.script = list(script)
        self.tool_names = []
        self.seen = []

    def bind_tools(self, tools):
        self.tool_names = [t.name for t in tools]
        return self

    def invoke(self, messages):
        self.seen = list(messages)
        return self.script.pop(0)


def call(name, args, id_):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id_}])


def tool_result(model, id_):
    return json.loads(next(m.content for m in model.seen if isinstance(m, ToolMessage) and m.tool_call_id == id_))


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


def test_b2_default_has_no_verifier_tool():
    # B2's reported results must stay reproducible: verify=False binds exactly the original two tools
    model = ScriptedModel([AIMessage(content="Không biết.")])
    single_agent.run_single_agent("q", "news", [10.7, 106.6], [10.9, 106.8], model=model)
    assert model.tool_names == ["geocode_street", "get_route"]


def test_b2plus_check_reports_violation_of_geocoded_hazard(monkeypatch):
    monkeypatch.setattr(single_agent, "geocode_street", lambda s, ward=None, district=None: dict(HAZARD))
    monkeypatch.setattr(single_agent, "calculate_route_osrm", lambda o, d, waypoints=None: THROUGH)
    model = ScriptedModel([
        call("geocode_street", {"street": "Quốc Hương"}, "1"),
        call("get_route", {}, "2"),
        call("check_route_safety", {}, "3"),
        AIMessage(content="Xong."),
    ])
    single_agent.run_single_agent("q", "Quốc Hương ngập", [10.79, 106.7], [10.81, 106.7], model=model, verify=True)
    assert model.tool_names == ["geocode_street", "get_route", "check_route_safety"]
    check = tool_result(model, "3")
    assert check["is_safe"] is False and check["hazards_checked"] == 1
    assert [v["street"] for v in check["violations"]] == ["Quốc Hương"]
    assert check["violations"][0]["distance_m"] < check["violations"][0]["radius_m"]


def test_b2plus_check_before_any_route_is_an_error():
    model = ScriptedModel([call("check_route_safety", {}, "1"), AIMessage(content="Xong.")])
    out = single_agent.run_single_agent("q", "news", [10.7, 106.6], [10.9, 106.8], model=model, verify=True)
    assert "error" in tool_result(model, "1") and out["current_route"] is None


def test_b2plus_keeps_least_violating_route_not_the_last(monkeypatch):
    monkeypatch.setattr(single_agent, "geocode_street", lambda s, ward=None, district=None: dict(HAZARD))
    monkeypatch.setattr(single_agent, "calculate_route_osrm", lambda o, d, waypoints=None: AROUND if waypoints else THROUGH)
    script = [
        call("geocode_street", {"street": "Quốc Hương"}, "1"),
        call("get_route", {"waypoints": [[10.8, 106.71]]}, "2"),
        call("get_route", {}, "3"),
        AIMessage(content="Xong."),
    ]
    b2 = single_agent.run_single_agent("q", "Quốc Hương ngập", [10.79, 106.7], [10.81, 106.7], model=ScriptedModel(script))
    b2plus = single_agent.run_single_agent(
        "q", "Quốc Hương ngập", [10.79, 106.7], [10.81, 106.7], model=ScriptedModel(script), verify=True
    )
    # B2 answers with its last route even though it crosses the zone; B2+ keeps the clean, longer one
    assert b2["current_route"] is THROUGH
    assert b2plus["current_route"] is AROUND
