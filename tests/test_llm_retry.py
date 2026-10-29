import pytest

from app.services import llm
from app.services.llm import LLMDailyQuotaExhausted, invoke_with_retry


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm, "MIN_INTERVAL_S", 0.0)


def test_retries_transient_overload_then_succeeds():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("503 UNAVAILABLE high demand")
        return "ok"

    assert invoke_with_retry(flaky) == "ok" and len(calls) == 3


def test_daily_quota_fails_fast_without_retrying():
    calls = []

    def spent():
        calls.append(1)
        raise RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    with pytest.raises(LLMDailyQuotaExhausted):
        invoke_with_retry(spent)
    assert len(calls) == 1


def test_non_transient_errors_are_not_retried():
    calls = []

    def bad():
        calls.append(1)
        raise ValueError("schema mismatch")

    with pytest.raises(ValueError):
        invoke_with_retry(bad)
    assert len(calls) == 1


def test_throttle_spaces_calls_and_counts_the_wait(monkeypatch):
    slept = []
    monkeypatch.setattr(llm, "MIN_INTERVAL_S", 4.0)
    monkeypatch.setattr(llm.time, "sleep", slept.append)
    monkeypatch.setattr(llm.time, "monotonic", lambda: 100.0)
    llm._last_call["t"] = 99.0
    before = llm.WAIT_S["total"]
    invoke_with_retry(lambda: "ok")
    assert slept == [3.0] and llm.WAIT_S["total"] - before == 3.0
