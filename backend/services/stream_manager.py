"""WebSocket connection pool and broadcasting.

StreamManager tracks all active WebSocket connections and provides
a broadcast method used by the pipeline orchestrator to push events.
"""

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class StreamManager:
    """Manages WebSocket connections and broadcasts messages to all clients."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.info("WebSocket client connected (%d total)", self.client_count)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info("WebSocket client disconnected (%d total)", self.client_count)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to all connected clients.

        Disconnects clients that fail to receive.
        """
        if not self._connections:
            return

        payload = json.dumps(message)
        dead: list[WebSocket] = []

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)
