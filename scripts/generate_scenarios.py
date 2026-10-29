"""
Generates synthetic benchmark scenarios from the HCMC flood blackspot dataset using real OSRM routes,
and writes data/scenarios_extended.json = the existing scenarios + the synthetic ones.

For each blackspot a trip is built across the hazard zone: origin and destination sit on roads
(snapped with OSRM /nearest) on opposite sides, outside the zone, such that the plain OSRM route
really does cross it. Synthetic scenarios carry "source_type": "synthetic", no source_url, and a
templated news_context; they are NOT real news. Ground truth is the blackspot itself, so geocoding
grounding on them is easy by construction (the gazetteer is built from the same file).

Usage: python scripts/generate_scenarios.py [--target 40] [--seed 42]
Requires the local OSRM container (docker compose up -d osrm).
"""
import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.geometry import from_local_xy, haversine_distance
from app.services.evaluation import evaluate_route, normalize_name
from app.services.osrm_service import OSRMError, calculate_route_osrm, snap_to_road

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAUSE_TEXT = {
    "mưa lớn": "mưa lớn kéo dài",
    "triều cường": "triều cường dâng cao",
    "cả hai": "mưa lớn kết hợp triều cường",
}


def build_scenario(spot, rng, next_id):
    r = spot["radius_m"]
    for _ in range(16):
        bearing = rng.uniform(0, math.pi)
        ux, uy = math.cos(bearing), math.sin(bearing)
        d1, d2 = rng.uniform(300, 800), rng.uniform(300, 800)
        try:
            o = snap_to_road(list(from_local_xy(ux * (r + d1), uy * (r + d1), spot["lat"], spot["lon"])))["point"]
            d = snap_to_road(list(from_local_xy(-ux * (r + d2), -uy * (r + d2), spot["lat"], spot["lon"])))["point"]
            route = calculate_route_osrm(o, d)
        except OSRMError:
            continue
        # Ground truth is only the street the news reports; hazards the text never mentions are not fair to grade.
        gt = [spot]
        if any(haversine_distance(p[0], p[1], spot["lat"], spot["lon"]) < r + 30 for p in (o, d)):
            continue
        if evaluate_route(route["coordinates"], gt)["is_safe"]:
            continue  # plain OSRM already avoids it: the scenario would not discriminate between systems
        place = spot.get("landmark") or spot["street"]
        cause = CAUSE_TEXT.get(spot["cause"], spot["cause"])
        return {
            "id": next_id,
            "title": f"[Synthetic] {cause.capitalize()} gây ngập đường {spot['street']} ({spot['district']})",
            "user_query": f"Chỉ đường đi qua khu vực {spot['street']} và né điểm ngập",
            "news_context": (
                f"Do {cause}, tuyến đường {spot['street']} ({place}) thuộc {spot['district']} "
                f"đang ngập sâu, phương tiện di chuyển khó khăn."
            ),
            "source_type": "synthetic",
            "source_url": None,
            "origin": {"name": f"Điểm đi gần {spot['street']}", "lat": o[0], "lon": o[1]},
            "destination": {"name": f"Điểm đến sau {spot['street']}", "lat": d[0], "lon": d[1]},
            "ground_truth_hazards": [
                {"street": s["street"], "lat": s["lat"], "lon": s["lon"], "radius_m": s["radius_m"]} for s in gt
            ],
        }
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=40, help="total scenarios in the extended file")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    with open(os.path.join(ROOT, "data", "scenarios.json"), encoding="utf-8") as f:
        scenarios = json.load(f)
    with open(os.path.join(ROOT, "data", "hcmc_flood_blackspots.json"), encoding="utf-8") as f:
        spots = json.load(f)["blackspots"]

    used = {normalize_name(h["street"]) for sc in scenarios for h in sc["ground_truth_hazards"]}
    candidates = [s for s in spots if normalize_name(s["street"]) not in used]
    rng.shuffle(candidates)

    next_id = max(sc["id"] for sc in scenarios) + 1
    added = 0
    for spot in candidates:
        if len(scenarios) >= args.target:
            break
        sc = build_scenario(spot, rng, next_id)
        if sc:
            scenarios.append(sc)
            next_id += 1
            added += 1
            print(f"  + #{sc['id']} {spot['street']} ({len(sc['ground_truth_hazards'])} hazard(s))")
    out = os.path.join(ROOT, "data", "scenarios_extended.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out}: {len(scenarios)} scenarios ({added} synthetic added)")


if __name__ == "__main__":
    main()
