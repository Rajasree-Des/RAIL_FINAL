"""Retry with exponential backoff for network and navigation."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    retryable: tuple[type[Exception], ...] = (Exception,),
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except retryable as e:
            last_error = e
            if attempt >= max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Attempt %d/%d failed (%s), retrying in %.1fs",
                attempt,
                max_attempts,
                type(e).__name__,
                delay,
            )
            await asyncio.sleep(delay)
    raise last_error  # type: ignore[misc]
