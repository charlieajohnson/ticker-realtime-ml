"""GET /api/symbols endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from backend.config import get_settings
from backend.database import get_connection

router = APIRouter()


@router.get("/symbols")
async def list_symbols():
    """List tracked symbols with latest price, prediction, and sparkline."""
    settings = get_settings()
    symbols = settings.symbol_list
    conn = get_connection()

    result = []
    for symbol in symbols:
        # Latest tick
        tick = conn.execute(
            """
            SELECT price, volume, timestamp
            FROM ticks WHERE symbol = ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            [symbol],
        ).fetchone()

        if not tick:
            result.append({"symbol": symbol, "price": None})
            continue

        price, volume, ts = tick

        # Sparkline (last 20 prices)
        sparkline_rows = conn.execute(
            """
            SELECT price FROM ticks
            WHERE symbol = ?
            ORDER BY timestamp DESC LIMIT 20
            """,
            [symbol],
        ).fetchall()
        sparkline = [r[0] for r in reversed(sparkline_rows)]

        # Change % from sparkline
        change_pct = 0.0
        if len(sparkline) >= 2 and sparkline[0] != 0:
            change_pct = round((sparkline[-1] - sparkline[0]) / sparkline[0] * 100, 2)

        # Latest prediction
        pred_row = conn.execute(
            """
            SELECT direction, confidence
            FROM predictions WHERE symbol = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            [symbol],
        ).fetchone()

        prediction = None
        if pred_row:
            prediction = {"direction": pred_row[0], "confidence": pred_row[1]}

        result.append({
            "symbol": symbol,
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "prediction": prediction,
            "sparkline": sparkline,
        })

    return {"symbols": result}


@router.get("/symbols/{symbol}/history")
async def symbol_history(symbol: str, period: str = Query("1h")):
    """Historical ticks, predictions, and features for a symbol."""
    hours = {"1h": 1, "4h": 4, "1d": 24}.get(period, 1)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    conn = get_connection()

    ticks = conn.execute(
        """
        SELECT id, price, volume, bid, ask, timestamp
        FROM ticks WHERE symbol = ?
          AND timestamp >= ?
        ORDER BY timestamp ASC
        """,
        [symbol, cutoff],
    ).fetchdf().to_dict(orient="records")

    predictions = conn.execute(
        """
        SELECT id, direction, confidence, price_at, model_version, created_at
        FROM predictions WHERE symbol = ?
          AND created_at >= ?
        ORDER BY created_at ASC
        """,
        [symbol, cutoff],
    ).fetchdf().to_dict(orient="records")

    features = conn.execute(
        """
        SELECT id, window_end, sma_20, ema_12, rsi_14, volatility,
               vwap, momentum, volume_zscore, spread
        FROM features WHERE symbol = ?
          AND window_end >= ?
        ORDER BY window_end ASC
        """,
        [symbol, cutoff],
    ).fetchdf().to_dict(orient="records")

    return {
        "symbol": symbol,
        "ticks": ticks,
        "predictions": predictions,
        "features": features,
    }
