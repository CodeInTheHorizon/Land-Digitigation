"""Document upload and retrieval schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from app.core.config import settings


class DocumentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    page_count: Optional[int] = None
    document_type: Optional[str] = None
    detected_language: Optional[str] = None
    status: str
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentPageResponse(BaseModel):
    id: uuid.UUID
    page_number: int
    width: Optional[int] = None
    height: Optional[int] = None
    raw_text: Optional[str] = None
    ocr_engine: Optional[str] = None
    ocr_confidence: Optional[float] = None
    detected_language: Optional[str] = None

    model_config = {"from_attributes": True}


class ProcessingJobResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    job_type: str
    status: str
    current_stage: Optional[str] = None
    pages_processed: int = 0
    entities_extracted: int = 0
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    @field_validator("error_message")
    @classmethod
    def safe_error_message(cls, value):
        if value and settings.APP_ENV == "production":
            return "Document processing failed. Please retry or contact support."
        return value

    model_config = {"from_attributes": True}
