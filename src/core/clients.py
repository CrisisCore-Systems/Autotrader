"""HTTP clients for external data providers used by the scanner."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Sequence

import httpx

if TYPE_CHECKING:  # pragma: no cover - import for type checkers only
    from feedparser import FeedParserDict


from src.core.http_manager import CachePolicy, RateAwareRequester, build_cache_backend
from src.core.rate_limit import RateLimit


DEFAULT_RATE_LIMITS: Mapping[str, RateLimit] = {
    "api.coingecko.com": RateLimit(30, 60.0),
    "api.llama.fi": RateLimit(60, 60.0),
    "api.etherscan.io": RateLimit(5, 1.0),
    "api.github.com": RateLimit(4500, 3600.0),
    "news.google.com": RateLimit(60, 60.0),
}
DEFAULT_RATE_LIMIT = RateLimit(120, 60.0)


class BaseClient:
    """Shared convenience helpers for HTTP clients."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client
        self._owns_client = client is None
    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        *,
        rate_limits: Mapping[str, RateLimit] | None = None,
        cache_config: Mapping[str, object] | None = None,
        requester: RateAwareRequester | None = None,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._requester = requester
        self._rate_limits = rate_limits
        self._cache_config = cache_config

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError("HTTP client has not been initialised")
        return self._client

    @property
    def requester(self) -> RateAwareRequester:
        if self._requester is None:
            if self._client is None:
                raise RuntimeError("HTTP client has not been initialised")
            cache_backend = build_cache_backend(self._cache_config)
            limits = self._rate_limits or DEFAULT_RATE_LIMITS
            self._requester = RateAwareRequester(
                self._client,
                rate_limits=limits,
                default_limit=DEFAULT_RATE_LIMIT,
                cache_backend=cache_backend,
            )
        return self._requester

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()

    def __enter__(self) -> "BaseClient":  # pragma: no cover - context manager sugar
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - context manager sugar
        self.close()


class CoinGeckoClient(BaseClient):
    """Client for the CoinGecko market data API."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.coingecko.com/api/v3",
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(base_url=base_url, timeout=timeout)
        super().__init__(session)

    def fetch_market_chart(self, token_id: str, *, vs_currency: str = "usd", days: int = 14) -> Dict[str, Any]:
        response = self.client.get(
            f"/coins/{token_id}/market_chart",
            params={"vs_currency": vs_currency, "days": days},
        )
        response.raise_for_status()
        super().__init__(session, rate_limits={"api.coingecko.com": RateLimit(30, 60.0)})

    def fetch_market_chart(self, token_id: str, *, vs_currency: str = "usd", days: int = 14) -> Dict[str, Any]:
        response = self.requester.request(
            "GET",
            f"/coins/{token_id}/market_chart",
            params={"vs_currency": vs_currency, "days": days},
            cache_policy=CachePolicy(ttl_seconds=300.0),
        )
        return response.json()


class DefiLlamaClient(BaseClient):
    """Client for DefiLlama protocol metrics."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.llama.fi",
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(base_url=base_url, timeout=timeout)
        super().__init__(session)

    def fetch_protocol(self, slug: str) -> Dict[str, Any]:
        response = self.client.get(f"/protocol/{slug}")
        response.raise_for_status()
        super().__init__(session, rate_limits={"api.llama.fi": RateLimit(60, 60.0)})

    def fetch_protocol(self, slug: str) -> Dict[str, Any]:
        response = self.requester.request(
            "GET",
            f"/protocol/{slug}",
            cache_policy=CachePolicy(ttl_seconds=600.0),
        )
        return response.json()


class EtherscanClient(BaseClient):
    """Client for retrieving contract metadata from Etherscan."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.etherscan.io/api",
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(base_url=base_url, timeout=timeout)
        super().__init__(session)
        self._api_key = api_key or ""

    def fetch_contract_source(self, address: str) -> Dict[str, Any]:
        response = self.client.get(
        super().__init__(
            session,
            rate_limits={"api.etherscan.io": RateLimit(5, 1.0)},
        )
        self._api_key = api_key or ""

    def fetch_contract_source(self, address: str) -> Dict[str, Any]:
        response = self.requester.request(
            "GET",
            "",
            params={
                "module": "contract",
                "action": "getsourcecode",
                "address": address,
                "apikey": self._api_key,
            },
        )
        response.raise_for_status()
            cache_policy=CachePolicy(ttl_seconds=3600.0),
        )
        payload = response.json()
        if payload.get("status") != "1":
            raise RuntimeError(f"Etherscan error: {payload.get('message', 'unknown error')}")
        results = payload.get("result", [])
        return results[0] if results else {}


class NewsFeedClient(BaseClient):
    """Client for retrieving RSS/Atom feeds used for narrative signals."""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(timeout=timeout)
        super().__init__(session)

    def fetch_feed(self, url: str) -> "FeedParserDict":
        """Return the parsed feed for ``url``.

        The client intentionally relies on :mod:`feedparser` to normalise
        responses into a consistent structure regardless of whether the
        upstream publishes RSS or Atom documents.
        """

        response = self.requester.request("GET", url, cache_policy=CachePolicy(ttl_seconds=300.0))
        try:
            import feedparser
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("feedparser is required for NewsFeedClient") from exc

        return feedparser.parse(response.content)


class SocialFeedClient(BaseClient):
    """Client for retrieving social feed JSON payloads."""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(timeout=timeout)
        super().__init__(session)

    def fetch_posts(self, url: str, *, limit: int = 50) -> Sequence[Dict[str, Any]]:
        response = self.requester.request(
            "GET",
            url,
            params={"limit": limit},
            cache_policy=CachePolicy(ttl_seconds=60.0),
        )
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("data", "posts", "items"):
                if key in payload:
                    data = payload[key]
                    if isinstance(data, list):
                        return data
            return []
        if isinstance(payload, list):
            return payload
        return []


class GitHubClient(BaseClient):
    """Client for fetching GitHub repository activity."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.github.com",
        timeout: float = 15.0,
        token: str | None = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        session = client or httpx.Client(base_url=base_url, timeout=timeout, headers=headers)
        super().__init__(session, rate_limits={"api.github.com": RateLimit(4500, 3600.0)})

    def fetch_repo_events(self, owner: str, repo: str, *, per_page: int = 30) -> Sequence[Dict[str, Any]]:
        response = self.requester.request(
            "GET",
            f"/repos/{owner}/{repo}/events",
            params={"per_page": per_page},
            cache_policy=CachePolicy(ttl_seconds=120.0),
        )
        data = response.json()
        if isinstance(data, list):
            return data
        return []


class TokenomicsClient(BaseClient):
    """Client for retrieving tokenomics metrics from generic APIs."""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(timeout=timeout)
        super().__init__(session)

    def fetch_token_metrics(self, url: str) -> Dict[str, Any]:
        response = self.requester.request("GET", url, cache_policy=CachePolicy(ttl_seconds=900.0))
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        raise RuntimeError("Tokenomics endpoint must return a JSON object")
