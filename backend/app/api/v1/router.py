"""Aggregate all v1 API routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.dashboard import router as dashboard_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.extraction import router as extraction_router
from app.api.v1.endpoints.land_records import router as land_records_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(land_records_router)
api_router.include_router(dashboard_router)
api_router.include_router(extraction_router)
