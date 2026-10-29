"""
Validates a scenario file before it is used for benchmarking.
Usage: python scripts/validate_scenarios.py [data/scenarios.json]
Exit code 1 when any ERROR is found; WARNINGs are informational.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.geometry import haversine_distance
from app.services.evaluation import evaluate_route, scenario_feasible
from app.services.osrm_service import OSRMError, calculate_route_osrm

HCMC_BBOX = (10.35, 106.35, 11.20, 107.05)  # min_lat, min_lon, max_lat, max_lon
REQUIRED = ["id", "title", "user_query", "news_context", "origin", "destination", "ground_truth_hazards"]


def in_hcmc(lat, lon):
    return HCMC_BBOX[0] <= lat <= HCMC_BBOX[2] and HCMC_BBOX[1] <= lon <= HCMC_BBOX[3]


def validate(path, check_routes=True):
    with open(path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    errors, warnings = [], []
    seen_ids = set()
    for sc in scenarios:
        sid = sc.get("id")
        tag = f"#{sid}"
        for key in REQUIRED:
            if key not in sc:
                errors.append(f"{tag}: missing '{key}'")
        if sid in seen_ids:
            errors.append(f"{tag}: duplicate id")
        seen_ids.add(sid)
        if any(k not in sc for k in REQUIRED):
            continue
        for end in ("origin", "destination"):
            if not in_hcmc(sc[end]["lat"], sc[end]["lon"]):
                errors.append(f"{tag}: {end} outside HCMC bounding box")
        if not sc["ground_truth_hazards"]:
            errors.append(f"{tag}: no ground_truth_hazards")
        for h in sc["ground_truth_hazards"]:
            if not in_hcmc(h["lat"], h["lon"]) or h.get("radius_m", 0) <= 0:
                errors.append(f"{tag}: bad hazard '{h.get('street')}'")
            if h["street"].lower() not in sc["news_context"].lower():
                warnings.append(f"{tag}: ground-truth street '{h['street']}' not literally in news_context")
        if not sc.get("source_url") and sc.get("source_type") != "synthetic":
            warnings.append(f"{tag}: no source_url (real-news scenarios should cite one)")
        o = [sc["origin"]["lat"], sc["origin"]["lon"]]
        d = [sc["destination"]["lat"], sc["destination"]["lon"]]
        if not scenario_feasible(o, d, sc["ground_truth_hazards"]):
            warnings.append(f"{tag}: UNWINNABLE, origin or destination lies inside a ground-truth hazard zone")
        if haversine_distance(*o, *d) < 300:
            warnings.append(f"{tag}: origin and destination are under 300 m apart")
        if check_routes:
            try:
                route = calculate_route_osrm(o, d)
                if evaluate_route(route["coordinates"], sc["ground_truth_hazards"])["is_safe"]:
                    warnings.append(f"{tag}: plain OSRM route already avoids every hazard (scenario does not discriminate)")
            except OSRMError as e:
                errors.append(f"{tag}: OSRM unavailable ({e})")
                check_routes = False
    return scenarios, errors, warnings


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/scenarios.json"
    scenarios, errors, warnings = validate(path)
    print(f"{path}: {len(scenarios)} scenarios, {len(errors)} error(s), {len(warnings)} warning(s)")
    for e in errors:
        print("  ERROR  ", e)
    for w in warnings:
        print("  WARNING", w)
    sys.exit(1 if errors else 0)
