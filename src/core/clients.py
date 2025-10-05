"""HTTP clients for external data providers used by the scanner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

import httpx

if TYPE_CHECKING:  # pragma: no cover - import for type checkers only
    from feedparser import FeedParserDict


class BaseClient:
    """Shared convenience helpers for HTTP clients."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError("HTTP client has not been initialised")
        return self._client

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
            "",
            params={
                "module": "contract",
                "action": "getsourcecode",
                "address": address,
                "apikey": self._api_key,
            },
        )
        response.raise_for_status()
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

        response = self.client.get(url)
        response.raise_for_status()
        try:
            import feedparser
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("feedparser is required for NewsFeedClient") from exc

        return feedparser.parse(response.content)
