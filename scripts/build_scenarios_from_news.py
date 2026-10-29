"""
Builds data/scenarios_v2.json from the verified articles in data/news_candidates.json, plus the legacy
scenarios in data/scenarios.json that are sound (or can be repaired).

News scenarios
  * one article per event (event_group); newer articles with more resolvable streets win
  * news_context is the article excerpt; ground truth is only the streets that excerpt names, geocoded
    with the validated geocoder (gazetteer first, then agreeing Nominatim/Photon; unresolved streets are dropped)
  * origin and destination sit on real roads (OSRM /nearest) on opposite sides of a ground-truth zone, outside
    every zone, so that the plain OSRM route really crosses a hazard. Scenarios that cannot be built that way
    are dropped and reported.

Legacy scenarios
  * kept when feasible (endpoints outside every zone) and discriminating (plain OSRM crosses a hazard)
  * otherwise their endpoints are regenerated with the same news text and ground truth; the original endpoints
    are preserved in original_origin / original_destination

Everything needs a human pass: excerpts come from a page-reading tool and are not verified verbatim, and a
geocoded point is one point on the street, not the flooded segment.

Usage: python scripts/build_scenarios_from_news.py [--max 50] [--no-repair]
Requires the local OSRM container (docker compose up -d osrm).
"""
import argparse
import json
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(__file__))

from app.core.geometry import from_local_xy, haversine_distance
from app.services.evaluation import evaluate_route, normalize_name, scenario_feasible
from app.services.geocoding_service import geocode_street
from app.services.osrm_service import OSRMError, calculate_route_osrm, snap_to_road

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAX_SNAP_M = 120.0
ENDPOINT_MARGIN_M = 30.0
ATTEMPTS_PER_HAZARD = 8


def street_in_text(street, text):
    s, t = normalize_name(street), normalize_name(text)
    return re.search(rf"(?<!\w){re.escape(s)}(?!\w)", t) is not None


def load_review_set():
    with open(os.path.join(ROOT, "data", "hcmc_flood_blackspots.json"), encoding="utf-8") as f:
        return {normalize_name(s["street"]) for s in json.load(f)["blackspots"] if s.get("needs_review")}


def resolve_hazard(street, review_set):
    geo = geocode_street(street)
    if geo is None:
        return None
    return {
        "street": geo["street"], "lat": geo["lat"], "lon": geo["lon"], "radius_m": geo["radius_m"],
        "_needs_review": geo["geocode_source"] not in ("gazetteer", "nominatim+photon")
        or normalize_name(geo["street"]) in review_set,
    }


def find_trip(gt, rng):
    """Origin/destination on roads either side of a ground-truth zone such that plain OSRM crosses a zone."""
    order = list(range(len(gt)))
    rng.shuffle(order)
    for idx in order:
        target = gt[idx]
        r = target["radius_m"]
        for _ in range(ATTEMPTS_PER_HAZARD):
            bearing = rng.uniform(0, math.pi)
            ux, uy = math.cos(bearing), math.sin(bearing)
            d1, d2 = rng.uniform(300, 800), rng.uniform(300, 800)
            try:
                o = snap_to_road(list(from_local_xy(ux * (r + d1), uy * (r + d1), target["lat"], target["lon"])))
                d = snap_to_road(list(from_local_xy(-ux * (r + d2), -uy * (r + d2), target["lat"], target["lon"])))
                if o["snap_distance_m"] > MAX_SNAP_M or d["snap_distance_m"] > MAX_SNAP_M:
                    continue
                o, d = o["point"], d["point"]
                if not scenario_feasible(o, d, [{**h, "radius_m": h["radius_m"] + ENDPOINT_MARGIN_M} for h in gt]):
                    continue
                route = calculate_route_osrm(o, d)
            except OSRMError:
                continue
            if evaluate_route(route["coordinates"], gt)["is_safe"]:
                continue  # plain OSRM already avoids everything: would not discriminate
            return o, d, route
    return None


def clean_hazards(gt):
    return [{k: v for k, v in h.items() if not k.startswith("_")} for h in gt]


def build_news_scenarios(review_set, rng_seed):
    with open(os.path.join(ROOT, "data", "news_candidates.json"), encoding="utf-8") as f:
        articles = json.load(f)

    groups = {}
    for a in articles:
        groups.setdefault(a["event_group"], []).append(a)

    scenarios, dropped = [], []
    for group, items in sorted(groups.items()):
        scored = []
        for a in items:
            named = [s for s in a["streets"] if street_in_text(s, a["excerpt"])]
            scored.append((a["year"] >= 2022, len(named), a["year"], a, named))
        scored.sort(key=lambda x: x[:3], reverse=True)
        _, _, _, art, named = scored[0]

        gt = [h for h in (resolve_hazard(s, review_set) for s in named) if h]
        if not gt:
            dropped.append((art["id"], art["title"], "no street in the excerpt could be geocoded reliably"))
            continue
        trip = find_trip(gt, random.Random(f"{rng_seed}-{art['id']}"))
        if trip is None:
            dropped.append((art["id"], art["title"], "no road trip crossing the zone with endpoints outside every zone"))
            continue
        o, d, route = trip
        target = gt[0]["street"]
        scenarios.append({
            "title": f"{art['title']} ({art['published_date']})",
            "user_query": f"Chỉ đường đi qua khu vực {target} và né các điểm ngập",
            "news_context": art["excerpt"],
            "source_type": "news",
            "source_url": art["url"],
            "source_outlet": art["outlet"],
            "published_date": art["published_date"],
            "event_date": art["event_date"],
            "news_candidate_id": art["id"],
            "excerpt_verified": False,
            "needs_review": any(h["_needs_review"] for h in gt),
            "origin": {"name": f"Điểm đi gần {target}", "lat": o[0], "lon": o[1]},
            "destination": {"name": f"Điểm đến sau {target}", "lat": d[0], "lon": d[1]},
            "ground_truth_hazards": clean_hazards(gt),
        })
    return scenarios, dropped


def build_legacy_scenarios(repair, rng_seed):
    with open(os.path.join(ROOT, "data", "scenarios.json"), encoding="utf-8") as f:
        legacy = json.load(f)
    kept, repaired, dropped = [], [], []
    for sc in legacy:
        o = [sc["origin"]["lat"], sc["origin"]["lon"]]
        d = [sc["destination"]["lat"], sc["destination"]["lon"]]
        gt = sc["ground_truth_hazards"]
        base = {**sc, "legacy_id": sc["id"], "source_type": "news", "excerpt_verified": None}
        base.pop("id")
        try:
            route = calculate_route_osrm(o, d)
        except OSRMError as e:
            dropped.append((f"legacy#{sc['id']}", sc["title"], f"OSRM error: {e}"))
            continue
        if scenario_feasible(o, d, gt) and not evaluate_route(route["coordinates"], gt)["is_safe"]:
            kept.append(base)
            continue
        if not repair:
            dropped.append((f"legacy#{sc['id']}", sc["title"], "unwinnable or non-discriminating (repair disabled)"))
            continue
        trip = find_trip(gt, random.Random(f"{rng_seed}-legacy-{sc['id']}"))
        if trip is None:
            dropped.append((f"legacy#{sc['id']}", sc["title"], "could not regenerate endpoints"))
            continue
        no, nd, _ = trip
        base["original_origin"], base["original_destination"] = sc["origin"], sc["destination"]
        base["origin"] = {"name": f"Điểm đi gần {gt[0]['street']}", "lat": no[0], "lon": no[1]}
        base["destination"] = {"name": f"Điểm đến sau {gt[0]['street']}", "lat": nd[0], "lon": nd[1]}
        base["endpoints_regenerated"] = True
        repaired.append(base)
    return kept, repaired, dropped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=50, help="cap on total scenarios")
    parser.add_argument("--no-repair", dest="repair", action="store_false")
    parser.add_argument("--seed", default="42")
    parser.add_argument("--out", default=os.path.join(ROOT, "data", "scenarios_v2.json"))
    args = parser.parse_args()

    review_set = load_review_set()
    kept, repaired, legacy_dropped = build_legacy_scenarios(args.repair, args.seed)
    news, news_dropped = build_news_scenarios(review_set, args.seed)

    legacy_urls = {s.get("source_url") for s in kept + repaired}
    news = [s for s in news if s["source_url"] not in legacy_urls]

    combined = kept + repaired + news
    if len(combined) > args.max:
        # keep unmodified legacy first, then the newest news, then repaired legacy
        news.sort(key=lambda s: s["event_date"], reverse=True)
        combined = (kept + news + repaired)[: args.max]
    for i, sc in enumerate(combined, 1):
        sc["id"] = i
    combined = [{"id": s.pop("id"), **s} for s in combined]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"legacy kept as-is: {len(kept)} | legacy repaired: {len(repaired)} | news built: {len(news)} -> {len(combined)} scenarios")
    print(f"Wrote {args.out}")
    for label, rows in (("DROPPED (legacy)", legacy_dropped), ("DROPPED (news)", news_dropped)):
        for r in rows:
            print(f"  {label}: {r[0]} {r[1][:60]} -> {r[2]}")

    import validate_scenarios
    _, errors, warnings = validate_scenarios.validate(args.out)
    print(f"\nvalidate: {len(errors)} error(s), {len(warnings)} warning(s)")
    for e in errors:
        print("  ERROR  ", e)
    for w in warnings[:15]:
        print("  WARNING", w)


if __name__ == "__main__":
    main()
