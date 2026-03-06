"""Load model and run predictions.

InferenceService wraps TickerNet for live prediction during the pipeline loop.
Handles missing checkpoints gracefully so the pipeline can run without a model.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from backend.database import get_connection
from backend.models.tickernet import TickerNet

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT = Path(__file__).parent.parent / "models" / "checkpoints" / "tickernet_v0.1.pt"


class InferenceService:
    """Loads a TickerNet checkpoint and runs predictions on feature windows."""

    def __init__(self, checkpoint_path: Path | None = None) -> None:
        self._model: TickerNet | None = None
        self._model_version: str = "unknown"
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        path = checkpoint_path or DEFAULT_CHECKPOINT
        if path.exists():
            self.load_model(path)
        else:
            logger.warning("No model checkpoint at %s — inference disabled", path)

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def load_model(self, path: Path) -> None:
        """Load TickerNet weights from a checkpoint file."""
        try:
            checkpoint = torch.load(path, map_location=self._device, weights_only=True)
            model = TickerNet().to(self._device)
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            self._model = model
            self._model_version = checkpoint.get("model_version", "unknown")
            logger.info(
                "Loaded model %s (val_loss=%.4f, acc=%.3f)",
                self._model_version,
                checkpoint.get("val_loss", 0),
                checkpoint.get("accuracy", 0),
            )
        except Exception:
            logger.exception("Failed to load model from %s", path)
            self._model = None

    def predict(self, feature_vector: np.ndarray) -> dict | None:
        """Run inference on a feature window.

        Args:
            feature_vector: numpy array of shape (seq_len, 10)

        Returns:
            dict with keys: direction, confidence, model_version
            or None if model not loaded.
        """
        if self._model is None:
            return None

        try:
            x = torch.tensor(feature_vector, dtype=torch.float32).unsqueeze(0).to(self._device)

            with torch.no_grad():
                dir_probs, confidence = self._model(x)

            dir_idx = dir_probs.argmax(dim=1).item()
            direction = "LONG" if dir_idx == 1 else "SHORT"

            return {
                "direction": direction,
                "confidence": float(confidence.item()),
                "model_version": self._model_version,
            }
        except Exception:
            logger.exception("Inference failed")
            return None


def store_prediction(
    symbol: str,
    prediction: dict,
    price_at: float,
    features_id: str | None = None,
    horizon_s: int = 10,
) -> str:
    """Insert a prediction row into DuckDB. Returns the prediction ID."""
    pred_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO predictions
            (id, symbol, direction, confidence, price_at,
             horizon_s, model_version, features_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            pred_id,
            symbol,
            prediction["direction"],
            prediction["confidence"],
            price_at,
            horizon_s,
            prediction["model_version"],
            features_id,
        ],
    )
    return pred_id
