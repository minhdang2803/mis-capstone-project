# Multi-Agent Traffic Routing Backend for Flood Hazard Avoidance in Ho Chi Minh City

Backend for **Research Question 1 (RQ1)** of a Master's thesis in MIS. It reads unstructured Vietnamese flood news, turns it into spatial hazard zones, routes around them with a real routing engine, and verifies the result.

## Architecture (LangGraph `StateGraph`)

```
news text → Perception → Reasoning (OSRM) → Reflector ─safe/budget spent→ END
                              ▲                  │ violation
                              └── detour waypoints┘
```

- **Traffic Perception Agent** (`app/agents/perception.py`): Gemini structured extraction of flooded streets, then geocoding (local blackspot gazetteer → Nominatim → Photon). In strict mode a Gemini failure raises instead of silently using the gazetteer; the state always records `perception_source`.
- **Route Reasoning Agent** (`app/agents/reasoning.py`): routes through a real OSRM server (`app/services/osrm_service.py`) via any detour waypoints.
- **Reflector Agent** (`app/agents/reflector.py`): checks the route polyline **segments** (not just vertices) against hazard zones. On a violation it places a detour waypoint perpendicular to the route, beyond the zone, snapped to the road network (OSRM `/nearest`); later attempts try the opposite side and larger margins. If the reflection budget runs out it returns the least-violating route with `is_safe=False`.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
cp .env.example .env                       # add your own GOOGLE_API_KEY, never commit it

scripts/setup_osrm.sh                      # one-off: downloads the Vietnam OSM extract, crops to HCMC, builds OSRM data
docker compose up -d osrm                  # OSRM on http://localhost:5001 (macOS reserves port 5000)
.venv/bin/python tests/smoke_check.py      # verifies OSRM and Gemini are really reachable

.venv/bin/python -m app.main               # API on :8000, docs at /docs
```

## RQ1 experiment

The proposed system is compared against two baselines (B1, B2) on the same scenarios, all judged by the same `ground_truth_hazards`. B1+ is an extra ablation, not a third baseline.

| System | Description | Role |
|---|---|---|
| **B1 OSRM** | Plain OSRM shortest route | Baseline 1 |
| **B2 Single-Agent LLM** | One Gemini agent with `geocode_street` and `get_route` tools; no role split, no verifier | Baseline 2 |
| **Proposed** | Perception → Reasoning → Reflector loop | Proposed system |
| B1+ (ablation) | Perception + OSRM's own alternative routes, no reflection | Isolates what reflection adds |

Metrics: avoidance rate (all scenarios, and feasible ones only), extraction precision / recall, grounding accuracy, path overhead vs. B1 (km), latency (mean, p95, share under the 3.5 s target), reflection count.

```bash
.venv/bin/python scripts/validate_scenarios.py data/scenarios_v2.json
.venv/bin/python -u tests/run_rq1_experiment.py --scenarios data/scenarios_v2.json \
    --runs 1 --out data/results_rq1_v2.csv | tee run_v2.log          # strict: aborts if Gemini/OSRM is down
```

Each run writes the CSV given by `--out` (one row per scenario × system × run, default `data/results_rq1.csv`) and a matching `*_summary.json`. On the Gemini free tier, run one `--runs 1` pass per day; the script stops and says so when the daily quota runs out.

### Datasets

- `data/scenarios_v2.json` (**main set for the report**, 42 scenarios): built by `scripts/build_scenarios_from_news.py` from the verified articles in `data/news_candidates.json` plus the sound legacy scenarios. Every scenario is feasible (endpoints outside all hazard zones) and discriminating (plain OSRM crosses a hazard). Repaired legacy scenarios keep their original endpoints in `original_origin` / `original_destination`. To favour accuracy over size, the following were removed by hand after the build:
  - 6 news scenarios flagged `needs_review`, because a ground-truth street came from a single geocoder or from an unreviewed gazetteer entry;
  - ground-truth streets the scenario's `news_context` never mentions (legacy #6 Bạch Đằng, #1 Xuân Thủy, #2 Dương Văn Cam), and two scenarios that became unusable as a result (legacy #10, no longer discriminating; legacy #19, its only street is absent from the text).

  Re-running the builder brings these back, so re-apply the filter or edit the builder first. News excerpts are not yet checked verbatim against the source articles (`excerpt_verified: false`).
- `data/hcmc_flood_blackspots.json`: gazetteer of 118 flood blackspots (78 original + 40 added in v1.1.0 by `scripts/expand_gazetteer.py`). Entries that only one geocoder could confirm, plus wrong matches, are listed in `data/gazetteer_unresolved.json` instead (19 streets). Each coordinate is one point on the street, not the flooded segment.
- `data/scenarios.json`: the original 20 scenarios (kept for reference and for the first benchmark). `validate_scenarios.py` flags 5 whose origin or destination lies inside a ground-truth hazard zone (unwinnable) and 10 where plain OSRM already avoids every hazard (non-discriminating); the benchmark reports avoidance both over all and over feasible scenarios.
- `data/scenarios_extended.json`: the 20 above plus 20 **synthetic** scenarios (`"source_type": "synthetic"`, no `source_url`) generated from `data/hcmc_flood_blackspots.json` with real OSRM routes (`scripts/generate_scenarios.py`). They are not real news, and the gazetteer comes from the same file, so geocoding on them is easy by construction. Report them separately from the real-news set.

## Tests

```bash
.venv/bin/python -m pytest -q tests        # offline; OSRM and Gemini are mocked
RUN_LLM_TESTS=1 .venv/bin/python -m pytest tests/test_perception.py   # live Gemini tests
```

## Deployment

> **Draft, not yet tested on a real server.** The compose file validates and the image builds locally; nothing more has been verified.

`docker-compose.prod.yml` runs Caddy (automatic HTTPS) → backend → OSRM; only Caddy is exposed. Put secrets in a server-side `.env`, set `CORS_ORIGINS` to your app's origin, and run `DOMAIN=api.example.com docker compose -f docker-compose.prod.yml up -d --build`.

## Known limitations

- OSRM's `car` profile does not model motorbikes, which dominate HCMC traffic.
- OSRM has no flood awareness, which is the gap the agents fill. The OSM extract date is recorded in `osrm/data/extract_downloaded_at.txt`.
- Hazards on a bridge or a road with no alternative cannot be avoided, so the avoidance rate stays below 100%.
- A detour waypoint can make OSRM take a U-turn near it; such routes are kept only if they violate fewer hazards than the best so far.
- Public Nominatim/Photon forbid heavy use; self-host a geocoder or rely on the gazetteer in production.
- Latency is far above the 3.5 s target, mostly because of Gemini calls; Gemini perception is not cached yet.
- The model is `gemini-3.1-flash-lite`, because `gemini-2.5-flash` (named in the proposal) is not available to new API users.
- The Reflector does not merge nearby hazard zones or detect U-turns explicitly.
- The scenario set is small (42), so differences of a few scenarios between systems are not statistically significant.
