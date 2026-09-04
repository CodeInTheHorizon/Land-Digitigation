"""User, Role, and UserRole models."""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Table, Column, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    users: Mapped[List["User"]] = relationship(
        secondary="user_roles", back_populates="roles"
    )


class UserRole(Base, TimestampMixin):
    """Association table for many-to-many user ↔ role."""
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    roles: Mapped[List[Role]] = relationship(
        secondary="user_roles", back_populates="users", lazy="selectin"
    )
    documents: Mapped[List["Document"]] = relationship(back_populates="uploaded_by_user")  # type: ignore[name-defined]
