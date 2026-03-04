"""GET /api/alerts endpoint."""

from fastapi import APIRouter, Query
from typing import Optional

from backend.database import get_connection

router = APIRouter()


@router.get("/alerts")
async def list_alerts(
    limit: int = Query(50, ge=1, le=500),
    type: Optional[str] = Query(None, alias="type"),
):
    """Recent alerts and signals, optionally filtered by type."""
    conn = get_connection()
    try:
        if type:
            rows = conn.execute(
                """
                SELECT id, type, symbol, message, severity, metadata, created_at
                FROM alerts
                WHERE type = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [type, limit],
            ).fetchdf()
        else:
            rows = conn.execute(
                """
                SELECT id, type, symbol, message, severity, metadata, created_at
                FROM alerts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchdf()

        return {"alerts": rows.to_dict(orient="records")}
    finally:
        conn.close()
