"""Synthetic data provider using geometric Brownian motion.

Generates realistic tick data so the project runs out of the box with no
API key. Prices follow a random walk with occasional momentum regimes to
trigger alerts and interesting sparkline patterns.
"""

import math
import random
from datetime import datetime, timezone

import aiohttp

from backend.pipeline.providers.base import Provider

# Approximate real base prices per symbol
_BASE_PRICES = {
    "AAPL": 189.0,
    "GOOGL": 175.0,
    "MSFT": 420.0,
    "AMZN": 187.0,
    "NVDA": 875.0,
    "TSLA": 176.0,
    "META": 505.0,
    "JPM": 199.0,
}

_DEFAULT_BASE = 100.0


class SyntheticProvider(Provider):
    """Generates synthetic tick data via geometric Brownian motion.

    Prices persist across calls per symbol instance, so sparklines show
    continuous movement rather than random jumps.
    """

    def __init__(self) -> None:
        self._prices: dict[str, float] = {}
        self._momentum: dict[str, tuple[float, int]] = {}  # symbol → (drift, ticks_remaining)

    def _get_price(self, symbol: str) -> float:
        if symbol not in self._prices:
            self._prices[symbol] = _BASE_PRICES.get(symbol, _DEFAULT_BASE)
        return self._prices[symbol]

    def _step_price(self, symbol: str) -> float:
        """Advance the price by one tick using GBM with momentum regimes."""
        price = self._get_price(symbol)

        # Check / start momentum regime
        drift, remaining = self._momentum.get(symbol, (0.0, 0))
        if remaining <= 0:
            # 5% chance of entering a momentum regime each tick
            if random.random() < 0.05:
                drift = random.choice([-1, 1]) * random.uniform(0.0003, 0.001)
                remaining = random.randint(20, 50)
            else:
                drift = 0.0
                remaining = 0
        else:
            remaining -= 1
        self._momentum[symbol] = (drift, remaining)

        # GBM step: S(t+1) = S(t) * exp((mu - σ²/2)*dt + σ*sqrt(dt)*Z)
        sigma = 0.001  # ~0.1% per tick
        mu = drift
        dt = 1.0
        z = random.gauss(0, 1)
        log_return = (mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z

        new_price = price * math.exp(log_return)
        self._prices[symbol] = new_price
        return new_price

    async def fetch(self, session: aiohttp.ClientSession, symbol: str) -> dict | None:
        price = self._step_price(symbol)

        # Volume from log-normal distribution
        volume = int(math.exp(random.gauss(11, 0.5)))

        # Bid/ask spread: 2-10 basis points
        spread_bps = random.uniform(2, 10)
        half_spread = price * spread_bps / 10000
        bid = round(price - half_spread, 4)
        ask = round(price + half_spread, 4)

        return {
            "symbol": symbol,
            "price": round(price, 4),
            "volume": volume,
            "bid": bid,
            "ask": ask,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
