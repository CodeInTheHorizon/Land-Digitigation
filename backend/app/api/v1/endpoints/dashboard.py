"""Dashboard statistics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.land_record import LandRecord, Landowner, MutationRecord, RegistrationRecord
from app.models.review import ReviewTask
from app.models.user import User
from app.schemas.common import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate dashboard statistics for the current user."""
    user_docs = select(Document.id).where(Document.uploaded_by == current_user.id).subquery()

    # Document counts
    total_docs = (await db.execute(
        select(func.count()).select_from(Document).where(Document.uploaded_by == current_user.id)
    )).scalar() or 0

    processed = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.uploaded_by == current_user.id, Document.status == "processed"
        )
    )).scalar() or 0

    pending = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.uploaded_by == current_user.id, Document.status.in_(["uploaded", "processing"])
        )
    )).scalar() or 0

    failed = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.uploaded_by == current_user.id, Document.status == "failed"
        )
    )).scalar() or 0

    # Record counts
    total_records = (await db.execute(
        select(func.count()).select_from(LandRecord).where(LandRecord.document_id.in_(select(user_docs)))
    )).scalar() or 0

    total_owners = (await db.execute(select(func.count()).select_from(Landowner))).scalar() or 0

    total_mutations = (await db.execute(
        select(func.count()).select_from(MutationRecord)
        .join(LandRecord)
        .where(LandRecord.document_id.in_(select(user_docs)))
    )).scalar() or 0

    total_regs = (await db.execute(
        select(func.count()).select_from(RegistrationRecord)
        .join(LandRecord)
        .where(LandRecord.document_id.in_(select(user_docs)))
    )).scalar() or 0

    # Pending reviews
    pending_reviews = (await db.execute(
        select(func.count()).select_from(ReviewTask).where(
            ReviewTask.document_id.in_(select(user_docs)),
            ReviewTask.status == "pending",
        )
    )).scalar() or 0

    # Average confidence
    avg_conf = (await db.execute(
        select(func.avg(LandRecord.overall_confidence)).where(
            LandRecord.document_id.in_(select(user_docs)),
            LandRecord.overall_confidence.isnot(None),
        )
    )).scalar()

    # Docs by type
    type_rows = (await db.execute(
        select(Document.document_type, func.count())
        .where(Document.uploaded_by == current_user.id, Document.document_type.isnot(None))
        .group_by(Document.document_type)
    )).all()
    docs_by_type = {row[0]: row[1] for row in type_rows}

    # Docs by language
    lang_rows = (await db.execute(
        select(Document.detected_language, func.count())
        .where(Document.uploaded_by == current_user.id, Document.detected_language.isnot(None))
        .group_by(Document.detected_language)
    )).all()
    docs_by_lang = {row[0]: row[1] for row in lang_rows}

    return DashboardStats(
        total_documents=total_docs,
        documents_processed=processed,
        documents_pending=pending,
        documents_failed=failed,
        total_land_records=total_records,
        total_landowners=total_owners,
        total_mutations=total_mutations,
        total_registrations=total_regs,
        pending_reviews=pending_reviews,
        avg_confidence=round(avg_conf, 3) if avg_conf else None,
        documents_by_type=docs_by_type,
        documents_by_language=docs_by_lang,
    )
