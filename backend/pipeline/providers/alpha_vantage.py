"""Alpha Vantage data provider.

Uses the GLOBAL_QUOTE endpoint. Requires an API key (free tier: 5 req/min).
Best suited for daily snapshot data, not real-time streaming.
"""

import logging

import aiohttp

from backend.pipeline.providers.base import Provider

logger = logging.getLogger(__name__)

_AV_BASE = "https://www.alphavantage.co/query"


class AlphaVantageProvider(Provider):
    """Fetches quotes from Alpha Vantage GLOBAL_QUOTE endpoint."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch(self, session: aiohttp.ClientSession, symbol: str) -> dict | None:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self._api_key,
        }
        try:
            async with session.get(_AV_BASE, params=params) as resp:
                if resp.status != 200:
                    logger.warning("Alpha Vantage %s HTTP %s", symbol, resp.status)
                    return None
                data = await resp.json(content_type=None)

            quote = data.get("Global Quote", {})
            if not quote or "05. price" not in quote:
                note = data.get("Note") or data.get("Information") or ""
                if note:
                    logger.warning("Alpha Vantage rate limit: %s", note)
                else:
                    logger.warning("Empty quote for %s", symbol)
                return None

            return {
                "symbol": symbol,
                "price": float(quote["05. price"]),
                "volume": int(quote["06. volume"]),
                "bid": None,
                "ask": None,
                "timestamp": quote.get("07. latest trading day", ""),
            }
        except Exception:
            logger.exception("Error fetching %s from Alpha Vantage", symbol)
            return None
