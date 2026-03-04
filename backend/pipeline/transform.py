"""Tick cleaning and normalization."""

import logging
from datetime import datetime, timezone

import pandas as pd

from backend.database import get_connection

logger = logging.getLogger(__name__)


def clean_tick(raw: dict) -> dict | None:
    """Validate and normalize a single raw tick.

    Returns the cleaned tick dict, or None if invalid.
    """
    try:
        price = float(raw["price"])
        volume = int(raw["volume"])
    except (KeyError, ValueError, TypeError):
        logger.warning("Invalid price/volume in tick: %s", raw)
        return None

    if price <= 0:
        logger.warning("Non-positive price %.4f for %s", price, raw.get("symbol"))
        return None
    if volume < 0:
        logger.warning("Negative volume %d for %s", volume, raw.get("symbol"))
        return None

    # Fill missing bid/ask from price
    bid = raw.get("bid")
    ask = raw.get("ask")
    if bid is None:
        bid = price * 0.999
    if ask is None:
        ask = price * 1.001

    # Parse timestamp
    ts = raw.get("timestamp")
    if isinstance(ts, str) and ts:
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            ts = datetime.now(timezone.utc)
    elif not isinstance(ts, datetime):
        ts = datetime.now(timezone.utc)

    return {
        "symbol": raw["symbol"],
        "price": price,
        "volume": volume,
        "bid": float(bid),
        "ask": float(ask),
        "timestamp": ts,
    }


def get_recent_ticks(symbol: str, limit: int = 100) -> pd.DataFrame:
    """Query DuckDB for the latest *limit* ticks for a symbol.

    Returns a DataFrame sorted by timestamp ascending (oldest first).
    """
    conn = get_connection()
    try:
        df = conn.execute(
            """
            SELECT symbol, price, volume, bid, ask, timestamp
            FROM ticks
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            [symbol, limit],
        ).fetchdf()
    finally:
        conn.close()

    if df.empty:
        return df

    # Sort ascending so oldest is first (rolling calcs need chronological order)
    return df.sort_values("timestamp").reset_index(drop=True)
