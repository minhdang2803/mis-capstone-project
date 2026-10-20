# pyrefly: ignore[missing-import]
from fastapi import FastAPI
# pyrefly: ignore[missing-import]
from fastapi.middleware.cors import CORSMiddleware
from app.core.settings import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for MAS4POI Multi-Agent Traffic Routing with LangGraph StateGraph Workflow"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

if __name__ == "__main__":
    # pyrefly: ignore[missing-import]
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
