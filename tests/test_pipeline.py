"""Tests for pipeline stages."""

from datetime import datetime, timezone

import pytest

from backend.pipeline.transform import clean_tick, get_recent_ticks
from backend.pipeline.ingest import store_tick
from backend.services.alert_engine import AlertEngine, store_alert


# ── clean_tick ──


class TestCleanTick:
    def test_valid_tick(self):
        raw = {"symbol": "AAPL", "price": 150.0, "volume": 10000, "bid": 149.9, "ask": 150.1, "timestamp": "2024-06-01T12:00:00"}
        result = clean_tick(raw)
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["price"] == 150.0
        assert result["volume"] == 10000
        assert result["bid"] == 149.9
        assert result["ask"] == 150.1

    def test_fills_missing_bid_ask(self):
        raw = {"symbol": "MSFT", "price": 400.0, "volume": 5000, "timestamp": "2024-01-01"}
        result = clean_tick(raw)
        assert result is not None
        assert result["bid"] == pytest.approx(400.0 * 0.999)
        assert result["ask"] == pytest.approx(400.0 * 1.001)

    def test_rejects_zero_price(self):
        raw = {"symbol": "X", "price": 0, "volume": 100}
        assert clean_tick(raw) is None

    def test_rejects_negative_price(self):
        raw = {"symbol": "X", "price": -5.0, "volume": 100}
        assert clean_tick(raw) is None

    def test_rejects_negative_volume(self):
        raw = {"symbol": "X", "price": 100.0, "volume": -1}
        assert clean_tick(raw) is None

    def test_rejects_missing_price(self):
        raw = {"symbol": "X", "volume": 100}
        assert clean_tick(raw) is None

    def test_handles_invalid_timestamp(self):
        raw = {"symbol": "AAPL", "price": 150.0, "volume": 1000, "timestamp": "not-a-date"}
        result = clean_tick(raw)
        assert result is not None
        assert isinstance(result["timestamp"], datetime)

    def test_handles_none_timestamp(self):
        raw = {"symbol": "AAPL", "price": 150.0, "volume": 1000, "timestamp": None}
        result = clean_tick(raw)
        assert result is not None
        assert isinstance(result["timestamp"], datetime)


# ── store_tick + get_recent_ticks ──


class TestStoreTick:
    def test_store_and_retrieve(self, db):
        tick = {"symbol": "TSLA", "price": 175.0, "volume": 8000, "timestamp": "2024-06-01T10:00:00"}
        tick_id = store_tick(tick)

        row = db.execute("SELECT * FROM ticks WHERE id = ?", [tick_id]).fetchone()
        assert row is not None
        assert row[1] == "TSLA"  # symbol

    def test_get_recent_ticks_returns_chronological(self, db):
        # Insert 5 ticks with incrementing timestamps
        for i in range(5):
            store_tick({
                "symbol": "GOOGL",
                "price": 170.0 + i,
                "volume": 1000,
                "timestamp": f"2024-06-01T10:0{i}:00",
            })

        df = get_recent_ticks("GOOGL", limit=10)
        assert len(df) == 5
        # Should be sorted ascending by timestamp
        prices = df["price"].tolist()
        assert prices == sorted(prices)

    def test_get_recent_ticks_empty(self):
        df = get_recent_ticks("NONEXISTENT", limit=10)
        assert df.empty


# ── AlertEngine ──


class TestAlertEngine:
    def setup_method(self):
        self.engine = AlertEngine()

    def test_no_alerts_for_normal_data(self):
        features = {"volume_zscore": 0.5, "volatility": 0.005, "momentum": 0.01}
        prediction = {"direction": "LONG", "confidence": 0.6}
        alerts = self.engine.check("AAPL", features, prediction)
        assert alerts == []

    def test_signal_alert_high_confidence(self):
        prediction = {"direction": "LONG", "confidence": 0.92}
        alerts = self.engine.check("AAPL", None, prediction)
        assert len(alerts) == 1
        assert alerts[0]["type"] == "signal"
        assert "LONG" in alerts[0]["message"]

    def test_anomaly_volume_spike(self):
        features = {"volume_zscore": 3.0, "volatility": 0.001, "momentum": 0.0}
        alerts = self.engine.check("NVDA", features, None)
        assert any(a["type"] == "anomaly" for a in alerts)

    def test_anomaly_high_volatility(self):
        features = {"volume_zscore": 0.0, "volatility": 0.05, "momentum": 0.0}
        alerts = self.engine.check("TSLA", features, None)
        assert any(a["type"] == "anomaly" and "volatility" in a["message"].lower() for a in alerts)

    def test_momentum_breakout(self):
        features = {"volume_zscore": 0.0, "volatility": 0.0, "momentum": 0.05}
        alerts = self.engine.check("MSFT", features, None)
        assert any(a["type"] == "signal" and "momentum" in a["message"].lower() for a in alerts)

    def test_no_data_no_alerts(self):
        alerts = self.engine.check("AAPL", None, None)
        assert alerts == []


class TestStoreAlert:
    def test_store_and_retrieve(self, db):
        alert = {
            "type": "signal",
            "symbol": "AAPL",
            "message": "Test alert",
            "severity": "warning",
        }
        alert_id = store_alert(alert)
        row = db.execute("SELECT * FROM alerts WHERE id = ?", [alert_id]).fetchone()
        assert row is not None
        assert row[1] == "signal"
