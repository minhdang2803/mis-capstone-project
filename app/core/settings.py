import os
from dotenv import load_dotenv

load_dotenv()

class AppSettings:
    PROJECT_NAME: str = "Final Project Traffic Routing"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    OSRM_SERVER_URL: str = os.getenv("OSRM_SERVER_URL", "https://router.project-osrm.org")
    DEFAULT_HAZARD_RADIUS_M: float = 350.0
    DEFAULT_MAX_REFLECTIONS: int = 2
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

settings = AppSettings()

