from fastapi import APIRouter
from app.api.v1.endpoints import routing, scenarios

api_router = APIRouter()
api_router.include_router(routing.router, prefix="/route", tags=["Multi-Agent Routing"])
api_router.include_router(scenarios.router, prefix="/scenarios", tags=["Benchmark Scenarios"])
