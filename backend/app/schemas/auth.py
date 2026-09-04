"""Authentication and user schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    roles: List[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
