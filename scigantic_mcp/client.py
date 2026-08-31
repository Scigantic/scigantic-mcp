"""Async HTTP client for the public Scigantic API.

Deliberately mirrors the shape of Kiro's `life-sciences-common` base
(async httpx client, exponential backoff on 429/5xx/timeout, a small error
taxonomy) so this connector can either run standalone (self-serve install) or
be adapted to inherit `BaseLifeSciencesServer` for the aws-samples monorepo.

Only public, unauthenticated, read-only endpoints are used here.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import httpx

from . import __version__

DEFAULT_BASE_URL = "https://api.scigantic.com"
# The API derives its (default) tenant from the request Origin; pinning it to
# scigantic.com keeps this connector on the main public catalog.
DEFAULT_ORIGIN = "https://scigantic.com"
# Built from the installed package's own __version__ (same source server.py's
# serverInfo.version reads) so this can't silently drift out of date the way
# the old hardcoded "0.1" literal did once the package moved past 0.1.x.
USER_AGENT = f"scigantic-mcp/{__version__} (+https://scigantic.com)"

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ScigateApiError(Exception):
    """Base class for Scigantic API errors."""


class RateLimitError(ScigateApiError):
    """429 Too Many Requests after retries were exhausted."""


class AuthenticationError(ScigateApiError):
    """401/403 — should not happen on public endpoints, surfaced for clarity."""


class NotFoundError(ScigateApiError):
    """404 — archive/paper/resource does not exist."""


class ScigateClient:
    """Thin retrying JSON client over the public Scigantic REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        origin: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 3,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("SCIGANTIC_API_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.origin = origin or os.environ.get("SCIGANTIC_API_ORIGIN") or DEFAULT_ORIGIN
        self.max_retries = max_retries
        self._timeout = timeout
        # Allow an injected client (tests use httpx.MockTransport); otherwise lazily build one.
        self._client = http_client
        self._owns_client = http_client is None

    def _headers(self) -> Dict[str, str]:
        return {"Origin": self.origin, "User-Agent": USER_AGENT, "Accept": "application/json"}

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        client = await self._ensure_client()
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await client.request(method, path, headers=self._headers(), **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise ScigateApiError(f"{method} {path} failed: {exc}") from exc

            if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                await asyncio.sleep(self._backoff(attempt))
                continue

            return self._handle_response(method, path, resp)

        # Only reached if every attempt raised a transport error.
        raise ScigateApiError(f"{method} {path} failed after retries: {last_exc}")

    @staticmethod
    def _backoff(attempt: int) -> float:
        # 0.5s, 1s, 2s — capped exponential backoff.
        # 2.0 (not 2) as the base: typeshed types int.__pow__ as returning Any
        # for a non-literal exponent (an int ** int can be int or float
        # depending on sign), which otherwise infects this whole expression.
        return min(0.5 * (2.0 ** attempt), 4.0)

    @staticmethod
    def _handle_response(method: str, path: str, resp: httpx.Response) -> Any:
        status = resp.status_code
        if status == 404:
            raise NotFoundError(f"{path} not found")
        if status in (401, 403):
            raise AuthenticationError(f"{path} requires authentication ({status})")
        if status == 429:
            raise RateLimitError(f"{path} rate-limited (429)")
        if status >= 400:
            raise ScigateApiError(f"{method} {path} -> HTTP {status}: {resp.text[:200]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise ScigateApiError(f"{path} returned non-JSON body") from exc

    async def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        return await self._request("GET", path, params=clean)

    async def post_json(self, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        return await self._request("POST", path, json=body or {})
