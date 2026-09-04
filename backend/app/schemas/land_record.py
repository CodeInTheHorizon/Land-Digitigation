"""Land record, ownership, mutation, registration schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Extracted field with confidence
# ---------------------------------------------------------------------------

class ExtractedFieldResponse(BaseModel):
    field_name: str
    raw_value: str
    normalized_value: Optional[str] = None
    confidence: float
    source: str
    page_number: Optional[int] = None
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_width: Optional[int] = None
    bbox_height: Optional[int] = None
    validation_status: str = "pending"
    needs_review: bool = False

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Land Record
# ---------------------------------------------------------------------------

class LandRecordResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID

    village: Optional[str] = None
    tehsil: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    survey_number: Optional[str] = None
    khasra_number: Optional[str] = None
    khata_number: Optional[str] = None
    plot_number: Optional[str] = None
    area: Optional[float] = None
    area_unit: Optional[str] = None
    land_classification: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    remarks: Optional[str] = None

    overall_confidence: Optional[float] = None
    field_confidences: Optional[Dict[str, Any]] = None
    status: str

    owners: List["OwnershipRecordResponse"] = []
    mutations: List["MutationRecordResponse"] = []
    registrations: List["RegistrationRecordResponse"] = []

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LandRecordUpdate(BaseModel):
    """Manual corrections to a land record."""
    village: Optional[str] = None
    tehsil: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    survey_number: Optional[str] = None
    khasra_number: Optional[str] = None
    khata_number: Optional[str] = None
    plot_number: Optional[str] = None
    area: Optional[float] = None
    area_unit: Optional[str] = None
    land_classification: Optional[str] = None
    remarks: Optional[str] = None


class LandRecordListResponse(BaseModel):
    items: List[LandRecordResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Landowner
# ---------------------------------------------------------------------------

class LandownerResponse(BaseModel):
    id: uuid.UUID
    name: str
    father_or_husband_name: Optional[str] = None
    guardian_name: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LandownerListResponse(BaseModel):
    items: List[LandownerResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

class OwnershipRecordResponse(BaseModel):
    id: uuid.UUID
    landowner_id: uuid.UUID
    landowner_name: Optional[str] = None
    ownership_type: Optional[str] = None
    ownership_percentage: Optional[float] = None
    is_current: bool = True

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

class MutationRecordResponse(BaseModel):
    id: uuid.UUID
    mutation_number: Optional[str] = None
    mutation_type: Optional[str] = None
    mutation_date: Optional[date] = None
    from_owner: Optional[str] = None
    to_owner: Optional[str] = None
    order_number: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MutationListResponse(BaseModel):
    items: List[MutationRecordResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegistrationRecordResponse(BaseModel):
    id: uuid.UUID
    registration_number: Optional[str] = None
    registration_date: Optional[date] = None
    registration_office: Optional[str] = None
    transaction_type: Optional[str] = None
    consideration_amount: Optional[float] = None
    stamp_duty: Optional[float] = None
    remarks: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegistrationListResponse(BaseModel):
    items: List[RegistrationRecordResponse]
    total: int
    page: int
    page_size: int
