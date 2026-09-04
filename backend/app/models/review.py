"""Validation results and human review task models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ValidationResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Result of running validation rules on a land record or entity."""

    __tablename__ = "validation_results"

    land_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("land_records.id", ondelete="CASCADE"), nullable=True
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extracted_entities.id", ondelete="CASCADE"), nullable=True
    )

    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="format | range | required | consistency | llm_reasoning | cross_reference",
    )
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="passed | failed | warning | skipped",
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium",
        comment="low | medium | high | critical",
    )


class ReviewTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A task for a human reviewer to verify or correct extracted data."""

    __tablename__ = "review_tasks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    land_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("land_records.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="low_confidence | validation_failure | manual_entry | conflict_resolution",
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending",
        comment="pending | in_progress | completed | skipped",
    )

    # What needs review
    fields_to_review: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    original_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    corrected_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
