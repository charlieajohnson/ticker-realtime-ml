"""WebSocket endpoint /ws/stream.

Clients connect here to receive real-time tick, prediction, alert,
and pipeline_status events broadcast by the pipeline orchestrator.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    """Accept a WebSocket connection and keep it alive for streaming."""
    manager = ws.app.state.stream_manager

    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive; ignore client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
