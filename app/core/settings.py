import os
from dotenv import load_dotenv

load_dotenv()

class AppSettings:
    PROJECT_NAME: str = "Final Project Traffic Routing"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    # Local Docker OSRM by default (see docker-compose.yml); the public demo server is not for heavy use
    OSRM_SERVER_URL: str = os.getenv("OSRM_SERVER_URL", "http://localhost:5001")
    OSRM_TIMEOUT_S: float = float(os.getenv("OSRM_TIMEOUT_S", "10"))
    OSRM_CACHE_ENABLED: bool = os.getenv("OSRM_CACHE_ENABLED", "true").lower() == "true"
    ROUTE_CACHE_DIR: str = os.getenv("ROUTE_CACHE_DIR", ".route_cache")
    DEFAULT_HAZARD_RADIUS_M: float = 350.0
    DEFAULT_MAX_REFLECTIONS: int = 2
    # Reflector: how far beyond a hazard's radius the detour waypoint is placed, and the
    # farthest the waypoint may sit from the road network before it is rejected
    DETOUR_MARGIN_M: float = float(os.getenv("DETOUR_MARGIN_M", "120"))
    MAX_SNAP_DISTANCE_M: float = float(os.getenv("MAX_SNAP_DISTANCE_M", "200"))
    # Reflector ring search: candidate waypoints sit on DETOUR_RING_OFFSETS_M rings around a
    # violated hazard, DETOUR_BEARINGS of them per ring. Fixed before the benchmark so the
    # numbers are not tuned on the scenario set.
    DETOUR_BEARINGS: int = int(os.getenv("DETOUR_BEARINGS", "16"))
    DETOUR_RING_OFFSETS_M: tuple = (150.0, 300.0, 600.0, 1000.0)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

settings = AppSettings()

