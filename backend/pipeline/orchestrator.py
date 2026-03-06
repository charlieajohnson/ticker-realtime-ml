"""Pipeline coordinator and scheduling.

Runs the ingest → transform → features → inference → alerts loop on a
configurable interval, tracks per-stage timing, records pipeline_metrics
to DuckDB, and broadcasts events to WebSocket clients.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

import aiohttp

from backend.config import get_settings
from backend.database import get_connection
from backend.pipeline.ingest import ingest_cycle, store_tick
from backend.pipeline.transform import clean_tick, get_recent_ticks
from backend.pipeline.features import (
    build_feature_vector,
    compute_features,
    store_features,
)
from backend.pipeline.inference import InferenceService, store_prediction
from backend.services.alert_engine import AlertEngine, store_alert
from backend.services.stream_manager import StreamManager

logger = logging.getLogger(__name__)


def _record_metric(stage: str, latency_ms: float, throughput: float = 0, errors: int = 0) -> None:
    """Write a pipeline_metrics row to DuckDB."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO pipeline_metrics
            (id, stage, throughput, latency_p50, latency_p99, error_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [str(uuid.uuid4()), stage, throughput, latency_ms, latency_ms, errors],
    )


class PipelineOrchestrator:
    """Coordinates the full pipeline and broadcasts events via WebSocket."""

    def __init__(
        self,
        stream_manager: StreamManager | None = None,
        alert_engine: AlertEngine | None = None,
    ) -> None:
        self._task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._inference = InferenceService()
        self._stream = stream_manager
        self._alerts = alert_engine or AlertEngine()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        self._running = True
        self._task = asyncio.create_task(self._run_forever())
        logger.info("Pipeline orchestrator started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
        logger.info("Pipeline orchestrator stopped")

    # ------------------------------------------------------------------
    # Broadcasting helper
    # ------------------------------------------------------------------

    async def _broadcast(self, message: dict) -> None:
        if self._stream:
            await self._stream.broadcast(message)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _run_forever(self) -> None:
        settings = get_settings()
        symbols = settings.symbol_list
        interval = settings.ingest_interval_s

        logger.info("Pipeline loop: %d symbols, interval=%ss", len(symbols), interval)

        while self._running:
            try:
                await self._run_cycle(symbols)
            except Exception:
                logger.exception("Pipeline cycle error")
            await asyncio.sleep(interval)

    async def _run_cycle(self, symbols: list[str]) -> None:
        """Execute one full pipeline cycle."""
        assert self._session is not None
        settings = get_settings()
        now = datetime.now(timezone.utc).isoformat()
        stage_metrics: list[dict] = []

        # --- Ingest stage (fetch only) ---
        t0 = time.perf_counter()
        raw_quotes = await ingest_cycle(self._session, symbols)
        ingest_ms = (time.perf_counter() - t0) * 1000
        _record_metric("ingest", ingest_ms, throughput=len(raw_quotes))
        stage_metrics.append({"name": "ingest", "status": "active", "throughput": len(raw_quotes), "latency_ms": round(ingest_ms, 1)})

        # --- Transform stage (clean + store) ---
        t0 = time.perf_counter()
        cleaned = [clean_tick(q) for q in raw_quotes]
        cleaned = [t for t in cleaned if t is not None]
        for tick in cleaned:
            try:
                store_tick(tick)
            except Exception:
                logger.exception("Failed to store tick for %s", tick.get("symbol"))
        transform_ms = (time.perf_counter() - t0) * 1000
        _record_metric("transform", transform_ms, throughput=len(cleaned))
        stage_metrics.append({"name": "transform", "status": "active", "throughput": len(cleaned), "latency_ms": round(transform_ms, 1)})

        if cleaned:
            logger.info("Ingested %d ticks (%.0fms + %.0fms)", len(cleaned), ingest_ms, transform_ms)

        # Broadcast tick updates
        for tick in cleaned:
            conn = get_connection()
            rows = conn.execute(
                "SELECT price FROM ticks WHERE symbol = ? ORDER BY timestamp DESC LIMIT 20",
                [tick["symbol"]],
            ).fetchall()
            sparkline = [r[0] for r in reversed(rows)]

            change = 0.0
            if len(sparkline) >= 2 and sparkline[0] != 0:
                change = round((sparkline[-1] - sparkline[0]) / sparkline[0] * 100, 2)

            await self._broadcast({
                "type": "tick",
                "symbol": tick["symbol"],
                "price": tick["price"],
                "change": change,
                "volume": tick["volume"],
                "sparkline": sparkline,
                "timestamp": now,
            })

        # --- Feature engineering stage ---
        t0 = time.perf_counter()
        feature_count = 0
        feature_ids: dict[str, str] = {}
        feature_dicts: dict[str, dict] = {}
        for symbol in symbols:
            try:
                df = get_recent_ticks(symbol, limit=settings.feature_window_size)
                if df.empty:
                    continue
                feats = compute_features(df)
                if feats is None:
                    continue
                feat_id = store_features(symbol, feats)
                feature_ids[symbol] = feat_id
                feature_dicts[symbol] = feats
                feature_count += 1
            except Exception:
                logger.exception("Feature engineering failed for %s", symbol)
        feature_ms = (time.perf_counter() - t0) * 1000
        _record_metric("feature", feature_ms, throughput=feature_count)
        stage_metrics.append({"name": "feature", "status": "active", "throughput": feature_count, "latency_ms": round(feature_ms, 1)})

        # --- Inference stage ---
        t0 = time.perf_counter()
        pred_count = 0
        predictions: dict[str, dict] = {}
        if self._inference.is_ready:
            for symbol in symbols:
                try:
                    df = get_recent_ticks(symbol, limit=settings.feature_window_size)
                    if df.empty:
                        continue
                    vec = build_feature_vector(df)
                    if vec is None:
                        continue

                    prediction = self._inference.predict(vec)
                    if prediction is None:
                        continue

                    price_at = float(df["price"].iloc[-1])
                    features_id = feature_ids.get(symbol)
                    store_prediction(symbol, prediction, price_at, features_id)
                    predictions[symbol] = prediction
                    pred_count += 1

                    # Broadcast prediction
                    await self._broadcast({
                        "type": "prediction",
                        "symbol": symbol,
                        "direction": prediction["direction"],
                        "confidence": prediction["confidence"],
                        "model_version": prediction["model_version"],
                        "timestamp": now,
                    })
                except Exception:
                    logger.exception("Inference failed for %s", symbol)

        inference_ms = (time.perf_counter() - t0) * 1000
        _record_metric("inference", inference_ms, throughput=pred_count)
        stage_metrics.append({"name": "inference", "status": "active" if self._inference.is_ready else "idle", "throughput": pred_count, "latency_ms": round(inference_ms, 1)})

        if pred_count:
            logger.info("Generated %d predictions (%.0fms)", pred_count, inference_ms)

        # --- Alert stage ---
        for symbol in symbols:
            feats = feature_dicts.get(symbol)
            pred = predictions.get(symbol)
            if not feats and not pred:
                continue

            alerts = self._alerts.check(symbol, feats, pred)
            for alert in alerts:
                try:
                    store_alert(alert)
                    await self._broadcast({
                        "type": "alert",
                        "alert_type": alert["type"],
                        "symbol": alert.get("symbol"),
                        "message": alert["message"],
                        "timestamp": now,
                    })
                except Exception:
                    logger.exception("Alert storage/broadcast failed")

        # --- Broadcast pipeline status ---
        stage_metrics.append({"name": "serve", "status": "active", "throughput": 0, "latency_ms": 0})
        await self._broadcast({"type": "pipeline_status", "stages": stage_metrics})
