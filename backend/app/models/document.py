"""Document and DocumentPage models."""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import JSONType, Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents an uploaded document (PDF, image, etc.)."""

    __tablename__ = "documents"

    # -- Metadata --------------------------------------------------------------
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # -- Classification --------------------------------------------------------
    document_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True,
        comment="e.g. khasra, khatauni, mutation_order, sale_deed, map",
    )
    detected_language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # -- Processing state ------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="uploaded", index=True,
        comment="uploaded | processing | processed | failed | reviewed",
    )
    processing_metadata: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)

    # -- Owner -----------------------------------------------------------------
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    uploaded_by_user: Mapped["User"] = relationship(back_populates="documents")  # type: ignore[name-defined]

    # -- Relations -------------------------------------------------------------
    pages: Mapped[List["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number"
    )
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship(back_populates="document")  # type: ignore[name-defined]
    land_records: Mapped[List["LandRecord"]] = relationship(back_populates="document")  # type: ignore[name-defined]


class DocumentPage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One page of a multi-page document."""

    __tablename__ = "document_pages"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_storage_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dpi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # -- OCR output per page ---------------------------------------------------
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_engine: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detected_language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    document: Mapped[Document] = relationship(back_populates="pages")
    ocr_results: Mapped[List["OCRResult"]] = relationship(back_populates="page")  # type: ignore[name-defined]
