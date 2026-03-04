"""Tests for REST API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.pipeline.ingest import store_tick
from backend.pipeline.inference import store_prediction
from backend.services.alert_engine import store_alert


def _make_test_app():
    """Create a minimal FastAPI app with routers but no pipeline orchestrator."""
    from fastapi import FastAPI
    from backend.routers import symbols, model, alerts, pipeline

    app = FastAPI()
    app.include_router(symbols.router, prefix="/api")
    app.include_router(model.router, prefix="/api")
    app.include_router(alerts.router, prefix="/api")
    app.include_router(pipeline.router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture
def app():
    return _make_test_app()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Health ──


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Symbols ──


@pytest.mark.asyncio
async def test_symbols_empty(client):
    resp = await client.get("/api/symbols")
    assert resp.status_code == 200
    data = resp.json()
    assert "symbols" in data


@pytest.mark.asyncio
async def test_symbols_with_data(client):
    store_tick({"symbol": "AAPL", "price": 150.0, "volume": 10000, "timestamp": "2024-06-01T10:00:00"})
    store_tick({"symbol": "AAPL", "price": 151.0, "volume": 10500, "timestamp": "2024-06-01T10:01:00"})

    resp = await client.get("/api/symbols")
    assert resp.status_code == 200
    data = resp.json()
    aapl = next((s for s in data["symbols"] if s["symbol"] == "AAPL"), None)
    assert aapl is not None
    assert aapl["price"] is not None


# ── Symbol History ──


@pytest.mark.asyncio
async def test_symbol_history(client):
    resp = await client.get("/api/symbols/AAPL/history?period=1h")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert "ticks" in data
    assert "predictions" in data
    assert "features" in data


# ── Model Stats ──


@pytest.mark.asyncio
async def test_model_stats(client):
    resp = await client.get("/api/model/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data
    assert "architecture" in data
    assert "parameters" in data


# ── Alerts ──


@pytest.mark.asyncio
async def test_alerts_empty(client):
    resp = await client.get("/api/alerts")
    assert resp.status_code == 200
    assert "alerts" in resp.json()


@pytest.mark.asyncio
async def test_alerts_with_data(client):
    store_alert({"type": "signal", "symbol": "AAPL", "message": "Test signal", "severity": "info"})
    store_alert({"type": "anomaly", "symbol": "TSLA", "message": "Vol spike", "severity": "warning"})

    resp = await client.get("/api/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["alerts"]) == 2


@pytest.mark.asyncio
async def test_alerts_filter_by_type(client):
    store_alert({"type": "signal", "symbol": "AAPL", "message": "sig", "severity": "info"})
    store_alert({"type": "anomaly", "symbol": "TSLA", "message": "anom", "severity": "warning"})

    resp = await client.get("/api/alerts?type=signal")
    assert resp.status_code == 200
    data = resp.json()
    assert all(a["type"] == "signal" for a in data["alerts"])


# ── Pipeline Status ──


@pytest.mark.asyncio
async def test_pipeline_status(client):
    resp = await client.get("/api/pipeline/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "stages" in data
    assert "uptime" in data
    assert len(data["stages"]) == 5
