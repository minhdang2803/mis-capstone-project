"""
RQ1 benchmark: compares the proposed multi-agent system against two baselines on the same
scenarios, judged by the same ground-truth hazards.

  B1        plain OSRM shortest route                       (baseline)
  B2        single LLM agent with geocode + route tools     (baseline)
  PROPOSED  Perception -> Reasoning -> Reflector loop       (proposed system)
  B1+       Perception + OSRM alternatives, no reflection   (ablation, optional)

Usage:
  python tests/run_rq1_experiment.py                 # strict: aborts if Gemini or OSRM is unavailable
  python tests/run_rq1_experiment.py --runs 3        # repeat to average out LLM non-determinism
  python tests/run_rq1_experiment.py --allow-fallback --limit 5   # offline smoke run (gazetteer fallback)
"""
import argparse
import csv
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.single_agent import run_single_agent
from app.core.settings import settings
from app.services.baselines import osrm_alternatives_ablation, osrm_baseline
from app.services.llm import WAIT_S
from app.services.evaluation import evaluate_route, extraction_metrics, scenario_feasible
from app.services.workflow_service import run_langgraph_workflow

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LATENCY_TARGET_MS = 3500.0
SYSTEMS = ["B1_OSRM", "B2_SINGLE_AGENT", "PROPOSED", "B1PLUS_ABLATION"]


def run_system(system, sc, origin, destination, args):
    """Returns (route, perceived_hazards, extras) for one system on one scenario."""
    if system == "B1_OSRM":
        out = osrm_baseline(origin, destination)
        return out["current_route"], out["perceived_hazards"], {}
    if system == "B2_SINGLE_AGENT":
        out = run_single_agent(sc["user_query"], sc["news_context"], origin, destination)
        return out["current_route"], out["perceived_hazards"], {"tool_calls": out["tool_calls"]}
    if system == "PROPOSED":
        res = run_langgraph_workflow(
            sc["user_query"], sc["news_context"], origin, destination, scenario_id=sc["id"],
            max_reflections=args.max_reflections, strict_perception=not args.allow_fallback,
        )
        return res["current_route"], res["perceived_hazards"], {
            "reflections": res["reflection_count"], "perception_source": res["perception_source"],
        }
    if system == "B1PLUS_ABLATION":
        out = osrm_alternatives_ablation(
            sc["news_context"], origin, destination, strict_perception=not args.allow_fallback
        )
        return out["current_route"], out["perceived_hazards"], {"perception_source": out["perception_source"]}
    raise ValueError(system)


def preflight(args):
    """Refuses to benchmark against a silently degraded stack."""
    from tests.smoke_check import check_gemini, check_osrm  # noqa: WPS433

    ok = check_osrm()
    if not args.allow_fallback:
        ok = check_gemini() and ok
    if not ok:
        sys.exit("Preflight failed. Fix the service above, or pass --allow-fallback for an offline smoke run.")


def summarize(rows, runs):
    summary = {}
    for system in sorted({r["system"] for r in rows}):
        rs = [r for r in rows if r["system"] == system]
        ok = [r for r in rs if not r["error"]]

        def rate(subset):
            return sum(1 for r in subset if r["judge_safe"]) / len(subset) * 100.0 if subset else None

        per_run = [rate([r for r in rs if r["run"] == k]) for k in range(1, runs + 1)]
        per_run = [x for x in per_run if x is not None]
        lat = [r["latency_ms"] for r in ok]
        overhead = [r["overhead_km"] for r in ok if r["overhead_km"] is not None]
        entry = {
            "n_rows": len(rs),
            "errors": len(rs) - len(ok),
            "avoidance_rate_pct_all": rate(rs),
            "avoidance_rate_pct_feasible": rate([r for r in rs if r["feasible"]]),
            "avoidance_rate_pct_sd_across_runs": statistics.pstdev(per_run) if len(per_run) > 1 else 0.0,
            "mean_overhead_km": statistics.mean(overhead) if overhead else None,
            "mean_latency_ms": statistics.mean(lat) if lat else None,
            "p95_latency_ms": sorted(lat)[int(0.95 * (len(lat) - 1))] if lat else None,
            "pct_under_latency_target": sum(1 for x in lat if x < LATENCY_TARGET_MS) / len(lat) * 100.0 if lat else None,
            "mean_reflections": statistics.mean(r["reflections"] for r in ok) if ok and system == "PROPOSED" else None,
        }
        for k in ("extraction_precision", "extraction_recall", "grounding_accuracy"):
            vals = [r[k] for r in ok if r[k] is not None]
            entry[k] = statistics.mean(vals) if vals else None
        sources = {r["perception_source"] for r in ok if r["perception_source"]}
        entry["perception_sources"] = sorted(sources)
        summary[system] = entry
    return summary


def fmt(v, spec=".1f"):
    return "-" if v is None else format(v, spec)


def print_summary(summary, n_scen, n_feasible, runs):
    print("\n" + "=" * 100)
    print(f"RQ1 SUMMARY  |  {n_scen} scenarios ({n_feasible} feasible), {runs} run(s)")
    print("=" * 100)
    print(f"{'System':<18}{'Avoid% all':>11}{'Avoid% feas':>12}{'SD runs':>9}{'Overhead km':>13}{'Lat ms':>9}{'p95 ms':>9}"
          f"{'<3.5s %':>9}{'Extr R':>8}{'Ground':>8}{'Err':>5}")
    for name, s in summary.items():
        print(f"{name:<18}{fmt(s['avoidance_rate_pct_all']):>11}{fmt(s['avoidance_rate_pct_feasible']):>12}"
              f"{fmt(s['avoidance_rate_pct_sd_across_runs']):>9}{fmt(s['mean_overhead_km'], '.2f'):>13}"
              f"{fmt(s['mean_latency_ms'], '.0f'):>9}{fmt(s['p95_latency_ms'], '.0f'):>9}"
              f"{fmt(s['pct_under_latency_target']):>9}{fmt(s['extraction_recall'], '.2f'):>8}"
              f"{fmt(s['grounding_accuracy'], '.2f'):>8}{s['errors']:>5}")
    print("Perception source per system:", {k: v["perception_sources"] for k, v in summary.items() if v["perception_sources"]})
    print("=" * 100)


def run_rq1_benchmark(args):
    with open(args.scenarios, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    if args.limit:
        scenarios = scenarios[: args.limit]
    if args.systems:
        systems = [s.strip().upper() for s in args.systems.split(",") if s.strip()]
        unknown = [s for s in systems if s not in SYSTEMS]
        if unknown:
            sys.exit(f"Unknown system(s): {', '.join(unknown)}. Choose from: {', '.join(SYSTEMS)}")
    else:
        systems = [s for s in SYSTEMS if args.ablation or s != "B1PLUS_ABLATION"]

    settings.OSRM_CACHE_ENABLED = args.use_cache  # cached OSRM replies would make latency meaningless
    preflight(args)

    rows = []
    aborted = False
    for run in range(1, args.runs + 1):
        if aborted:
            break
        for sc in scenarios:
            if aborted:
                break
            origin = [sc["origin"]["lat"], sc["origin"]["lon"]]
            destination = [sc["destination"]["lat"], sc["destination"]["lon"]]
            gt = sc.get("ground_truth_hazards", [])
            feasible = scenario_feasible(origin, destination, gt)
            b1_km = None
            for system in systems:
                row = {
                    "scenario_id": sc["id"], "run": run, "system": system, "feasible": feasible,
                    "judge_safe": False, "violated": "", "min_margin_m": None, "distance_km": None,
                    "overhead_km": None, "latency_ms": None, "reflections": None, "tool_calls": None,
                    "perception_source": None, "extraction_precision": None, "extraction_recall": None,
                    "grounding_accuracy": None, "error": "",
                }
                t0, wait0 = time.time(), WAIT_S["total"]
                try:
                    route, perceived, extra = run_system(system, sc, origin, destination, args)
                    # retry/backoff waits are excluded so quota hiccups do not distort latency
                    row["latency_ms"] = round(((time.time() - t0) - (WAIT_S["total"] - wait0)) * 1000.0, 1)
                    row.update({k: extra.get(k) for k in ("reflections", "tool_calls", "perception_source")})
                    if route is None:
                        row["error"] = "no route produced"
                    else:
                        verdict = evaluate_route(route["coordinates"], gt)
                        row.update(judge_safe=verdict["is_safe"], violated="|".join(verdict["violated"]),
                                   min_margin_m=verdict["min_margin_m"], distance_km=round(route["distance_m"] / 1000.0, 3))
                        if system == "B1_OSRM":
                            b1_km = row["distance_km"]
                        if b1_km is not None:
                            row["overhead_km"] = round(row["distance_km"] - b1_km, 3)
                    if system != "B1_OSRM":
                        row.update(extraction_metrics(perceived, gt))
                except Exception as e:  # a failed run is recorded, never silently dropped
                    row["latency_ms"] = round(((time.time() - t0) - (WAIT_S["total"] - wait0)) * 1000.0, 1)
                    row["error"] = f"{type(e).__name__}: {e}"[:300]
                rows.append(row)
                if "PerDay" in row["error"]:
                    aborted = True
                    break
            print(f"run {run} scenario #{sc['id']:02d} done" + ("" if feasible else "  (infeasible: endpoint inside a hazard zone)"))

    if aborted:
        print("\n!! ABORTED: Gemini daily request quota is exhausted (free tier allows ~20 requests/day/model). "
              "Partial results below are NOT a complete benchmark. Enable billing or wait for the quota reset.")
    out_csv = os.path.abspath(args.out)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    n_feasible = sum(1 for sc in scenarios if scenario_feasible(
        [sc["origin"]["lat"], sc["origin"]["lon"]], [sc["destination"]["lat"], sc["destination"]["lon"]],
        sc.get("ground_truth_hazards", [])))
    summary = summarize(rows, args.runs)
    summary_path = os.path.splitext(out_csv)[0] + "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"scenarios": len(scenarios), "feasible_scenarios": n_feasible, "runs": args.runs,
                   "max_reflections": args.max_reflections, "gemini_model": settings.GEMINI_MODEL,
                   "osrm_server": settings.OSRM_SERVER_URL, "strict_perception": not args.allow_fallback,
                   "systems": summary}, f, indent=2, ensure_ascii=False)
    print_summary(summary, len(scenarios), n_feasible, args.runs)
    print(f"\nPer-row results: {out_csv}\nSummary:         {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", default=os.path.join(ROOT, "data", "scenarios.json"))
    parser.add_argument("--out", default=os.path.join(ROOT, "data", "results_rq1.csv"))
    parser.add_argument("--runs", type=int, default=1, help="repeat the benchmark to average LLM non-determinism")
    parser.add_argument("--max-reflections", type=int, default=settings.DEFAULT_MAX_REFLECTIONS)
    parser.add_argument("--limit", type=int, default=0, help="only the first N scenarios")
    parser.add_argument("--allow-fallback", action="store_true", help="permit gazetteer fallback when Gemini is unavailable")
    parser.add_argument("--no-ablation", dest="ablation", action="store_false", help="skip the B1+ ablation")
    parser.add_argument("--systems", default="",
                        help="comma-separated subset to run, e.g. B1_OSRM,PROPOSED. Repeat runs for variance only "
                             "need the systems under test; every Gemini-backed system costs daily quota. "
                             "Keep B1_OSRM in the subset, it is free and supplies the overhead_km reference.")
    parser.add_argument("--use-cache", action="store_true", help="keep the OSRM response cache on (distorts latency)")
    run_rq1_benchmark(parser.parse_args())
