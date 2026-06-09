"""Resilient external-call wrapper (architecture rule 3).

`resilient_call` retries a callable with exponential backoff and, on final
failure, returns a caller-supplied ``default`` instead of raising — so one bad
external response can never crash an ingestion cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger

log = get_logger("clients.resilient")

T = TypeVar("T")


class ExternalServiceError(Exception):
    """Raised by Real clients when an upstream API call ultimately fails."""


def resilient_call(
    fn: Callable[[], T],
    *,
    default: T,
    attempts: int = 3,
    op: str = "external_call",
) -> T:
    """Call ``fn`` with retry/backoff; return ``default`` if all attempts fail.

    The retry loop only retries :class:`ExternalServiceError` (transient upstream
    failures). Anything else propagates immediately (programming errors must surface).
    """

    @retry(
        retry=retry_if_exception_type(ExternalServiceError),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(attempts),
        reraise=True,
    )
    def _run() -> T:
        return fn()

    try:
        return _run()
    except ExternalServiceError as exc:
        log.warning("external_call_degraded", op=op, error=type(exc).__name__)
        return default
