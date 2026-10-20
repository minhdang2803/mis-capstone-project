#Multi-Agent Traffic Routing Backend for Flood Hazard Avoidance in Ho Chi Minh City

This repository implements the Multi-Agent Traffic Routing System proposed for Research Question 1 (RQ1) in Master's Thesis in MIS.

## Key Architecture

- **Traffic Perception Agent**: Extracts inundated street names from unstructured Vietnamese news text and geocodes them into spatial hazard zones.
- **Route Reasoning Agent**: Calls OSRM Routing Engine API with origin, destination, and detour waypoints.
- **Reflector Agent**: Performs geometric inspection of generated route polyline against hazard zones. Triggers Reflection Loop if safety constraints are violated.

## Directory Layout

- `app/main.py`: FastAPI entrypoint
- `app/agents/`: Perception, Reasoning, and Reflector Agents
- `app/services/`: OSRM, Geocoding, and LangGraph Workflow Services
- `app/api/v1/`: RESTful Endpoints
- `data/scenarios.json`: Benchmark dataset containing 20 real flood scenarios in Ho Chi Minh City
- `tests/run_rq1_experiment.py`: Benchmark evaluation script comparing 3 Baselines for RQ1

## Quick Start

```bash
pip install -r requirements.txt
python -m app.main
```

Run Benchmark Tests for RQ1:

```bash
python tests/run_rq1_experiment.py
```
# mis-capstone-project
