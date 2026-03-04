"""Async market data fetcher.

Dispatches to a configured provider (synthetic by default, Alpha Vantage
for real data) and stores validated ticks in DuckDB.
"""

import logging
import uuid
from datetime import datetime, timezone

import aiohttp

from backend.config import get_settings
from backend.database import get_connection
from backend.pipeline.providers.base import Provider
from backend.pipeline.providers.synthetic import SyntheticProvider
from backend.pipeline.providers.alpha_vantage import AlphaVantageProvider

logger = logging.getLogger(__name__)

# Singleton provider instance (created on first use)
_provider: Provider | None = None


def _get_provider() -> Provider:
    """Return the configured provider, creating it on first call."""
    global _provider
    if _provider is not None:
        return _provider

    settings = get_settings()
    name = settings.api_provider

    if name == "synthetic":
        _provider = SyntheticProvider()
    elif name == "alpha_vantage":
        api_key = settings.alpha_vantage_api_key
        if not api_key:
            logger.warning("ALPHA_VANTAGE_API_KEY not set — falling back to synthetic")
            _provider = SyntheticProvider()
        else:
            _provider = AlphaVantageProvider(api_key)
    else:
        logger.error("Unknown API provider '%s' — falling back to synthetic", name)
        _provider = SyntheticProvider()

    return _provider


async def fetch_quote(
    session: aiohttp.ClientSession,
    symbol: str,
) -> dict | None:
    """Fetch a single quote using the configured provider."""
    provider = _get_provider()
    return await provider.fetch(session, symbol)


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
