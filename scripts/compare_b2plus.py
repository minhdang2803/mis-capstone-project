"""
Compares the B2+ run against B2, PROPOSED and B1+ from the reported RQ1 v2 run.

B2+ was run separately (--systems B1_OSRM,B2PLUS_VERIFIER), so quality metrics are compared
across runs. That is valid because every system here is deterministic at temperature 0 and the
reported run reproduced bit-identically on repetition (results_rq1_v2_run2.csv). Latency is not:
it is only ever compared within one run.

Usage:
  python scripts/compare_b2plus.py
  python scripts/compare_b2plus.py --b2plus data/results_rq1_v2_b2plus.csv --reference data/results_rq1_v2_reflector2.csv
"""
import argparse
import csv
import os
import statistics
from collections import Counter
from math import comb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out.setdefault(r["system"], {})[int(r["scenario_id"])] = r
    return out


def safe(r):
    return r["judge_safe"] == "True" and not r["error"]


def binom_two_sided(x, y):
    """Exact two-sided binomial p for x vs y discordant outcomes under p = 0.5."""
    n = x + y
    return min(1.0, 2 * sum(comb(n, j) for j in range(min(x, y) + 1)) / 2 ** n) if n else 1.0


def mcnemar_exact(a, b, ids):
    """Two-sided exact McNemar (binomial on discordant pairs), as reported in Chapter 5."""
    only_a = sum(1 for i in ids if safe(a[i]) and not safe(b[i]))
    only_b = sum(1 for i in ids if safe(b[i]) and not safe(a[i]))
    return only_a, only_b, binom_two_sided(only_a, only_b)


def sign_test(diffs):
    """Two-sided exact sign test on paired differences; ties are dropped."""
    pos, neg = sum(1 for d in diffs if d > 0), sum(1 for d in diffs if d < 0)
    return pos, neg, binom_two_sided(pos, neg)


def rate(rows, ids):
    return sum(1 for i in ids if safe(rows[i])) / len(ids) * 100 if ids else float("nan")


def mean_overhead(rows, ids):
    vals = [float(rows[i]["overhead_km"]) for i in ids if rows[i]["overhead_km"]]
    return statistics.mean(vals) if vals else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--b2plus", default=os.path.join(ROOT, "data", "results_rq1_v2_b2plus.csv"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "data", "results_rq1_v2_reflector2.csv"))
    args = ap.parse_args()

    new, ref = load(args.b2plus), load(args.reference)
    b2p, b2, prop, b1p = new["B2PLUS_VERIFIER"], ref["B2_SINGLE_AGENT"], ref["PROPOSED"], ref["B1PLUS_ABLATION"]
    ids = sorted(b2p)
    errors = [i for i in ids if b2p[i]["error"]]
    print(f"B2+ rows: {len(ids)} scenarios, {len(errors)} error(s) {errors if errors else ''}")

    # Sanity: OSRM is deterministic, so B1 must route identically in both runs
    b1_new, b1_ref = new["B1_OSRM"], ref["B1_OSRM"]
    drift = [i for i in ids if b1_new[i]["distance_km"] != b1_ref[i]["distance_km"]]
    print(f"B1 distance identical across runs: {len(ids) - len(drift)}/{len(ids)}" + (f"  drift: {drift}" if drift else ""))

    print("\n== Avoidance rate (judge: ground truth) ==")
    for name, rows in (("B2", b2), ("B2+", b2p), ("B1+", b1p), ("PROPOSED", prop)):
        n_safe = sum(1 for i in ids if safe(rows[i]))
        print(f"  {name:<9}{n_safe:>3}/{len(ids)}  {rate(rows, ids):5.1f}%")

    print("\n== Exact McNemar (only-first / only-second, p) ==")
    for la, a, lb, b in (("PROPOSED", prop, "B2+", b2p), ("B2+", b2p, "B2", b2), ("B2+", b2p, "B1+", b1p)):
        x, y, p = mcnemar_exact(a, b, ids)
        print(f"  {la} vs {lb}: {x}/{y}  p = {p:.2e}")

    print("\n== Extraction (B2+ vs B2: same geocoding path, different prompt) ==")
    for name, rows in (("B2", b2), ("B2+", b2p), ("PROPOSED", prop)):
        vals = {k: [float(rows[i][k]) for i in ids if rows[i][k]] for k in
                ("extraction_precision", "extraction_recall", "grounding_accuracy")}
        print(f"  {name:<9}P {statistics.mean(vals['extraction_precision']):.3f}  "
              f"R {statistics.mean(vals['extraction_recall']):.3f}  "
              f"G {statistics.mean(vals['grounding_accuracy']):.3f}  "
              f"(recall < 1 in {sum(1 for v in vals['extraction_recall'] if v < 1)} scenarios)")

    # Separates "had no verifier" from "extracted worse": on scenarios where B2+ found every
    # hazard, any remaining gap to PROPOSED is about repairing the route, not perceiving hazards
    full = [i for i in ids if b2p[i]["extraction_recall"] and float(b2p[i]["extraction_recall"]) == 1.0]
    print(f"\n== Conditioned on B2+ recall = 1 ({len(full)} scenarios) ==")
    print(f"  B2+ {rate(b2p, full):5.1f}%   PROPOSED {rate(prop, full):5.1f}%")
    x, y, p = mcnemar_exact(prop, b2p, full)
    print(f"  PROPOSED vs B2+ on this subset: {x}/{y}  p = {p:.2e}")

    print("\n== B2+ failures by cause ==")
    fails = [i for i in ids if not safe(b2p[i])]
    missed = [i for i in fails if b2p[i]["extraction_recall"] and float(b2p[i]["extraction_recall"]) < 1.0]
    unrepaired = [i for i in fails if i not in missed and not b2p[i]["error"]]
    print(f"  perception missed a hazard (recall < 1): {len(missed)}  {missed}")
    print(f"  saw every hazard, could not route around: {len(unrepaired)}  {unrepaired}")
    print(f"  errors: {len(errors)}  {errors}")
    same_as_b1 = [i for i in unrepaired if b2p[i]["distance_km"] == b1_new[i]["distance_km"]]
    print(f"    of which returned OSRM's shortest route unchanged: {len(same_as_b1)}  {same_as_b1}")

    print("\n== Scenario-level agreement ==")
    for label, cond in (
        ("B2+ solves, B2 does not", lambda i: safe(b2p[i]) and not safe(b2[i])),
        ("B2 solves, B2+ does not", lambda i: safe(b2[i]) and not safe(b2p[i])),
        ("B2+ solves, PROPOSED does not", lambda i: safe(b2p[i]) and not safe(prop[i])),
        ("PROPOSED solves, B2+ does not", lambda i: safe(prop[i]) and not safe(b2p[i])),
    ):
        hit = [i for i in ids if cond(i)]
        print(f"  {label:<31}{len(hit):>3}  {hit}")

    # Averaging over all 42 is not comparable across systems with different avoidance rates
    # (Section 5.1), so detour length is compared on scenarios both systems solved
    both = [i for i in ids if safe(b2p[i]) and safe(prop[i])]
    print(f"\n== Detour on scenarios both B2+ and PROPOSED solved ({len(both)}) ==")
    print(f"  B2+ {mean_overhead(b2p, both):.2f} km   PROPOSED {mean_overhead(prop, both):.2f} km   (means)")
    print(f"  B2+ {statistics.median(float(b2p[i]['overhead_km']) for i in both):.2f} km   "
          f"PROPOSED {statistics.median(float(prop[i]['overhead_km']) for i in both):.2f} km   (medians)")
    longer, shorter, p = sign_test([float(b2p[i]["overhead_km"]) - float(prop[i]["overhead_km"]) for i in both])
    print(f"  B2+ longer in {longer}, shorter in {shorter}; sign test p = {p:.2e}")
    print(f"  B2+ detours over 3 km: {[(i, float(b2p[i]['overhead_km'])) for i in both if float(b2p[i]['overhead_km']) > 3]}")

    tc = [int(b2p[i]["tool_calls"]) for i in ids if b2p[i]["tool_calls"]]
    print("\n== B2+ effort ==")
    print(f"  tool calls: mean {statistics.mean(tc):.1f}, median {statistics.median(tc)}, max {max(tc)}"
          f"  (B2 in the reference run: mean "
          f"{statistics.mean(int(b2[i]['tool_calls']) for i in ids if b2[i]['tool_calls']):.1f})")
    print(f"  tool-call distribution: {sorted(Counter(tc).items())}")

    # tool_calls >= the step budget suggests (not proves: one turn can call several tools) that a
    # run was cut off. Worst case for PROPOSED: every such B2+ failure would have succeeded.
    capped = [i for i in ids if b2p[i]["tool_calls"] and int(b2p[i]["tool_calls"]) >= 12]
    capped_fail = [i for i in capped if not safe(b2p[i])]
    print(f"  >= 12 tool calls (may have hit the 12-step budget): {capped}, of which failed: {capped_fail}")
    x, y, _ = mcnemar_exact(prop, b2p, ids)
    flip = sum(1 for i in capped_fail if safe(prop[i]))
    p = binom_two_sided(x - flip, y)
    print(f"  sensitivity, if those failures had succeeded: B2+ {sum(1 for i in ids if safe(b2p[i])) + len(capped_fail)}/{len(ids)}, "
          f"PROPOSED vs B2+ {x - flip}/{y}  p = {p:.2e}")
    lat = sorted(float(b2p[i]["latency_ms"]) for i in ids if not b2p[i]["error"])
    print(f"  latency (this run only, not comparable to other runs): median {statistics.median(lat):.0f} ms, "
          f"mean {statistics.mean(lat):.0f} ms, under 3.5 s {sum(1 for x in lat if x < 3500) / len(lat) * 100:.1f}%")


if __name__ == "__main__":
    main()
