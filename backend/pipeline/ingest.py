"""Async market data fetcher (aiohttp).

Supports Alpha Vantage (default), with a provider abstraction
for easy swapping to Polygon or Finnhub.
"""

import logging
import uuid
from datetime import datetime, timezone

import aiohttp

from backend.config import get_settings
from backend.database import get_connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alpha Vantage provider
# ---------------------------------------------------------------------------

_AV_BASE = "https://www.alphavantage.co/query"


async def _fetch_alpha_vantage(
    session: aiohttp.ClientSession,
    symbol: str,
    api_key: str,
) -> dict | None:
    """Fetch a single quote from Alpha Vantage GLOBAL_QUOTE endpoint."""
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": api_key,
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


# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------


async def fetch_quote(
    session: aiohttp.ClientSession,
    symbol: str,
) -> dict | None:
    """Fetch a single quote using the configured provider."""
    settings = get_settings()
    provider = settings.api_provider

    if provider == "alpha_vantage":
        api_key = settings.alpha_vantage_api_key
        if not api_key:
            logger.warning("ALPHA_VANTAGE_API_KEY not set — skipping ingest")
            return None
        return await _fetch_alpha_vantage(session, symbol, api_key)

    logger.error("Unknown API provider: %s", provider)
    return None


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def store_tick(tick: dict) -> str:
    """Insert a single tick into DuckDB. Returns the tick ID."""
    tick_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO ticks (id, symbol, price, volume, bid, ask, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                tick_id,
                tick["symbol"],
                tick["price"],
                tick["volume"],
                tick.get("bid"),
                tick.get("ask"),
                tick.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            ],
        )
    finally:
        conn.close()
    return tick_id


# ---------------------------------------------------------------------------
# Ingest cycle
# ---------------------------------------------------------------------------


async def ingest_cycle(
    session: aiohttp.ClientSession,
    symbols: list[str],
) -> list[dict]:
    """Run one full ingest round: fetch + store for all symbols.

    Returns the list of successfully stored ticks.
    """
    stored: list[dict] = []
    for symbol in symbols:
        quote = await fetch_quote(session, symbol)
        if quote is None:
            continue
        try:
            store_tick(quote)
            stored.append(quote)
        except Exception:
            logger.exception("Failed to store tick for %s", symbol)
    return stored
