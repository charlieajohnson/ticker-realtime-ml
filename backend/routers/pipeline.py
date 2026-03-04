"""GET /api/pipeline/status endpoint."""

from fastapi import APIRouter

from backend.database import get_connection

router = APIRouter()

_STAGES = ["ingest", "transform", "feature", "inference", "serve"]


@router.get("/pipeline/status")
async def pipeline_status():
    """Pipeline health dashboard data — latest metrics per stage."""
    conn = get_connection()

    stages = []
    for stage_name in _STAGES:
        row = conn.execute(
            """
            SELECT throughput, latency_p50, latency_p99, error_count, recorded_at
            FROM pipeline_metrics
            WHERE stage = ?
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            [stage_name],
        ).fetchone()

        if row:
            stages.append({
                "name": stage_name,
                "status": "active",
                "throughput": row[0] or 0,
                "latency_p50_ms": round(row[1] or 0, 2),
                "latency_p99_ms": round(row[2] or 0, 2),
                "error_count": row[3] or 0,
            })
        else:
            stages.append({
                "name": stage_name,
                "status": "idle",
                "throughput": 0,
                "latency_p50_ms": 0,
                "latency_p99_ms": 0,
                "error_count": 0,
            })

    # Total ticks
    tick_count = conn.execute("SELECT COUNT(*) FROM ticks").fetchone()
    total_ticks = tick_count[0] if tick_count else 0

    # Uptime estimate: ratio of non-error metrics
    total_row = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN error_count = 0 THEN 1 ELSE 0 END) FROM pipeline_metrics"
    ).fetchone()
    if total_row and total_row[0] > 0:
        uptime = round(total_row[1] / total_row[0], 4)
    else:
        uptime = 1.0

    return {
        "stages": stages,
        "uptime": uptime,
        "total_ticks": total_ticks,
    }
