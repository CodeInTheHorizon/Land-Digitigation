"""Schemas for extraction pipeline results, validation, and human review."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class ClassificationResponse(BaseModel):
    """Document classification result."""

    category: str
    confidence: float
    scores: Dict[str, float] = {}
    matched_keywords: List[str] = []
    matched_headers: List[str] = []


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

class EntityResponse(BaseModel):
    """A single extracted entity with provenance."""

    entity_type: str
    value: str
    raw_text: str
    confidence: float
    extraction_method: str
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    context: Optional[str] = None
    secondary_value: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Entity extraction results for a document."""

    entities: List[EntityResponse] = []
    page_number: Optional[int] = None
    text_length: int = 0
    entity_count: int = 0


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

class FieldProvenanceResponse(BaseModel):
    """Provenance for a single mapped field."""

    field_name: str
    raw_value: str
    normalized_value: Any = None
    confidence: float
    source_entity_type: str
    extraction_method: str
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    context: Optional[str] = None


class MappedRecordResponse(BaseModel):
    """Structured land record with provenance."""

    fields: Dict[str, Any] = {}
    provenance: List[FieldProvenanceResponse] = []
    persons: List[Dict[str, Any]] = []
    unmapped_entities: List[EntityResponse] = []
    field_count: int = 0


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

class FieldConfidenceResponse(BaseModel):
    """Confidence breakdown for a single field."""

    ocr: float = 0.0
    extraction: float = 0.0
    pattern: float = 0.0
    cross_field: float = 0.0
    context: float = 0.0
    composite: float = 0.0


class ConfidenceResponse(BaseModel):
    """Full confidence breakdown for a record."""

    overall: float = 0.0
    field_count: int = 0
    low_confidence_fields: List[str] = []
    fields: Dict[str, FieldConfidenceResponse] = {}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationIssueResponse(BaseModel):
    """A single validation issue."""

    rule_name: str
    rule_type: str
    field_name: Optional[str] = None
    status: str  # passed | failed | warning | review_required
    message: str
    severity: str = "medium"
    details: Optional[Dict[str, Any]] = None


class ValidationResponse(BaseModel):
    """Aggregated validation result."""

    issues: List[ValidationIssueResponse] = []
    status: str = "pending"
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    review_count: int = 0
    is_valid: bool = False
    needs_review: bool = False


# ---------------------------------------------------------------------------
# Full extraction pipeline result
# ---------------------------------------------------------------------------

class ExtractionPipelineResponse(BaseModel):
    """Complete extraction pipeline result for a document."""

    document_id: uuid.UUID
    classification: ClassificationResponse
    extraction: ExtractionResponse
    mapped_record: MappedRecordResponse
    confidence: ConfidenceResponse
    validation: ValidationResponse
    processing_time_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Human review
# ---------------------------------------------------------------------------

class ReviewAction(BaseModel):
    """A single field review action (accept / reject / edit)."""

    field_name: str
    action: str = Field(
        ..., description="accept | reject | edit",
        pattern=r"^(accept|reject|edit)$",
    )
    new_value: Optional[str] = None
    comment: Optional[str] = None


class ReviewRequest(BaseModel):
    """Human review submission for a land record."""

    land_record_id: uuid.UUID
    actions: List[ReviewAction]
    reviewer_comment: Optional[str] = None


class ReviewLogEntry(BaseModel):
    """Audit log entry for a review action."""

    id: uuid.UUID
    land_record_id: uuid.UUID
    field_name: str
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    comment: Optional[str] = None
    reviewed_by: uuid.UUID
    reviewed_at: datetime

    model_config = {"from_attributes": True}


class ReviewLogResponse(BaseModel):
    """List of review log entries."""

    items: List[ReviewLogEntry]
    total: int
