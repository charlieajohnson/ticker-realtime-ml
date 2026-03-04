"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database import init_tables
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.services.alert_engine import AlertEngine
from backend.services.stream_manager import StreamManager
from backend.routers import symbols, model, alerts, pipeline, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logging.info("Initializing database tables...")
    init_tables()

    # Create shared services
    stream_manager = StreamManager()
    alert_engine = AlertEngine()
    app.state.stream_manager = stream_manager

    # Start pipeline
    orchestrator = PipelineOrchestrator(
        stream_manager=stream_manager,
        alert_engine=alert_engine,
    )
    await orchestrator.start()
    logging.info("Ticker pipeline starting up")

    yield

    await orchestrator.stop()
    logging.info("Ticker pipeline shutting down")


app = FastAPI(title="Ticker", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(symbols.router, prefix="/api")
app.include_router(model.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")

# WebSocket (no prefix — ws.py defines /ws/stream)
app.include_router(ws.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve frontend static build if available (production / Docker)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
