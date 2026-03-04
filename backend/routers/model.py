"""GET /api/model/stats endpoint."""

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

    return {
        "name": f"TickerNet {model_version}",
        "architecture": "LSTM + Attention",
        "parameters": f"{param_count / 1000:.1f}K",
        "accuracy_1h": accuracy,
        "val_loss": val_loss,
        "epoch": epoch,
        "predictions_today": predictions_today,
        "last_trained": last_trained,
    }
