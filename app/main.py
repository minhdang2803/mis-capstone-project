# pyrefly: ignore[missing-import]
from fastapi import FastAPI
# pyrefly: ignore[missing-import]
from fastapi.middleware.cors import CORSMiddleware
import os
from app.core.settings import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for MAS4POI Multi-Agent Traffic Routing with LangGraph StateGraph Workflow"
)

app.add_middleware(
    CORSMiddleware,
    # Comma-separated allow-list in production (e.g. CORS_ORIGINS=https://app.example.com); "*" for local dev only
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    from app.services.osrm_service import OSRMError, calculate_route_osrm
    try:
        calculate_route_osrm([10.8034, 106.7381], [10.8040, 106.7320])
        osrm = "up"
    except OSRMError:
        osrm = "down"
    return {
        "status": "online" if osrm == "up" else "degraded",
        "osrm": osrm,
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

if __name__ == "__main__":
    # pyrefly: ignore[missing-import]
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
