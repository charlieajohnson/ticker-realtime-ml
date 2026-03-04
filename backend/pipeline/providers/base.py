"""Abstract base class for data providers."""

from abc import ABC, abstractmethod

import aiohttp


class Provider(ABC):
    """Base class for market data providers.

    Each provider implements `fetch()` to return a single tick dict:
        {"symbol", "price", "volume", "bid", "ask", "timestamp"}
    or None on failure.
    """

    @abstractmethod
    async def fetch(self, session: aiohttp.ClientSession, symbol: str) -> dict | None:
        ...
