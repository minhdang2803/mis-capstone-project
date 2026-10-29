"""
Common judge for every system in the RQ1 benchmark. All routes are scored against the same
`ground_truth_hazards`, never against a system's own perceived hazards.
"""
import re
import unicodedata
from typing import Any, Dict, List

from app.core.geometry import distance_to_polyline, haversine_distance


def normalize_name(name: str) -> str:
    """Lower-case, accent-insensitive street name without 'đường/phố/tuyến' prefixes."""
    name = name.lower().replace("đ", "d")
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = re.sub(r"^(duong|pho|tuyen)\s+", "", name.strip())
    return re.sub(r"\s+", " ", name)


def evaluate_route(coords: List[List[float]], gt_hazards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Safety of a route against ground-truth hazard zones (segment-based distance)."""
    if not coords:
        return {"is_safe": False, "violated": [h["street"] for h in gt_hazards], "min_margin_m": None}
    violated, margins = [], []
    for h in gt_hazards:
        margin = distance_to_polyline(coords, h["lat"], h["lon"])["distance_m"] - h["radius_m"]
        margins.append(margin)
        if margin < 0:
            violated.append(h["street"])
    return {
        "is_safe": not violated,
        "violated": violated,
        "min_margin_m": round(min(margins), 1) if margins else None,
    }


def scenario_feasible(origin: List[float], destination: List[float], gt_hazards: List[Dict[str, Any]]) -> bool:
    """A scenario is unwinnable when an endpoint already lies inside a ground-truth hazard zone."""
    for p in (origin, destination):
        for h in gt_hazards:
            if haversine_distance(p[0], p[1], h["lat"], h["lon"]) < h["radius_m"]:
                return False
    return True


def extraction_metrics(
    perceived: List[Dict[str, Any]], gt_hazards: List[Dict[str, Any]], tolerance_m: float = 500.0
) -> Dict[str, Any]:
    """
    Precision / recall of extracted streets versus ground truth, plus grounding accuracy: the
    share of ground-truth hazards whose street was extracted AND geocoded within tolerance_m.
    """
    gt_names = {normalize_name(h["street"]): h for h in gt_hazards}
    matched, grounded = set(), set()
    correct_predictions = 0
    for p in perceived:
        pn = normalize_name(p["street"])
        key = next((g for g in gt_names if g == pn or g in pn or pn in g), None)
        if key is None:
            continue
        correct_predictions += 1
        matched.add(key)
        gh = gt_names[key]
        if haversine_distance(p["lat"], p["lon"], gh["lat"], gh["lon"]) <= tolerance_m:
            grounded.add(key)
    n_gt, n_pred = len(gt_names), len(perceived)
    return {
        "extraction_precision": round(correct_predictions / n_pred, 3) if n_pred else (1.0 if not n_gt else 0.0),
        "extraction_recall": round(len(matched) / n_gt, 3) if n_gt else 1.0,
        "grounding_accuracy": round(len(grounded) / n_gt, 3) if n_gt else 1.0,
    }
