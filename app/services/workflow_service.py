import time
from typing import Dict, Any, List
from app.models.state import AgentState
from app.agents.perception import traffic_perception_agent
from app.agents.reasoning import route_reasoning_agent
from app.agents.reflector import reflector_agent

def run_langgraph_workflow(
    user_query: str,
    news_context: str,
    origin: List[float],
    destination: List[float],
    scenario_id: int = None,
    max_reflections: int = 2,
    enable_reflection: bool = True
) -> AgentState:
    """
    Executes the Multi-Agent LangGraph StateGraph Workflow.
    If enable_reflection is False (Single-Agent Baseline 2), runs 1-pass without reflection loops.
    """
    start_time = time.time()
    
    state: AgentState = {
        "scenario_id": scenario_id,
        "user_query": user_query,
        "news_context": news_context,
        "origin": origin,
        "destination": destination,
        "perceived_hazards": [],
        "avoid_points": [],
        "current_route": None,
        "reflection_count": 0,
        "max_reflections": max_reflections if enable_reflection else 0,
        "is_safe": False,
        "violations": [],
        "waypoints": [],
        "logs": [],
        "extraction_accuracy": 1.0
    }
    
    # Node 1: Perception Agent
    state = traffic_perception_agent(state)
    
    # StateGraph execution loop
    while True:
        # Node 2: Reasoning Agent
        state = route_reasoning_agent(state)
        
        # Node 3: Reflector Agent
        state = reflector_agent(state)
        
        if not enable_reflection:
            break
            
        if state["is_safe"] or state["reflection_count"] > state["max_reflections"]:
            break
            
    elapsed_ms = (time.time() - start_time) * 1000.0
    state["logs"].append(f"\n[Execution Summary] Total Latency: {elapsed_ms:.2f} ms | Safe: {state['is_safe']} | Reflection Loops: {state['reflection_count']}")
    return state
