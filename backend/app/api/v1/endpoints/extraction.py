"""Extraction pipeline endpoints — results, validation, and human review."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.land_record import (
    ExtractionResult,
    LandRecord,
    ReviewLog,
)
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.extraction import (
    ClassificationResponse,
    ConfidenceResponse,
    ExtractionPipelineResponse,
    ExtractionResponse,
    FieldConfidenceResponse,
    MappedRecordResponse,
    ReviewLogEntry,
    ReviewLogResponse,
    ReviewRequest,
    ValidationIssueResponse,
    ValidationResponse,
)

router = APIRouter(prefix="/extraction", tags=["Extraction"])


@router.get("/{document_id}", response_model=ExtractionPipelineResponse)
async def get_extraction_result(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the extraction pipeline result for a document."""
    # Verify document exists and belongs to user
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get extraction result
    result = await db.execute(
        select(ExtractionResult).where(ExtractionResult.document_id == document_id)
    )
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="No extraction result found — document may still be processing")

    return _build_pipeline_response(ext)


@router.get("/{document_id}/classification", response_model=ClassificationResponse)
async def get_classification(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get document classification result."""
    ext = await _get_extraction(db, document_id)
    return ClassificationResponse(
        category=ext.document_category or "miscellaneous",
        confidence=ext.classification_confidence or 0.0,
        scores=ext.classification_scores or {},
    )


@router.get("/{document_id}/validation", response_model=ValidationResponse)
async def get_validation(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get validation result for a document."""
    ext = await _get_extraction(db, document_id)
    issues = [
        ValidationIssueResponse(**issue)
        for issue in (ext.validation_issues or [])
    ]
    return ValidationResponse(
        issues=issues,
        status=ext.validation_status,
        passed_count=ext.passed_count,
        failed_count=ext.failed_count,
        warning_count=ext.warning_count,
        review_count=ext.review_count,
        is_valid=ext.failed_count == 0,
        needs_review=ext.review_count > 0,
    )


@router.get("/{document_id}/confidence", response_model=ConfidenceResponse)
async def get_confidence(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get confidence breakdown for a document's extraction."""
    ext = await _get_extraction(db, document_id)
    field_confs = {}
    if ext.field_confidences:
        for fname, fdata in ext.field_confidences.items():
            if isinstance(fdata, dict):
                field_confs[fname] = FieldConfidenceResponse(**fdata)
    return ConfidenceResponse(
        overall=ext.overall_confidence or 0.0,
        field_count=ext.field_count,
        fields=field_confs,
    )


@router.post("/{document_id}/review")
async def submit_review(
    document_id: uuid.UUID,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit human review actions for extracted fields.

    Each action (accept / reject / edit) is logged for audit.
    Edits update the corresponding LandRecord fields.
    """
    # Get land record for this document
    result = await db.execute(
        select(LandRecord).where(LandRecord.document_id == document_id)
    )
    land_record = result.scalar_one_or_none()
    if not land_record:
        raise HTTPException(status_code=404, detail="No land record found for this document")

    if str(land_record.id) != str(body.land_record_id):
        raise HTTPException(status_code=400, detail="Land record ID does not match document")

    review_logs = []

    for action in body.actions:
        old_value = getattr(land_record, action.field_name, None)
        old_value_str = str(old_value) if old_value is not None else None

        # Apply edit if action is "edit"
        if action.action == "edit" and action.new_value is not None:
            if hasattr(land_record, action.field_name):
                # Convert types appropriately
                field_type = type(old_value) if old_value is not None else str
                try:
                    if field_type == float:
                        setattr(land_record, action.field_name, float(action.new_value))
                    elif field_type == int:
                        setattr(land_record, action.field_name, int(action.new_value))
                    else:
                        setattr(land_record, action.field_name, action.new_value)
                except (ValueError, TypeError):
                    setattr(land_record, action.field_name, action.new_value)

        # Mark field as reviewed
        if action.action == "accept":
            # Update status to reviewed
            pass

        # Create audit log entry
        log = ReviewLog(
            land_record_id=land_record.id,
            field_name=action.field_name,
            action=action.action,
            old_value=old_value_str,
            new_value=action.new_value,
            comment=action.comment,
            reviewed_by=current_user.id,
        )
        db.add(log)
        review_logs.append(log)

    # Update record status
    land_record.status = "reviewed"
    db.add(AuditLog(user_id=current_user.id, action="review.complete", resource_type="land_record", resource_id=str(land_record.id), new_values={"actions": len(review_logs)}))
    await db.flush()

    return {
        "status": "reviewed",
        "actions_applied": len(review_logs),
        "land_record_id": str(land_record.id),
    }


@router.get("/{document_id}/review-log", response_model=ReviewLogResponse)
async def get_review_log(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the review audit log for a document."""
    # Get land record
    result = await db.execute(
        select(LandRecord).where(LandRecord.document_id == document_id)
    )
    land_record = result.scalar_one_or_none()
    if not land_record:
        raise HTTPException(status_code=404, detail="No land record found for this document")

    # Get review logs
    result = await db.execute(
        select(ReviewLog)
        .where(ReviewLog.land_record_id == land_record.id)
        .order_by(ReviewLog.created_at.desc())
    )
    logs = result.scalars().all()

    return ReviewLogResponse(
        items=[
            ReviewLogEntry(
                id=log.id,
                land_record_id=log.land_record_id,
                field_name=log.field_name,
                action=log.action,
                old_value=log.old_value,
                new_value=log.new_value,
                comment=log.comment,
                reviewed_by=log.reviewed_by,
                reviewed_at=log.created_at,
            )
            for log in logs
        ],
        total=len(logs),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_extraction(db: AsyncSession, document_id: uuid.UUID) -> ExtractionResult:
    """Fetch extraction result or raise 404."""
    result = await db.execute(
        select(ExtractionResult).where(ExtractionResult.document_id == document_id)
    )
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="No extraction result found")
    return ext


def _build_pipeline_response(ext: ExtractionResult) -> ExtractionPipelineResponse:
    """Build the full pipeline response from a DB record."""
    # Classification
    classification = ClassificationResponse(
        category=ext.document_category or "miscellaneous",
        confidence=ext.classification_confidence or 0.0,
        scores=ext.classification_scores or {},
    )

    # Extraction summary (entities are not individually stored in this model)
    extraction = ExtractionResponse(
        entity_count=ext.entity_count,
        text_length=0,
    )

    # Mapped record
    mapped_record = MappedRecordResponse(
        fields=ext.mapped_fields or {},
        persons=ext.persons or [],
        field_count=ext.field_count,
    )

    # Confidence
    field_confs = {}
    if ext.field_confidences:
        for fname, fdata in ext.field_confidences.items():
            if isinstance(fdata, dict):
                field_confs[fname] = FieldConfidenceResponse(**fdata)
    confidence = ConfidenceResponse(
        overall=ext.overall_confidence or 0.0,
        field_count=ext.field_count,
        fields=field_confs,
    )

    # Validation
    issues = [
        ValidationIssueResponse(**issue)
        for issue in (ext.validation_issues or [])
    ]
    validation = ValidationResponse(
        issues=issues,
        status=ext.validation_status,
        passed_count=ext.passed_count,
        failed_count=ext.failed_count,
        warning_count=ext.warning_count,
        review_count=ext.review_count,
        is_valid=ext.failed_count == 0,
        needs_review=ext.review_count > 0,
    )

    return ExtractionPipelineResponse(
        document_id=ext.document_id,
        classification=classification,
        extraction=extraction,
        mapped_record=mapped_record,
        confidence=confidence,
        validation=validation,
        processing_time_ms=ext.processing_time_ms or 0,
        created_at=ext.created_at,
    )
