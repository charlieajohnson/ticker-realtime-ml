# ticker-realtime-ml
Real-time financial data pipeline with ML inference. Ingests live market data, engineers features (SMA, RSI, VWAP), runs an LSTM+Attention model for short-term price prediction, and serves predictions via WebSocket to a terminal-inspired React dashboard. Built with FastAPI, PyTorch, DuckDB, and Docker.
