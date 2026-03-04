"""DuckDB connection and table initialization."""

import os
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


def get_connection() -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    db_path = settings.duckdb_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(db_path)


def init_tables() -> None:
    conn = get_connection()
    for statement in _TABLES_SQL.strip().split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)
    conn.close()
