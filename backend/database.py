"""DuckDB connection and table initialization.

Uses a thread-safe singleton connection to avoid the overhead and
write-conflict issues of opening/closing connections on every call.
"""

import threading
from pathlib import Path

import duckdb

from backend.config import get_settings

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS ticks (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    price       DOUBLE NOT NULL,
    volume      BIGINT NOT NULL,
    bid         DOUBLE,
    ask         DOUBLE,
    timestamp   TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks(symbol, timestamp);

CREATE TABLE IF NOT EXISTS features (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    window_end  TIMESTAMP NOT NULL,
    sma_20      DOUBLE,
    ema_12      DOUBLE,
    rsi_14      DOUBLE,
    volatility  DOUBLE,
    vwap        DOUBLE,
    momentum    DOUBLE,
    volume_zscore DOUBLE,
    spread      DOUBLE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_features_symbol_window ON features(symbol, window_end);

CREATE TABLE IF NOT EXISTS predictions (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    direction   TEXT NOT NULL,
    confidence  DOUBLE NOT NULL,
    price_at    DOUBLE NOT NULL,
    target_price DOUBLE,
    horizon_s   INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    features_id TEXT REFERENCES features(id),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_predictions_symbol_ts ON predictions(symbol, created_at);

CREATE TABLE IF NOT EXISTS alerts (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    symbol      TEXT,
    message     TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'info',
    metadata    TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_metrics (
    id          TEXT PRIMARY KEY,
    stage       TEXT NOT NULL,
    throughput  DOUBLE,
    latency_p50 DOUBLE,
    latency_p99 DOUBLE,
    error_count INTEGER DEFAULT 0,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return the singleton DuckDB connection, creating it on first call."""
    global _conn
    with _lock:
        if _conn is None:
            settings = get_settings()
            db_path = settings.duckdb_path
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            _conn = duckdb.connect(db_path)
        return _conn


def close_connection() -> None:
    """Close the singleton connection (call during app shutdown)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def reset_connection() -> None:
    """Close and discard the singleton so a new path can be used (for tests)."""
    close_connection()


def init_tables() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    for statement in _TABLES_SQL.strip().split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)
