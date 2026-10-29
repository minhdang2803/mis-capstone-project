import os
import time
from typing import Any, Callable

# Seconds spent waiting on retries; the benchmark subtracts this so quota/backoff waits do not
# inflate the measured system latency.
WAIT_S = {"total": 0.0}

# Client-side pacing for per-minute quotas (e.g. 15 requests/min -> one call every 4 s)
MIN_INTERVAL_S = float(os.getenv("GEMINI_MIN_INTERVAL_S", "4.5"))
_last_call = {"t": 0.0}


def _throttle() -> None:
    gap = MIN_INTERVAL_S - (time.monotonic() - _last_call["t"])
    if gap > 0:
        WAIT_S["total"] += gap
        time.sleep(gap)
    _last_call["t"] = time.monotonic()

TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL", "timed out", "Timeout")
DAILY_QUOTA_MARKER = "PerDay"  # e.g. GenerateRequestsPerDayPerProjectPerModel-FreeTier


class LLMDailyQuotaExhausted(RuntimeError):
    """Raised when the daily request quota is spent: retrying cannot help for hours."""


def invoke_with_retry(fn: Callable[..., Any], *args, retries: int = 4, base_delay_s: float = 2.0, **kwargs) -> Any:
    """
    Calls `fn`, retrying transient Gemini errors (overload 503, per-minute 429) with exponential backoff.
    A daily-quota 429 fails immediately with LLMDailyQuotaExhausted.
    """
    for attempt in range(retries + 1):
        _throttle()
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if DAILY_QUOTA_MARKER in msg:
                raise LLMDailyQuotaExhausted(msg) from e
            if attempt == retries or not any(m in msg for m in TRANSIENT_MARKERS):
                raise
            delay = base_delay_s * (2 ** attempt)
            WAIT_S["total"] += delay
            time.sleep(delay)
