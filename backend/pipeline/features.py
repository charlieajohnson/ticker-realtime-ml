"""Feature engineering — SMA, RSI, VWAP, volatility, etc.

Computes the 8 indicators stored in the `features` table and the
10-element feature vector consumed by TickerNet.
"""

import logging
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend.database import get_connection

logger = logging.getLogger(__name__)

# Minimum ticks required to compute a meaningful feature set
MIN_TICKS = 20


# ---------------------------------------------------------------------------
# Individual indicator helpers
# ---------------------------------------------------------------------------


def _sma(prices: pd.Series, window: int = 20) -> float:
    """Simple moving average of the last *window* prices."""
    return float(prices.tail(window).mean())


def _ema(prices: pd.Series, span: int = 12) -> float:
    """Exponential moving average (last value of the EMA series)."""
    return float(prices.ewm(span=span, adjust=False).mean().iloc[-1])


def _rsi(prices: pd.Series, period: int = 14) -> float:
    """Relative Strength Index (0–100)."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period, min_periods=period).mean().iloc[-1]

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _volatility(prices: pd.Series, window: int = 20) -> float:
    """Rolling standard deviation of log returns."""
    log_ret = np.log(prices / prices.shift(1)).dropna()
    if len(log_ret) < 2:
        return 0.0
    return float(log_ret.tail(window).std())


def _vwap(prices: pd.Series, volumes: pd.Series) -> float:
    """Volume-weighted average price."""
    total_vol = volumes.sum()
    if total_vol == 0:
        return float(prices.iloc[-1])
    return float((prices * volumes).sum() / total_vol)


def _momentum(prices: pd.Series, lookback: int = 10) -> float:
    """Rate of change: current / price[-lookback] - 1."""
    if len(prices) <= lookback:
        return 0.0
    return float(prices.iloc[-1] / prices.iloc[-lookback] - 1.0)


def _volume_zscore(volumes: pd.Series, window: int = 20) -> float:
    """Z-score of the latest volume relative to a rolling window."""
    rolling = volumes.tail(window)
    mean = rolling.mean()
    std = rolling.std()
    if std == 0:
        return 0.0
    return float((volumes.iloc[-1] - mean) / std)


def _spread(bid: pd.Series, ask: pd.Series, price: pd.Series) -> float:
    """Normalised bid-ask spread: (ask - bid) / price."""
    last_bid = bid.iloc[-1]
    last_ask = ask.iloc[-1]
    last_price = price.iloc[-1]
    if last_price == 0:
        return 0.0
    return float((last_ask - last_bid) / last_price)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_features(df: pd.DataFrame) -> dict | None:
    """Compute all 8 stored features from a tick DataFrame.

    Expects columns: price, volume, bid, ask, timestamp.
    Returns a dict matching the `features` table columns, or None if
    there are too few ticks.
    """
    if len(df) < MIN_TICKS:
        return None

    prices = df["price"]
    volumes = df["volume"]
    bids = df["bid"]
    asks = df["ask"]

    sma_20 = _sma(prices, 20)

    return {
        "sma_20": sma_20,
        "ema_12": _ema(prices, 12),
        "rsi_14": _rsi(prices, 14),
        "volatility": _volatility(prices, 20),
        "vwap": _vwap(prices, volumes),
        "momentum": _momentum(prices, 10),
        "volume_zscore": _volume_zscore(volumes, 20),
        "spread": _spread(bids, asks, prices),
    }


def build_feature_vector(df: pd.DataFrame) -> np.ndarray | None:
    """Build the 10-element feature vector for TickerNet.

    Returns an array of shape (len(df), 10) or None if insufficient data.
    Each row corresponds to one timestep.

    Features (per timestep):
        0  price_normalized   — price / SMA_20
        1  return_1           — 1-tick return
        2  return_5           — 5-tick return
        3  rsi_14             — RSI scaled to 0-1
        4  volatility         — rolling std of log returns
        5  volume_zscore      — z-score of volume
        6  spread_normalized  — (ask - bid) / price
        7  momentum           — rate of change
        8  ema_ratio          — EMA_12 / SMA_20
        9  vwap_ratio         — price / VWAP
    """
    if len(df) < MIN_TICKS:
        return None

    prices = df["price"].astype(float)
    volumes = df["volume"].astype(float)
    bids = df["bid"].astype(float)
    asks = df["ask"].astype(float)

    sma_20 = prices.rolling(20, min_periods=1).mean()
    ema_12 = prices.ewm(span=12, adjust=False).mean()

    # Returns
    return_1 = prices.pct_change(1).fillna(0.0)
    return_5 = prices.pct_change(5).fillna(0.0)

    # RSI per-row (rolling)
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14, min_periods=1).mean()
    avg_loss = loss.rolling(14, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.inf)
    rsi = (100.0 - 100.0 / (1.0 + rs)) / 100.0  # scale to 0-1

    # Volatility (rolling std of log returns)
    log_ret = np.log(prices / prices.shift(1)).fillna(0.0)
    vol = log_ret.rolling(20, min_periods=1).std().fillna(0.0)

    # Volume z-score (rolling)
    vol_mean = volumes.rolling(20, min_periods=1).mean()
    vol_std = volumes.rolling(20, min_periods=1).std().replace(0, 1.0)
    volume_z = (volumes - vol_mean) / vol_std

    # Spread
    spread_norm = (asks - bids) / prices.replace(0, 1.0)

    # Momentum
    momentum = prices.pct_change(10).fillna(0.0)

    # Ratios
    ema_ratio = ema_12 / sma_20.replace(0, 1.0)
    cum_vwap = (prices * volumes).cumsum() / volumes.cumsum().replace(0, 1.0)
    vwap_ratio = prices / cum_vwap.replace(0, 1.0)

    vec = np.column_stack([
        (prices / sma_20.replace(0, 1.0)).values,  # price_normalized
        return_1.values,
        return_5.values,
        rsi.fillna(0.5).values,
        vol.values,
        volume_z.fillna(0.0).values,
        spread_norm.fillna(0.0).values,
        momentum.values,
        ema_ratio.fillna(1.0).values,
        vwap_ratio.fillna(1.0).values,
    ])

    # Replace any NaN/inf that slipped through
    vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)

    return vec


def store_features(symbol: str, feats: dict) -> str:
    """Insert a feature row into DuckDB. Returns the feature ID."""
    feat_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO features
                (id, symbol, window_end, sma_20, ema_12, rsi_14,
                 volatility, vwap, momentum, volume_zscore, spread)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                feat_id,
                symbol,
                datetime.now(timezone.utc),
                feats["sma_20"],
                feats["ema_12"],
                feats["rsi_14"],
                feats["volatility"],
                feats["vwap"],
                feats["momentum"],
                feats["volume_zscore"],
                feats["spread"],
            ],
        )
    finally:
        conn.close()
    return feat_id
