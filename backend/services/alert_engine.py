"""Anomaly detection and signal generation.

Analyzes features and predictions to produce alerts of three types:
  - signal:  high-confidence predictions, momentum breakouts
  - anomaly: volume spikes, unusual spread, volatility jumps
  - info:    pipeline status updates
"""

import logging
import uuid
from datetime import datetime, timezone

from backend.database import get_connection

logger = logging.getLogger(__name__)

# Thresholds
CONFIDENCE_THRESHOLD = 0.85
VOLUME_ZSCORE_THRESHOLD = 2.5
VOLATILITY_THRESHOLD = 0.02
MOMENTUM_THRESHOLD = 0.03


class AlertEngine:
    """Generates alerts from feature data and model predictions."""

    def check(
        self,
        symbol: str,
        features: dict | None,
        prediction: dict | None,
    ) -> list[dict]:
        """Analyze features and prediction for a symbol.

        Returns a list of alert dicts ready for storage and broadcast.
        """
        alerts: list[dict] = []

        # --- Signal alerts (from predictions) ---
        if prediction and prediction.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
            direction = prediction["direction"]
            confidence = prediction["confidence"]
            alerts.append({
                "type": "signal",
                "symbol": symbol,
                "message": f"{direction} signal — confidence {confidence:.0%}",
                "severity": "warning" if confidence >= 0.9 else "info",
                "metadata": f'{{"direction":"{direction}","confidence":{confidence:.4f}}}',
            })

        # --- Anomaly alerts (from features) ---
        if features:
            vol_z = features.get("volume_zscore", 0)
            if abs(vol_z) >= VOLUME_ZSCORE_THRESHOLD:
                alerts.append({
                    "type": "anomaly",
                    "symbol": symbol,
                    "message": f"Volume anomaly detected — z-score {vol_z:.2f}",
                    "severity": "warning",
                    "metadata": f'{{"volume_zscore":{vol_z:.4f}}}',
                })

            volatility = features.get("volatility", 0)
            if volatility >= VOLATILITY_THRESHOLD:
                alerts.append({
                    "type": "anomaly",
                    "symbol": symbol,
                    "message": f"High volatility — {volatility:.4f}",
                    "severity": "warning",
                    "metadata": f'{{"volatility":{volatility:.4f}}}',
                })

            momentum = features.get("momentum", 0)
            if abs(momentum) >= MOMENTUM_THRESHOLD:
                direction = "bullish" if momentum > 0 else "bearish"
                alerts.append({
                    "type": "signal",
                    "symbol": symbol,
                    "message": f"Momentum breakout ({direction}) — {momentum:+.2%}",
                    "severity": "info",
                    "metadata": f'{{"momentum":{momentum:.4f}}}',
                })

        return alerts


def store_alert(alert: dict) -> str:
    """Insert an alert into DuckDB. Returns the alert ID."""
    alert_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO alerts (id, type, symbol, message, severity, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            alert_id,
            alert["type"],
            alert.get("symbol"),
            alert["message"],
            alert.get("severity", "info"),
            alert.get("metadata"),
        ],
    )
    return alert_id
