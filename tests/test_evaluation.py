from app.core.geometry import from_local_xy
from app.services.evaluation import evaluate_route, extraction_metrics, normalize_name, scenario_feasible

LAT, LON = 10.80, 106.70
HAZ = {"street": "Quốc Hương", "lat": LAT, "lon": LON, "radius_m": 300}


def pt(dx, dy):
    return list(from_local_xy(dx, dy, LAT, LON))


def test_normalize_name_is_accent_and_prefix_insensitive():
    assert normalize_name("Đường Quốc  Hương") == normalize_name("quoc huong")


def test_route_through_zone_is_unsafe_and_margin_negative():
    verdict = evaluate_route([pt(-600, 100), pt(600, 100)], [HAZ])
    assert not verdict["is_safe"] and verdict["violated"] == ["Quốc Hương"]
    assert verdict["min_margin_m"] == -200


def test_route_outside_zone_is_safe():
    verdict = evaluate_route([pt(-600, 500), pt(600, 500)], [HAZ])
    assert verdict["is_safe"] and verdict["min_margin_m"] == 200


def test_missing_route_is_unsafe():
    assert not evaluate_route([], [HAZ])["is_safe"]


def test_scenario_feasibility():
    assert scenario_feasible(pt(-800, 0), pt(800, 0), [HAZ])
    assert not scenario_feasible(pt(-100, 0), pt(800, 0), [HAZ])


def test_extraction_metrics():
    gt = [HAZ, {"street": "Xuân Thủy", "lat": LAT + 0.01, "lon": LON, "radius_m": 250}]
    perceived = [
        {"street": "Quốc Hương", "lat": LAT, "lon": LON},                 # correct and grounded
        {"street": "Xuân Thủy", "lat": LAT + 0.05, "lon": LON},           # right street, geocoded 4 km away
        {"street": "Lê Lợi", "lat": LAT, "lon": LON},                     # hallucinated
    ]
    m = extraction_metrics(perceived, gt)
    assert m["extraction_recall"] == 1.0
    assert m["extraction_precision"] == round(2 / 3, 3)
    assert m["grounding_accuracy"] == 0.5


def test_extraction_metrics_with_no_hazards():
    assert extraction_metrics([], [])["extraction_recall"] == 1.0
    assert extraction_metrics([{"street": "X", "lat": 0, "lon": 0}], [])["extraction_precision"] == 0.0
