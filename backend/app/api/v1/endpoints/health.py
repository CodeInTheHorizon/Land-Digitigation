"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Application health check – probes DB connectivity."""
    db_status = "unknown"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version="0.1.0",
        database=db_status,
    )
