"""Land record CRUD and search endpoints."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.land_record import (
    LandRecord,
    Landowner,
    MutationRecord,
    OwnershipRecord,
    RegistrationRecord,
)
from app.models.user import User
from app.schemas.land_record import (
    LandRecordListResponse,
    LandRecordResponse,
    LandRecordUpdate,
    LandownerListResponse,
    LandownerResponse,
    MutationListResponse,
    RegistrationListResponse,
)

router = APIRouter(prefix="/land-records", tags=["Land Records"])


@router.get("", response_model=LandRecordListResponse)
async def list_land_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    district: Optional[str] = None,
    tehsil: Optional[str] = None,
    village: Optional[str] = None,
    survey_number: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    document_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List land records with filtering and search."""
    query = (
        select(LandRecord)
        .join(Document)
        .where(Document.uploaded_by == current_user.id)
        .options(
            selectinload(LandRecord.owners).selectinload(OwnershipRecord.landowner),
            selectinload(LandRecord.mutations),
            selectinload(LandRecord.registrations),
        )
    )

    if district:
        query = query.where(LandRecord.district.ilike(f"%{district}%"))
    if tehsil:
        query = query.where(LandRecord.tehsil.ilike(f"%{tehsil}%"))
    if village:
        query = query.where(LandRecord.village.ilike(f"%{village}%"))
    if survey_number:
        query = query.where(LandRecord.survey_number == survey_number)
    if status_filter:
        query = query.where(LandRecord.status == status_filter)
    if search:
        query = query.where(
            or_(
                LandRecord.village.ilike(f"%{search}%"),
                LandRecord.district.ilike(f"%{search}%"),
                LandRecord.survey_number.ilike(f"%{search}%"),
                LandRecord.khasra_number.ilike(f"%{search}%"),
            )
        )
    if document_id:
        query = query.where(LandRecord.document_id == document_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(LandRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    records = result.scalars().unique().all()

    return LandRecordListResponse(items=records, total=total, page=page, page_size=page_size)


@router.get("/{record_id}", response_model=LandRecordResponse)
async def get_land_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single land record with all related data."""
    result = await db.execute(
        select(LandRecord)
        .join(Document)
        .where(LandRecord.id == record_id, Document.uploaded_by == current_user.id)
        .options(
            selectinload(LandRecord.owners).selectinload(OwnershipRecord.landowner),
            selectinload(LandRecord.mutations),
            selectinload(LandRecord.registrations),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Land record not found")
    return record


@router.patch("/{record_id}", response_model=LandRecordResponse)
async def update_land_record(
    record_id: uuid.UUID,
    body: LandRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update land record fields (manual correction)."""
    result = await db.execute(
        select(LandRecord)
        .join(Document)
        .where(LandRecord.id == record_id, Document.uploaded_by == current_user.id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Land record not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    await db.flush()
    await db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Landowners
# ---------------------------------------------------------------------------

@router.get("/landowners/all", response_model=LandownerListResponse)
async def list_landowners(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all landowners."""
    query = select(Landowner)
    if search:
        query = query.where(
            or_(
                Landowner.name.ilike(f"%{search}%"),
                Landowner.normalized_name.ilike(f"%{search}%"),
            )
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Landowner.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    owners = result.scalars().all()

    return LandownerListResponse(items=owners, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

@router.get("/mutations/all", response_model=MutationListResponse)
async def list_mutations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all mutation records."""
    query = (
        select(MutationRecord)
        .join(LandRecord)
        .join(Document)
        .where(Document.uploaded_by == current_user.id)
    )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(MutationRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    mutations = result.scalars().all()

    return MutationListResponse(items=mutations, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Registrations
# ---------------------------------------------------------------------------

@router.get("/registrations/all", response_model=RegistrationListResponse)
async def list_registrations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all registration records."""
    query = (
        select(RegistrationRecord)
        .join(LandRecord)
        .join(Document)
        .where(Document.uploaded_by == current_user.id)
    )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(RegistrationRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    regs = result.scalars().all()

    return RegistrationListResponse(items=regs, total=total, page=page, page_size=page_size)
