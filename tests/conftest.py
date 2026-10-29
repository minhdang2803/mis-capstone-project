import pytest

from app.services import llm


@pytest.fixture(autouse=True)
def no_llm_throttle(monkeypatch):
    """Unit tests never wait on the Gemini pacing interval."""
    monkeypatch.setattr(llm, "MIN_INTERVAL_S", 0.0)
