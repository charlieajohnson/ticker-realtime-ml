# Ticker — Real-Time Financial Data Pipeline with ML Inference

> **Purpose**: Portfolio project demonstrating production ML + data engineering.
> **Level**: MVP — functional pipeline, clean architecture, Dockerised.
> **Stack**: Python, FastAPI, WebSockets, DuckDB, PyTorch, Docker, React frontend.

---

## System Overview

Ticker ingests real-time market data, engineers features from the stream,
runs a lightweight LSTM model for short-term price movement prediction,
and serves predictions + alerts via a WebSocket-powered dashboard.

```
┌──────────────────────────────────────────────────────────────────┐
│  Data Sources (Market APIs)                                      │
│  Alpha Vantage / Polygon.io / Finnhub (pick one with free tier) │
└──────────┬───────────────────────────────────────────────────────┘
           │  REST poll (1s) or WebSocket stream
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Pipeline                                                        │
│                                                                  │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐ │
│  │  Ingest  │→ │ Transform │→ │ Feature   │→ │  Inference    │ │
│  │          │  │           │  │ Engineer  │  │  (PyTorch)    │ │
│  └──────────┘  └───────────┘  └───────────┘  └───────┬───────┘ │
│       │                                              │          │
│       ▼                                              ▼          │
│  ┌──────────┐                                  ┌───────────┐   │
│  │  DuckDB  │                                  │  Alerts /  │   │
│  │  (store) │                                  │  Signals   │   │
│  └──────────┘                                  └───────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
           │
           │  FastAPI + WebSocket
           ▼
┌──────────────────┐
│  React Dashboard │  ← "Ticker" UI (see TickerUI.jsx reference)
│  - Live prices   │
│  - Predictions   │
│  - Signal feed   │
│  - Pipeline viz  │
└──────────────────┘
```

---

## Data Models

### DuckDB Tables

```sql
-- Raw tick data as ingested
CREATE TABLE ticks (
    id          TEXT PRIMARY KEY,    -- uuid4
    symbol      TEXT NOT NULL,
    price       DOUBLE NOT NULL,
    volume      BIGINT NOT NULL,
    bid         DOUBLE,
    ask         DOUBLE,
    timestamp   TIMESTAMP NOT NULL,  -- exchange timestamp
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ticks_symbol_ts ON ticks(symbol, timestamp);

-- Engineered features (computed per window)
CREATE TABLE features (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    window_end  TIMESTAMP NOT NULL,
    sma_20      DOUBLE,             -- simple moving average
    ema_12      DOUBLE,             -- exponential moving average
    rsi_14      DOUBLE,             -- relative strength index
    volatility  DOUBLE,             -- rolling std dev of returns
    vwap        DOUBLE,             -- volume-weighted average price
    momentum    DOUBLE,             -- rate of change
    volume_zscore DOUBLE,           -- volume anomaly score
    spread      DOUBLE,             -- bid-ask spread
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_features_symbol_window ON features(symbol, window_end);

-- Model predictions
CREATE TABLE predictions (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    direction   TEXT NOT NULL,       -- 'LONG' | 'SHORT'
    confidence  DOUBLE NOT NULL,     -- 0.0 to 1.0
    price_at    DOUBLE NOT NULL,     -- price when prediction was made
    target_price DOUBLE,            -- predicted price (optional)
    horizon_s   INTEGER NOT NULL,    -- prediction horizon in seconds
    model_version TEXT NOT NULL,
    features_id TEXT REFERENCES features(id),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_predictions_symbol_ts ON predictions(symbol, created_at);

-- Alerts / signals
CREATE TABLE alerts (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,       -- 'signal' | 'anomaly' | 'info'
    symbol      TEXT,                -- nullable for system alerts
    message     TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'info',  -- info | warning | critical
    metadata    TEXT,                -- JSON blob for extra context
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Pipeline health metrics
CREATE TABLE pipeline_metrics (
    id          TEXT PRIMARY KEY,
    stage       TEXT NOT NULL,       -- 'ingest' | 'transform' | 'feature' | 'inference' | 'serve'
    throughput  DOUBLE,             -- messages per second
    latency_p50 DOUBLE,            -- milliseconds
    latency_p99 DOUBLE,
    error_count INTEGER DEFAULT 0,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## API Design

### WebSocket: `/ws/stream`
Primary real-time channel. Pushes events to the frontend.

```
Messages (server → client):

// Price update
{
  "type": "tick",
  "symbol": "AAPL",
  "price": 189.23,
  "change": 0.34,
  "volume": 1240000,
  "sparkline": [188.9, 189.0, ...],  // last N prices
  "timestamp": "2025-03-04T14:32:08Z"
}

// New prediction
{
  "type": "prediction",
  "symbol": "AAPL",
  "direction": "LONG",
  "confidence": 0.87,
  "model_version": "v0.3",
  "timestamp": "2025-03-04T14:32:10Z"
}

// Alert
{
  "type": "alert",
  "alert_type": "signal",        // signal | anomaly | info
  "symbol": "NVDA",
  "message": "Momentum breakout detected — confidence 0.91",
  "timestamp": "2025-03-04T14:32:08Z"
}

// Pipeline status
{
  "type": "pipeline_status",
  "stages": [
    { "name": "ingest", "status": "active", "throughput": 1200, "latency_ms": 3 },
    ...
  ]
}
```

### REST Endpoints

#### `GET /api/symbols`
List tracked symbols with latest data.

```
Response: 200
{
  "symbols": [
    {
      "symbol": "AAPL",
      "price": 189.23,
      "change_pct": 0.34,
      "volume": 12400000,
      "prediction": { "direction": "LONG", "confidence": 0.87 },
      "sparkline": [188.9, 189.0, ...]
    }
  ]
}
```

#### `GET /api/symbols/{symbol}/history`
Historical ticks and predictions for a symbol.

```
Query params: ?period=1h|4h|1d  (default: 1h)

Response: 200
{
  "symbol": "AAPL",
  "ticks": [...],
  "predictions": [...],
  "features": [...]
}
```

#### `GET /api/model/stats`
Current model performance metrics.

```
Response: 200
{
  "name": "TickerNet v0.3",
  "architecture": "LSTM + Attention",
  "parameters": "1.2M",
  "accuracy_1h": 0.673,
  "sharpe_ratio": 1.84,
  "max_drawdown": -0.042,
  "predictions_today": 2847,
  "last_trained": "2025-03-04T12:00:00Z"
}
```

#### `GET /api/alerts`
Recent alerts and signals.

```
Query params: ?limit=50&type=signal|anomaly|info

Response: 200
{
  "alerts": [
    {
      "id": "...",
      "type": "signal",
      "symbol": "NVDA",
      "message": "Momentum breakout detected",
      "created_at": "2025-03-04T14:32:08Z"
    }
  ]
}
```

#### `GET /api/pipeline/status`
Pipeline health dashboard data.

```
Response: 200
{
  "stages": [
    {
      "name": "ingest",
      "status": "active",
      "throughput": 1200,
      "latency_p50_ms": 3,
      "latency_p99_ms": 12,
      "error_count": 0
    }
  ],
  "uptime": 0.9997,
  "total_ticks": 48203
}
```

---

## ML Model — TickerNet

### Architecture

```
Input (sequence of feature vectors, window=60)
  │
  ▼
LSTM (hidden_size=64, num_layers=2, dropout=0.2)
  │
  ▼
Attention (single-head, over LSTM hidden states)
  │
  ▼
Linear(64 → 32) + ReLU + Dropout(0.3)
  │
  ▼
Linear(32 → 2)  →  [direction_logit, confidence_logit]
  │
  ▼
Softmax (direction) + Sigmoid (confidence)
```

### Feature Vector (per timestep)

```python
FEATURES = [
    "price_normalized",     # price / SMA_20
    "return_1",             # 1-tick return
    "return_5",             # 5-tick return
    "rsi_14",               # 0-100 scaled to 0-1
    "volatility",           # rolling std of returns
    "volume_zscore",        # (vol - mean) / std
    "spread_normalized",    # (ask - bid) / price
    "momentum",             # rate of change
    "ema_ratio",            # EMA_12 / SMA_20
    "vwap_ratio",           # price / VWAP
]
# Input shape: (batch, 60, 10)
```

### Training Strategy (MVP)

- **Data**: Collect ticks for 24-48h, then train offline
- **Train/val split**: Time-based (no lookahead), 80/20
- **Loss**: Cross-entropy (direction) + MSE (confidence calibration)
- **Optimizer**: AdamW, lr=1e-3, weight_decay=1e-4
- **Epochs**: 50 with early stopping (patience=10)
- **Inference**: Run on latest 60-tick window, emit prediction every N ticks

### Model Files

```
models/
├── tickernet.py          ← model definition (nn.Module)
├── train.py              ← training script
├── evaluate.py           ← backtesting + metrics
└── checkpoints/
    └── tickernet_v03.pt  ← saved weights
```

---

## File Structure

```
ticker/
├── README.md
├── SPEC.md                      ← this file
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml           ← app + optional DuckDB volume
├── .env.example                 ← API keys for data provider
│
├── backend/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI app, WebSocket manager, lifespan
│   ├── config.py                ← pydantic-settings (API keys, intervals, etc.)
│   ├── database.py              ← DuckDB connection + table init
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── ingest.py            ← async market data fetcher (aiohttp)
│   │   ├── transform.py         ← tick cleaning, normalization
│   │   ├── features.py          ← feature engineering (SMA, RSI, VWAP, etc.)
│   │   ├── inference.py         ← load model, run predictions
│   │   └── orchestrator.py      ← pipeline coordinator, scheduling
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── tickernet.py         ← PyTorch model definition
│   │   ├── train.py             ← training script
│   │   └── checkpoints/         ← saved model weights
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── symbols.py           ← /api/symbols endpoints
│   │   ├── model.py             ← /api/model/stats endpoint
│   │   ├── alerts.py            ← /api/alerts endpoint
│   │   ├── pipeline.py          ← /api/pipeline/status endpoint
│   │   └── ws.py                ← WebSocket endpoint
│   │
│   └── services/
│       ├── __init__.py
│       ├── stream_manager.py    ← WebSocket connection pool + broadcasting
│       └── alert_engine.py      ← anomaly detection, signal generation
│
├── frontend/                    ← "Ticker" — cold terminal dashboard (see TickerUI.jsx)
│   ├── package.json
│   ├── index.html
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx              ← dashboard grid layout
│       ├── api.js               ← REST fetch wrappers
│       ├── ws.js                ← WebSocket client with reconnect
│       ├── styles.css           ← CSS variables, animations, grain overlay
│       ├── components/
│       │   ├── TopBar.jsx       ← logo, live status, tick count, clock
│       │   ├── PipelineStrip.jsx ← horizontal pipeline stage visualizer
│       │   ├── StockTable.jsx   ← live-updating price table with sparklines
│       │   ├── StockRow.jsx     ← symbol, price, change, volume, prediction
│       │   ├── Sparkline.jsx    ← inline SVG sparkline with area fill
│       │   ├── ModelCard.jsx    ← model stats grid (accuracy, sharpe, etc.)
│       │   ├── AlertFeed.jsx    ← scrollable signal/anomaly/info feed
│       │   ├── AlertItem.jsx    ← typed alert with timestamp and badge
│       │   ├── ConfidenceBar.jsx ← thin horizontal confidence indicator
│       │   └── BottomBar.jsx    ← pipeline health, latency, uptime
│       └── main.jsx
│
└── tests/
    ├── test_pipeline.py
    ├── test_features.py
    ├── test_model.py
    └── test_api.py
```

---

## Dependencies

```toml
# pyproject.toml [project.dependencies]
fastapi = ">=0.110"
uvicorn = { version = ">=0.29", extras = ["standard"] }
websockets = ">=12.0"
aiohttp = ">=3.9"
duckdb = ">=0.10"
torch = ">=2.2"
numpy = ">=1.26"
pandas = ">=2.2"
scikit-learn = ">=1.4"       # for preprocessing / metrics
pydantic-settings = ">=2.0"
python-dotenv = ">=1.0"
```

---

## Docker

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .

# DuckDB data directory
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - duckdb-data:/app/data

volumes:
  duckdb-data:
```

---

## Frontend Design — "Ticker"

The frontend is a real-time dashboard with a cold, terminal-inspired aesthetic.
It should feel like a quant's monitoring tool — data-dense, precise, alive.
Reference `TickerUI.jsx` for the complete interactive mock with live-updating
prices, sparklines, and working animations.

### Design System

```
Theme:        Cold dark (blue-black backgrounds, cyan accents)
Font stack:   Outfit (headings/labels) + IBM Plex Mono (data/numbers)
Accent color: #00DCC8 (electric cyan) — live dot, model stats, signal badges
Danger:       #F87171 (red) — short signals, negative changes
Success:      #34D399 (green) — long signals, positive changes
Warning:      #FBBF24 (amber) — anomaly alerts, mid-confidence
Texture:      subtle grain overlay via SVG noise filter
```

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Top Bar: logo · LIVE dot · tick count · symbols · clock         │
├─────────────────────────────────────────────┬────────────────────┤
│  Pipeline strip (horizontal flow viz)       │                    │
├─────────────────────────────────────────────┤   Model Card       │
│                                             │   - accuracy       │
│  Stock Table (live-updating)                │   - sharpe         │
│   symbol | price | Δ% | vol | spark | conf  │   - drawdown       │
│   AAPL   | 189.2 | +  | 12M | ~~~~ | 87%  │   - predictions    │
│   ...    | ...   | .. | ... | .... | ...   │                    │
│                                             ├────────────────────┤
│                                             │   Signal Feed      │
│                                             │   - alert items    │
│                                             │   - typed badges   │
│                                             │   - timestamps     │
├─────────────────────────────────────────────┴────────────────────┤
│  Bottom Bar: pipeline health · e2e latency · model · uptime     │
└──────────────────────────────────────────────────────────────────┘
```

### Key UI Details

- **Live updates**: prices, sparklines, confidence bars update every ~1.5s
- **Pipeline strip**: horizontal flow with animated scanline effect per stage
- **Sparklines**: inline SVGs with gradient area fill, color-coded by direction
- **Prediction badges**: LONG (green) / SHORT (red) with zap icon
- **Signal feed**: left-border colored by type (cyan=signal, amber=anomaly, gray=info)
- **Grain overlay**: subtle SVG noise texture animated across the viewport
- **Status bar**: bottom bar with pipeline health, e2e latency, WebSocket status

### Wiring to Backend

Replace mock data with WebSocket + REST in `ws.js` and `api.js`:

```javascript
// ws.js
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/stream";

export function createSocket(onMessage) {
  let ws;
  let reconnectTimer;

  function connect() {
    ws = new WebSocket(WS_URL);
    ws.onmessage = (e) => onMessage(JSON.parse(e.data));
    ws.onclose = () => {
      reconnectTimer = setTimeout(connect, 2000);
    };
  }

  connect();
  return () => {
    clearTimeout(reconnectTimer);
    ws?.close();
  };
}
```

```javascript
// api.js
const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export async function getSymbols() {
  const res = await fetch(`${API}/symbols`);
  return res.json();
}

export async function getModelStats() {
  const res = await fetch(`${API}/model/stats`);
  return res.json();
}

export async function getAlerts(limit = 50) {
  const res = await fetch(`${API}/alerts?limit=${limit}`);
  return res.json();
}

export async function getPipelineStatus() {
  const res = await fetch(`${API}/pipeline/status`);
  return res.json();
}
```

---

## Build Order (suggested for Claude Code)

1. **Project scaffolding** — pyproject.toml, Dockerfile, .env.example, folder structure
2. **Database layer** — database.py (DuckDB init, table creation)
3. **Data ingestion** — ingest.py (async market data fetcher, tick storage)
4. **Feature engineering** — features.py (SMA, RSI, VWAP, volatility, etc.)
5. **Pipeline orchestrator** — orchestrator.py (coordinate ingest → transform → features)
6. **Model definition** — tickernet.py (LSTM + Attention module)
7. **Training script** — train.py (data loading, training loop, checkpoint saving)
8. **Inference service** — inference.py (load model, run on feature windows)
9. **Alert engine** — alert_engine.py (volume anomalies, signal detection)
10. **REST endpoints** — symbols.py, model.py, alerts.py, pipeline.py
11. **WebSocket streaming** — ws.py + stream_manager.py
12. **Docker** — Dockerfile + docker-compose.yml, verify containerised run
13. **Frontend** — React dashboard matching Ticker design (reference TickerUI.jsx)
14. **Tests** — pipeline, features, model, API integration
15. **README** — architecture diagram, setup, demo screenshot

---

## Portfolio Talking Points

This project demonstrates:
- **Real-time data engineering** — async ingestion, streaming pipeline, live processing
- **ML in production** — PyTorch model serving predictions in a live system, not just a notebook
- **Feature engineering** — financial indicators computed from raw ticks (SMA, RSI, VWAP)
- **WebSocket architecture** — real-time push to frontend, connection management, reconnection
- **Data modeling** — DuckDB for analytics-friendly storage, time-series indexing
- **Containerisation** — Dockerised for portable deployment
- **System monitoring** — pipeline health metrics, throughput/latency tracking
