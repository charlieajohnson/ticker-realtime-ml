"""Tests for feature engineering."""

import numpy as np
import pandas as pd
import pytest

from backend.pipeline.features import (
    _sma,
    _ema,
    _rsi,
    _volatility,
    _vwap,
    _momentum,
    _volume_zscore,
    _spread,
    compute_features,
    build_feature_vector,
    store_features,
    MIN_TICKS,
)


def _make_df(n=30, base_price=100.0):
    """Build a synthetic tick DataFrame with n rows."""
    np.random.seed(42)
    prices = base_price + np.cumsum(np.random.randn(n) * 0.5)
    volumes = np.random.randint(1000, 50000, size=n)
    bids = prices * 0.999
    asks = prices * 1.001
    return pd.DataFrame({
        "price": prices,
        "volume": volumes,
        "bid": bids,
        "ask": asks,
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="s"),
    })


# ── Individual indicators ──


class TestSMA:
    def test_basic(self):
        prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _sma(prices, 5) == pytest.approx(3.0)

    def test_window_smaller_than_series(self):
        prices = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        assert _sma(prices, 3) == pytest.approx(40.0)  # mean of last 3


class TestEMA:
    def test_returns_float(self):
        prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _ema(prices, span=3)
        assert isinstance(result, float)

    def test_converges_to_constant(self):
        prices = pd.Series([5.0] * 20)
        assert _ema(prices, span=12) == pytest.approx(5.0)


class TestRSI:
    def test_all_gains_returns_100(self):
        prices = pd.Series(range(1, 30), dtype=float)
        assert _rsi(prices, 14) == pytest.approx(100.0)

    def test_range(self):
        df = _make_df(50)
        result = _rsi(df["price"], 14)
        assert 0 <= result <= 100


class TestVolatility:
    def test_constant_prices_zero_vol(self):
        prices = pd.Series([100.0] * 25)
        assert _volatility(prices, 20) == pytest.approx(0.0)

    def test_positive_for_varying_prices(self):
        df = _make_df(30)
        assert _volatility(df["price"], 20) > 0


class TestVWAP:
    def test_equal_volumes(self):
        prices = pd.Series([10.0, 20.0, 30.0])
        volumes = pd.Series([1, 1, 1])
        assert _vwap(prices, volumes) == pytest.approx(20.0)

    def test_zero_volume_fallback(self):
        prices = pd.Series([42.0, 43.0])
        volumes = pd.Series([0, 0])
        assert _vwap(prices, volumes) == pytest.approx(43.0)


class TestMomentum:
    def test_no_change(self):
        prices = pd.Series([50.0] * 20)
        assert _momentum(prices, 10) == pytest.approx(0.0)

    def test_positive_momentum(self):
        prices = pd.Series(range(1, 20), dtype=float)
        assert _momentum(prices, 10) > 0

    def test_too_few_ticks(self):
        prices = pd.Series([1.0, 2.0])
        assert _momentum(prices, 10) == pytest.approx(0.0)


class TestVolumeZscore:
    def test_constant_volume(self):
        volumes = pd.Series([1000] * 25)
        assert _volume_zscore(volumes, 20) == pytest.approx(0.0)

    def test_spike_detected(self):
        volumes = pd.Series([1000] * 24 + [5000])
        assert _volume_zscore(volumes, 20) > 2.0


class TestSpread:
    def test_basic_spread(self):
        bid = pd.Series([99.0])
        ask = pd.Series([101.0])
        price = pd.Series([100.0])
        assert _spread(bid, ask, price) == pytest.approx(0.02)

    def test_zero_price(self):
        bid = pd.Series([1.0])
        ask = pd.Series([2.0])
        price = pd.Series([0.0])
        assert _spread(bid, ask, price) == pytest.approx(0.0)


# ── compute_features ──


class TestComputeFeatures:
    def test_returns_none_below_min_ticks(self):
        df = _make_df(n=10)
        assert compute_features(df) is None

    def test_returns_dict_with_all_keys(self):
        df = _make_df(n=30)
        result = compute_features(df)
        assert result is not None
        expected_keys = {"sma_20", "ema_12", "rsi_14", "volatility", "vwap", "momentum", "volume_zscore", "spread"}
        assert set(result.keys()) == expected_keys

    def test_values_are_finite(self):
        df = _make_df(n=50)
        result = compute_features(df)
        for key, val in result.items():
            assert np.isfinite(val), f"{key} is not finite: {val}"


# ── build_feature_vector ──


class TestBuildFeatureVector:
    def test_returns_none_below_min_ticks(self):
        df = _make_df(n=10)
        assert build_feature_vector(df) is None

    def test_output_shape(self):
        df = _make_df(n=40)
        vec = build_feature_vector(df)
        assert vec is not None
        assert vec.shape == (40, 10)

    def test_no_nan_or_inf(self):
        df = _make_df(n=60)
        vec = build_feature_vector(df)
        assert not np.any(np.isnan(vec))
        assert not np.any(np.isinf(vec))


# ── store_features (DB integration) ──


class TestStoreFeatures:
    def test_store_and_retrieve(self, db):
        df = _make_df(n=30)
        feats = compute_features(df)
        feat_id = store_features("AAPL", feats)

        row = db.execute("SELECT * FROM features WHERE id = ?", [feat_id]).fetchone()
        assert row is not None
        assert row[1] == "AAPL"  # symbol column
