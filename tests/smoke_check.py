"""
Preflight check: verifies the real services are reachable so a benchmark never
silently falls back to the gazetteer or a simulated router.
Usage: python tests/smoke_check.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.settings import settings
from app.services.llm import invoke_with_retry
from app.services.osrm_service import OSRMError, calculate_route_osrm, snap_to_road


def check_osrm() -> bool:
    try:
        route = calculate_route_osrm([10.8034, 106.7381], [10.8040, 106.7320])
        snap = snap_to_road([10.8041, 106.7352])
        print(f"[OK] OSRM {settings.OSRM_SERVER_URL}: {route['distance_m']} m, "
              f"{len(route['coordinates'])} vertices, snap {snap['snap_distance_m']} m")
        return True
    except OSRMError as e:
        print(f"[FAIL] OSRM: {e}\n       Start it with: docker compose up -d osrm")
        return False


def check_gemini() -> bool:
    if not settings.GOOGLE_API_KEY:
        print("[FAIL] Gemini: GOOGLE_API_KEY / GEMINI_API_KEY is not set")
        return False
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL, google_api_key=settings.GOOGLE_API_KEY, max_retries=0
        )
        reply = invoke_with_retry(model.invoke, "Reply with the single word: ok", retries=5)
        print(f"[OK] Gemini {settings.GEMINI_MODEL}: {str(reply.content).strip()[:40]!r}")
        return True
    except Exception as e:
        print(f"[FAIL] Gemini: {e}")
        return False


if __name__ == "__main__":
    results = [check_osrm(), check_gemini()]
    sys.exit(0 if all(results) else 1)
