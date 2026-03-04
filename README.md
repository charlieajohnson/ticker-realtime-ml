# ticker-realtime-ml
Real-time financial data pipeline with ML inference. Ingests live market data, engineers features (SMA, RSI, VWAP), runs an LSTM+Attention model for short-term price prediction, and serves predictions via WebSocket to a terminal-inspired React dashboard. Built with FastAPI, PyTorch, DuckDB, and Docker.

# Ticker

**Real-time financial data pipeline with ML inference.**

Ticker ingests live market data, engineers features from the stream, runs a lightweight LSTM model for short-term price movement prediction, and serves predictions + alerts via a WebSocket-powered dashboard.

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688)
![PyTorch](https://img.shields.io/badge/PyTorch-2.2+-ee4c2c)
![DuckDB](https://img.shields.io/badge/DuckDB-0.10+-ffd700)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED)

---

## Demo

<!-- Replace with actual screenshot -->
> ![Dashboard Screenshot](docs/screenshot.png)
>
> *The Ticker dashboard showing live prices, sparklines, model predictions, pipeline health, and signal feed.*

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Data Sources (Alpha Vantage / Polygon.io / Finnhub)            │
└──────────┬───────────────────────────────────────────────────────┘
           │  REST poll (1s) or WebSocket stream
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Pipeline                                                        │
│                                                                  │
│  ┌──────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐  │
│  │  Ingest  │──▶│ Transform │──▶│ Feature   │──▶│ Inference  │  │
│  │          │   │           │   │ Engineer  │   │ (PyTorch)  │  │
│  └────┬─────┘   └───────────┘   └───────────┘   └─────┬─────┘  │
│       │                                                │         │
│       ▼                                                ▼         │
│  ┌──────────┐                                   ┌───────────┐   │
│  │  DuckDB  │                                   │  Alerts /  │   │
│  │  (store) │                                   │  Signals   │   │
│  └──────────┘                                   └───────────┘   │
└──────────────────────────────────────────────────────────────────┘
           │
           │  FastAPI + WebSocket
           ▼
┌──────────────────┐
│  React Dashboard │
│  - Live prices   │
│  - Predictions   │
│  - Signal feed   │
│  - Pipeline viz  │
└──────────────────┘
```

---

## Features

**Data Pipeline**
- Async market data ingestion via aiohttp (REST polling or WebSocket)
- Tick cleaning, normalization, and storage in DuckDB
- Real-time feature engineering: SMA, EMA, RSI, VWAP, volatility, momentum, volume z-score, bid-ask spread

**ML Inference**
- LSTM + single-head attention model (TickerNet, ~1.2M parameters)
- Predicts short-term price direction (LONG/SHORT) with confidence score
- Runs inference on sliding 60-tick feature windows
- Offline training script with time-based train/val split and early stopping

**Backend**
- FastAPI with WebSocket streaming for real-time push to clients
- REST endpoints for symbols, model stats, alerts, and pipeline health
- Connection pool management with automatic reconnection
- Alert engine for volume anomalies and momentum signals

**Frontend — "Ticker" Dashboard**
- Cold, terminal-inspired aesthetic (Outfit + IBM Plex Mono, cyan accents, grain overlay)
- Live-updating price table with inline SVG sparklines
- Pipeline stage visualizer with animated scanline effect
- Model stats card (accuracy, Sharpe ratio, drawdown, prediction count)
- Signal feed with typed alerts (signal / anomaly / info)
- Bottom status bar with pipeline health and WebSocket status

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, WebSockets, uvicorn |
| ML | PyTorch (LSTM + Attention) |
| Data | DuckDB, pandas, NumPy |
| Data Source | Alpha Vantage / Polygon.io / Finnhub |
| Frontend | React, Vite |
| Infra | Docker, docker-compose |

---

## Project Structure

```
ticker/
├── backend/
│   ├── main.py                  # FastAPI app, WebSocket manager, lifespan
│   ├── config.py                # Settings via pydantic-settings
│   ├── database.py              # DuckDB connection + table init
│   ├── pipeline/
│   │   ├── ingest.py            # Async market data fetcher
│   │   ├── transform.py         # Tick cleaning, normalization
│   │   ├── features.py          # Feature engineering (SMA, RSI, VWAP, etc.)
│   │   ├── inference.py         # Load model, run predictions
│   │   └── orchestrator.py      # Pipeline coordinator
│   ├── models/
│   │   ├── tickernet.py         # PyTorch model definition
│   │   ├── train.py             # Training script
│   │   └── checkpoints/         # Saved model weights
│   ├── routers/
│   │   ├── symbols.py           # /api/symbols endpoints
│   │   ├── model.py             # /api/model/stats
│   │   ├── alerts.py            # /api/alerts
│   │   ├── pipeline.py          # /api/pipeline/status
│   │   └── ws.py                # WebSocket endpoint
│   └── services/
│       ├── stream_manager.py    # WebSocket connection pool + broadcasting
│       └── alert_engine.py      # Anomaly detection, signal generation
├── frontend/
│   └── src/
│       ├── App.jsx              # Dashboard grid layout
│       ├── api.js               # REST fetch wrappers
│       ├── ws.js                # WebSocket client with reconnect
│       └── components/          # TopBar, StockTable, Sparkline, ModelCard, etc.
├── tests/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (optional)
- API key (optional) — the project runs with synthetic data by default

### Setup

```bash
# Clone the repo
git clone https://github.com/charlieajohnson/ticker-realtime-ml.git
cd ticker-realtime-ml

# Configure environment
cp .env.example .env

# Install backend dependencies
pip install -e .

# Install frontend dependencies
cd frontend && npm install && cd ..
```

> **Note:** No API key is needed for the default setup. The synthetic data provider generates realistic tick data using geometric Brownian motion so the full pipeline runs out of the box.

### Run (Development)

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) to view the dashboard.

### Run (Docker)

```bash
docker-compose up --build
```

The app will be available at [http://localhost:8000](http://localhost:8000).

### Train the Model

```bash
# Collect tick data for 24-48h first, then:
python -m backend.models.train
```

Model checkpoints are saved to `backend/models/checkpoints/`.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `WS` | `/ws/stream` | Real-time tick, prediction, alert, and pipeline status events |
| `GET` | `/api/symbols` | List tracked symbols with latest prices and predictions |
| `GET` | `/api/symbols/{symbol}/history` | Historical ticks, predictions, and features |
| `GET` | `/api/model/stats` | Model performance metrics (accuracy, Sharpe, drawdown) |
| `GET` | `/api/alerts` | Recent signals, anomalies, and info alerts |
| `GET` | `/api/pipeline/status` | Pipeline stage health, throughput, and latency |

---

## Model — TickerNet

```
Input (batch, 60, 10)     ← 60-tick window, 10 features per tick
       │
  LSTM (hidden=64, layers=2, dropout=0.2)
       │
  Attention (single-head over hidden states)
       │
  Linear(64→32) + ReLU + Dropout(0.3)
       │
  Linear(32→2)  →  direction (softmax) + confidence (sigmoid)
```

**Feature vector per timestep:** price/SMA ratio, 1-tick return, 5-tick return, RSI (normalized), volatility, volume z-score, normalized spread, momentum, EMA/SMA ratio, price/VWAP ratio.

**Training:** AdamW optimizer, cross-entropy + MSE loss, early stopping with patience of 10 epochs, time-based 80/20 train/val split.

---

## What This Demonstrates

- **Real-time data engineering** — async ingestion, streaming pipeline, live processing
- **ML in production** — PyTorch model serving predictions in a live system, not just a notebook
- **Feature engineering** — financial indicators computed from raw ticks (SMA, RSI, VWAP)
- **WebSocket architecture** — real-time push to frontend, connection management, reconnection
- **Data modeling** — DuckDB for analytics-friendly storage, time-series indexing
- **Containerization** — Dockerized for portable deployment
- **System monitoring** — pipeline health metrics, throughput/latency tracking

---

## License

MIT
