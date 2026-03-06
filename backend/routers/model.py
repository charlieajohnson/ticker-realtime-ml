"""GET /api/model/stats endpoint."""

import math
from pathlib import Path

import torch
from fastapi import APIRouter

from backend.database import get_connection
from backend.models.tickernet import TickerNet

router = APIRouter()

CHECKPOINT_DIR = Path(__file__).parent.parent / "models" / "checkpoints"


@router.get("/model/stats")
async def model_stats():
    """Current model performance metrics."""
    # Count parameters
    model = TickerNet()
    param_count = sum(p.numel() for p in model.parameters())

    # Try to load checkpoint metadata
    checkpoint_path = CHECKPOINT_DIR / "tickernet_v0.1.pt"
    accuracy = None
    val_loss = None
    model_version = "v0.1"
    last_trained = None
    epoch = None

    if checkpoint_path.exists():
        try:
            ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
            accuracy = ckpt.get("accuracy")
            val_loss = ckpt.get("val_loss")
            model_version = ckpt.get("model_version", "v0.1")
            epoch = ckpt.get("epoch")
        except Exception:
            pass

    # Count today's predictions
    conn = get_connection()
    row = conn.execute(
        """
        SELECT COUNT(*) FROM predictions
        WHERE created_at >= CURRENT_DATE
        """
    ).fetchone()
    predictions_today = row[0] if row else 0

    # Compute Sharpe ratio and max drawdown from resolved predictions
    sharpe = None
    max_drawdown = None

    outcomes = conn.execute(
        """
        SELECT p.direction, p.price_at,
               (SELECT t.price FROM ticks t
                WHERE t.symbol = p.symbol
                  AND t.timestamp >= p.created_at + INTERVAL (p.horizon_s) SECOND
                ORDER BY t.timestamp ASC LIMIT 1) AS outcome_price
        FROM predictions p
        WHERE p.created_at >= CURRENT_DATE
        """
    ).fetchall()

    returns = []
    for direction, price_at, outcome_price in outcomes:
        if outcome_price is None or price_at == 0:
            continue
        ret = (outcome_price - price_at) / price_at
        sign = 1.0 if direction == "LONG" else -1.0
        returns.append(ret * sign)

    if len(returns) >= 30:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / len(returns))
        sharpe = round(mean_r / std_r * math.sqrt(len(returns)), 3) if std_r > 0 else None

        # Max drawdown from cumulative returns
        cumulative = 0.0
        peak = 0.0
        worst_dd = 0.0
        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > worst_dd:
                worst_dd = dd
        max_drawdown = round(-worst_dd, 4)

    return {
        "name": f"TickerNet {model_version}",
        "architecture": "LSTM + Attention",
        "parameters": f"{param_count / 1000:.1f}K",
        "accuracy_1h": accuracy,
        "val_loss": val_loss,
        "epoch": epoch,
        "predictions_today": predictions_today,
        "last_trained": last_trained,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
    }
