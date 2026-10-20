import os
import sys
import json
import csv
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.osrm_service import calculate_route_osrm
from app.services.workflow_service import run_langgraph_workflow
from app.core.geometry import haversine_distance

def run_rq1_benchmark():
    scenarios_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/scenarios.json"))
    output_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/results_rq1.csv"))
    
    with open(scenarios_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
        
    print("=" * 80)
    print("      RQ1 AUTOMATED BENCHMARK EVALUATION (20 SCENARIOS - HCMC FLOOD DATASET)")
    print("=" * 80)
    print(f"Total Scenarios Evaluated: {len(scenarios)}\n")
    
    results = []
    
    # Baseline 1 Summary Metrics
    b1_safe_count = 0
    b1_total_dist = 0.0
    b1_total_time = 0.0
    
    # Baseline 2 Summary Metrics
    b2_safe_count = 0
    b2_total_dist = 0.0
    b2_total_time = 0.0
    
    # Proposed System Summary Metrics
    prop_safe_count = 0
    prop_total_dist = 0.0
    prop_total_time = 0.0
    prop_reflections = 0
    
    for sc in scenarios:
        s_id = sc["id"]
        title = sc["title"]
        origin = [sc["origin"]["lat"], sc["origin"]["lon"]]
        destination = [sc["destination"]["lat"], sc["destination"]["lon"]]
        gt_hazards = sc.get("ground_truth_hazards", [])
        news_text = sc["news_context"]
        query = sc["user_query"]
        
        # --- BASELINE 1: Standard OSRM (No Perception, No Reflection) ---
        t0 = time.time()
        b1_route = calculate_route_osrm(origin, destination)
        b1_latency = (time.time() - t0) * 1000.0
        b1_coords = b1_route["coordinates"]
        
        # Verify safety against ground_truth_hazards
        b1_is_safe = True
        for gh in gt_hazards:
            min_d = min([haversine_distance(pt[0], pt[1], gh["lat"], gh["lon"]) for pt in b1_coords])
            if min_d < gh["radius_m"]:
                b1_is_safe = False
                break
        if b1_is_safe:
            b1_safe_count += 1
        b1_total_dist += b1_route["distance_m"] / 1000.0
        b1_total_time += b1_latency
        
        # --- BASELINE 2: Single-Agent LLM (Perception + 1-Pass Routing, No Reflection) ---
        t0 = time.time()
        b2_res = run_langgraph_workflow(query, news_text, origin, destination, scenario_id=s_id, enable_reflection=False)
        b2_latency = (time.time() - t0) * 1000.0
        if b2_res["is_safe"]:
            b2_safe_count += 1
        b2_dist = b2_res["current_route"]["distance_m"] / 1000.0 if b2_res["current_route"] else 0.0
        b2_total_dist += b2_dist
        b2_total_time += b2_latency
        
        # --- PROPOSED SYSTEM: Multi-Agent LangGraph (Perception + Reasoning + Reflector Loop) ---
        t0 = time.time()
        prop_res = run_langgraph_workflow(query, news_text, origin, destination, scenario_id=s_id, enable_reflection=True, max_reflections=2)
        prop_latency = (time.time() - t0) * 1000.0
        if prop_res["is_safe"]:
            prop_safe_count += 1
        prop_dist = prop_res["current_route"]["distance_m"] / 1000.0 if prop_res["current_route"] else 0.0
        prop_total_dist += prop_dist
        prop_total_time += prop_latency
        prop_reflections += prop_res["reflection_count"]
        
        # Record scenario row
        results.append({
            "scenario_id": s_id,
            "title": title,
            "b1_osrm_safe": b1_is_safe,
            "b1_distance_km": round(b1_route["distance_m"] / 1000.0, 2),
            "b1_latency_ms": round(b1_latency, 2),
            "b2_single_agent_safe": b2_res["is_safe"],
            "b2_distance_km": round(b2_dist, 2),
            "b2_latency_ms": round(b2_latency, 2),
            "proposed_safe": prop_res["is_safe"],
            "proposed_reflection_loops": prop_res["reflection_count"],
            "proposed_distance_km": round(prop_dist, 2),
            "proposed_latency_ms": round(prop_latency, 2)
        })
        
        print(f"Scenario #{s_id:02d}: {title[:45]}...")
        print(f"  └─ OSRM Baseline: Safe={b1_is_safe} ({b1_route['distance_m']/1000.0:.2f}km)")
        print(f"  └─ Single-Agent:  Safe={b2_res['is_safe']} ({b2_dist:.2f}km)")
        print(f"  └─ Multi-Agent:   Safe={prop_res['is_safe']} ({prop_dist:.2f}km) | Reflections={prop_res['reflection_count']}")
        print("-" * 80)
        
    # Write results CSV
    keys = results[0].keys()
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)
        
    n = len(scenarios)
    print("\n" + "=" * 80)
    print("                     BENCHMARK EXPERIMENT SUMMARY FOR RQ1")
    print("=" * 80)
    print(f"Metrics                         | Baseline 1 (OSRM) | Baseline 2 (Single-Agent) | Proposed (Multi-Agent)")
    print("-" * 80)
    print(f"Constraint Avoidance Rate (%)   | {b1_safe_count/n*100.0:17.1f}% | {b2_safe_count/n*100.0:25.1f}% | {prop_safe_count/n*100.0:22.1f}%")
    print(f"Average Distance (km)           | {b1_total_dist/n:17.2f}  | {b2_total_dist/n:25.2f}  | {prop_total_dist/n:22.2f}")
    print(f"Average System Latency (ms)     | {b1_total_time/n:17.2f}  | {b2_total_time/n:25.2f}  | {prop_total_time/n:22.2f}")
    print(f"Total Reflection Loops Triggered| {'0':17}  | {'0':25}  | {prop_reflections:22}")
    print("=" * 80)
    print(f"\n[OUTPUT CSV SAVED] Detailed results written to: {output_csv_path}\n")

if __name__ == "__main__":
    run_rq1_benchmark()
