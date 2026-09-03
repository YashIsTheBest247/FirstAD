"""Tests for retry classification and backoff.

Both behaviours here were written after real runs failed. A 503 killed a
three-minute run because only rate limits were retried, and a 429 exhausted all
four attempts in 28 seconds while the API was asking for 42.
"""

from __future__ import annotations

import pytest

from app.core.adk_runtime import _is_transient, server_retry_delay


class _Err(Exception):
    pass


@pytest.mark.parametrize(
    "message",
    [
        "503 UNAVAILABLE. This model is currently experiencing high demand.",
        "429 RESOURCE_EXHAUSTED. You exceeded your current quota",
        "500 internal error",
        "502 Bad Gateway",
        "504 DEADLINE_EXCEEDED",
        "connection reset by peer",
        "request timeout",
        "The service is overloaded",
    ],
)
def test_transient_failures_are_retried(message: str) -> None:
    assert _is_transient(_Err(message)) is True


@pytest.mark.parametrize(
    "message",
    [
        "400 INVALID_ARGUMENT: schema mismatch",
        "403 PERMISSION_DENIED: API key not valid",
        "404 NOT_FOUND: model does not exist",
        "the prompt was blocked by a safety filter",
    ],
)
def test_real_errors_fail_fast(message: str) -> None:
    """Burning four attempts on a malformed request is just slow failure."""
    assert _is_transient(_Err(message)) is False


def test_server_retry_delay_is_read_from_the_error() -> None:
    """The API says how long to wait; guessing instead is what broke a run."""
    exc = _Err("429 RESOURCE_EXHAUSTED {'quotaId': 'x', 'retryDelay': '42s'}")
    assert server_retry_delay(exc) == 42.0


def test_server_retry_delay_handles_json_quoting_and_decimals() -> None:
    assert server_retry_delay(_Err('"retryDelay": "7.5s"')) == 7.5
    assert server_retry_delay(_Err('retryDelay:30s')) == 30.0


def test_server_retry_delay_is_none_when_not_offered() -> None:
    assert server_retry_delay(_Err("503 UNAVAILABLE, no hint given")) is None
    assert server_retry_delay(_Err("")) is None
