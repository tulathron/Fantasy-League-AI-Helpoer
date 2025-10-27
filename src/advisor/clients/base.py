"""Shared HTTP client utilities."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential


_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class HttpClientFactory:
    """Factory responsible for creating shared :class:`httpx.AsyncClient` instances."""

    def __init__(self, timeout: Optional[httpx.Timeout] = None) -> None:
        self._timeout = timeout or _DEFAULT_TIMEOUT

    @asynccontextmanager
    async def client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            yield client


async def robust_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> httpx.Response:
    """Issue a GET request with sensible retries."""

    async for attempt in AsyncRetrying(
        wait=wait_exponential(multiplier=0.6, min=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    ):
        with attempt:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response


__all__ = ["HttpClientFactory", "robust_get"]
