"""Shared response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
    errors: Optional[list[dict[str, Any]]] = None


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    database: str = "unknown"
    redis: str = "unknown"
    storage: str = "unknown"


class DashboardStats(BaseModel):
    total_documents: int = 0
    documents_processed: int = 0
    documents_pending: int = 0
    documents_failed: int = 0
    total_land_records: int = 0
    total_landowners: int = 0
    total_mutations: int = 0
    total_registrations: int = 0
    pending_reviews: int = 0
    avg_confidence: Optional[float] = None
    documents_by_type: dict[str, int] = {}
    documents_by_language: dict[str, int] = {}
    recent_activity: list[dict[str, Any]] = []
