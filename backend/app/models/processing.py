"""Processing job and OCR result models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProcessingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks a single processing run for a document (or re-processing)."""

    __tablename__ = "processing_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="full_pipeline | ocr_only | revalidation | reextraction",
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="queued", index=True,
        comment="queued | running | completed | failed | cancelled",
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pipeline stage tracking
    current_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    stage_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Stats
    pages_processed: Mapped[int] = mapped_column(Integer, default=0)
    entities_extracted: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="processing_jobs")  # type: ignore[name-defined]


class OCRResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores granular OCR output (per-block or per-line) with bounding boxes."""

    __tablename__ = "ocr_results"

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False
    )

    # -- OCR engine info -------------------------------------------------------
    ocr_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    detected_language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # -- Extracted text --------------------------------------------------------
    block_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="text",
        comment="text | table | header | footer | handwriting | stamp",
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # -- Spatial info ----------------------------------------------------------
    bbox_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # -- Extra metadata --------------------------------------------------------
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    page: Mapped["DocumentPage"] = relationship(back_populates="ocr_results")  # type: ignore[name-defined]
