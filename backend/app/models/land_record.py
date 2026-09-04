"""Core land record domain models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# ---------------------------------------------------------------------------
# Extracted Entity (generic NER / field extraction result)
# ---------------------------------------------------------------------------

class ExtractedEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single extracted field from a document page."""

    __tablename__ = "extracted_entities"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False
    )

    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="ocr | nlp | llm | rule | manual",
    )

    # Spatial reference
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Validation
    validation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending | valid | invalid | needs_review",
    )
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# Land Record (the final structured output)
# ---------------------------------------------------------------------------

class LandRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured land record assembled from extracted entities."""

    __tablename__ = "land_records"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    # -- Location -------------------------------------------------------------
    village: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    tehsil: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # -- Identifiers ----------------------------------------------------------
    survey_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    khasra_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    khata_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    plot_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # -- Area -----------------------------------------------------------------
    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_unit: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="hectare | acre | bigha | sq_meter | sq_feet | guntha | kanal | marla",
    )

    # -- Classification -------------------------------------------------------
    land_classification: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="agricultural | residential | commercial | industrial | barren | forest | govt",
    )

    # -- Document info --------------------------------------------------------
    document_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # -- Confidence -----------------------------------------------------------
    overall_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    field_confidences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # -- Status ---------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft",
        comment="draft | validated | reviewed | finalized",
    )

    # -- Relations ------------------------------------------------------------
    document: Mapped["Document"] = relationship(back_populates="land_records")  # type: ignore[name-defined]
    owners: Mapped[List["OwnershipRecord"]] = relationship(
        back_populates="land_record", cascade="all, delete-orphan"
    )
    mutations: Mapped[List["MutationRecord"]] = relationship(
        back_populates="land_record", cascade="all, delete-orphan"
    )
    registrations: Mapped[List["RegistrationRecord"]] = relationship(
        back_populates="land_record", cascade="all, delete-orphan"
    )
    parcel_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("land_parcels.id", ondelete="SET NULL"), nullable=True
    )
    parcel: Mapped[Optional["LandParcel"]] = relationship(back_populates="land_records")


# ---------------------------------------------------------------------------
# Landowner
# ---------------------------------------------------------------------------

class Landowner(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A resolved landowner entity (may appear across multiple records)."""

    __tablename__ = "landowners"

    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    father_or_husband_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    guardian_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # De-duplication
    normalized_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, index=True)
    name_variants: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    ownership_records: Mapped[List["OwnershipRecord"]] = relationship(back_populates="landowner")


# ---------------------------------------------------------------------------
# Land Parcel (geographic entity)
# ---------------------------------------------------------------------------

class LandParcel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a unique physical land parcel."""

    __tablename__ = "land_parcels"

    survey_number: Mapped[str] = mapped_column(String(100), nullable=False)
    khasra_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    village: Mapped[str] = mapped_column(String(255), nullable=False)
    tehsil: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(255), nullable=False)

    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    land_classification: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # GeoJSON or bounding polygon (future)
    geometry: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    land_records: Mapped[List[LandRecord]] = relationship(back_populates="parcel")

    __table_args__ = (
        UniqueConstraint("survey_number", "village", "tehsil", "district", "state", name="uq_parcel_location"),
    )


# ---------------------------------------------------------------------------
# Ownership Record (join between LandRecord and Landowner)
# ---------------------------------------------------------------------------

class OwnershipRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ownership_records"

    land_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("land_records.id", ondelete="CASCADE"), nullable=False
    )
    landowner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landowners.id", ondelete="CASCADE"), nullable=False
    )

    ownership_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="sole | joint | inherited | leased | government",
    )
    ownership_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    land_record: Mapped[LandRecord] = relationship(back_populates="owners")
    landowner: Mapped[Landowner] = relationship(back_populates="ownership_records")


# ---------------------------------------------------------------------------
# Mutation Record
# ---------------------------------------------------------------------------

class MutationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "mutation_records"

    land_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("land_records.id", ondelete="CASCADE"), nullable=False
    )

    mutation_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mutation_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="sale | inheritance | partition | gift | govt_order | court_decree",
    )
    mutation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    from_owner: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    to_owner: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    order_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    land_record: Mapped[LandRecord] = relationship(back_populates="mutations")


# ---------------------------------------------------------------------------
# Registration Record
# ---------------------------------------------------------------------------

class RegistrationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "registration_records"

    land_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("land_records.id", ondelete="CASCADE"), nullable=False
    )

    registration_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    registration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    registration_office: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transaction_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="sale | mortgage | lease | gift | exchange | partition",
    )
    consideration_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stamp_duty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    parties: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    land_record: Mapped[LandRecord] = relationship(back_populates="registrations")


# ---------------------------------------------------------------------------
# Review Log (human review audit trail)
# ---------------------------------------------------------------------------

class ReviewLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit log for human review actions on extracted fields."""

    __tablename__ = "review_logs"

    land_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("land_records.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="accept | reject | edit",
    )
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    land_record: Mapped[LandRecord] = relationship()


# ---------------------------------------------------------------------------
# Extraction Result (cached pipeline output per document)
# ---------------------------------------------------------------------------

class ExtractionResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cached extraction pipeline output for a document."""

    __tablename__ = "extraction_results"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="SET NULL"), nullable=True
    )

    # Classification
    document_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    classification_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Extraction summary
    entity_count: Mapped[int] = mapped_column(Integer, default=0)
    field_count: Mapped[int] = mapped_column(Integer, default=0)
    mapped_fields: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    persons: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Confidence
    overall_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    field_confidences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Validation
    validation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending",
        comment="passed | failed | warning | review_required",
    )
    validation_issues: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    # Provenance
    provenance: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Processing
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
