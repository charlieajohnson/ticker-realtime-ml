"""Finnhub data provider.

Uses the /quote endpoint. Free tier: 60 API calls/minute.
Suitable for polling with 8-10s intervals.
"""

import logging

import aiohttp

from backend.pipeline.providers.base import Provider

logger = logging.getLogger(__name__)

_FINNHUB_BASE = "https://finnhub.io/api/v1/quote"


class FinnhubProvider(Provider):
    """Fetches quotes from Finnhub /quote endpoint."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch(self, session: aiohttp.ClientSession, symbol: str) -> dict | None:
        params = {"symbol": symbol, "token": self._api_key}
        try:
            async with session.get(_FINNHUB_BASE, params=params) as resp:
                if resp.status != 200:
                    logger.warning("Finnhub %s HTTP %s", symbol, resp.status)
                    return None
                data = await resp.json(content_type=None)

            price = data.get("c")  # current price
            if not price or price == 0:
                return None

            return {
                "symbol": symbol,
                "price": float(price),
                "volume": int(data.get("v", 0) or 0),
                "bid": None,
                "ask": None,
                "timestamp": None,
            }
        except Exception:
            logger.exception("Error fetching %s from Finnhub", symbol)
            return None
