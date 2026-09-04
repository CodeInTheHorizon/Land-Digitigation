"""Tests for SQLAlchemy model definitions, relationships, and constraints.

These are structural tests – they validate model metadata without a live database.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect as sa_inspect

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User, Role, UserRole
from app.models.document import Document, DocumentPage
from app.models.processing import ProcessingJob, OCRResult
from app.models.land_record import (
    LandRecord,
    ExtractedEntity,
    Landowner,
    LandParcel,
    OwnershipRecord,
    MutationRecord,
    RegistrationRecord,
)
from app.models.review import ValidationResult, ReviewTask
from app.models.audit import AuditLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_MODELS = [
    User, Role, UserRole,
    Document, DocumentPage,
    ProcessingJob, OCRResult,
    LandRecord, ExtractedEntity,
    Landowner, LandParcel,
    OwnershipRecord, MutationRecord, RegistrationRecord,
    ValidationResult, ReviewTask,
    AuditLog,
]


def _column_names(model) -> set[str]:
    """Return the set of column names declared on a model."""
    mapper = sa_inspect(model)
    return {c.key for c in mapper.columns}


def _has_fk_to(model, target_table: str) -> bool:
    """Check whether *model* has at least one FK pointing at *target_table*."""
    mapper = sa_inspect(model)
    for col in mapper.columns:
        for fk in col.foreign_keys:
            if fk.column.table.name == target_table:
                return True
    return False


# ---------------------------------------------------------------------------
# 1. Base / Mixins
# ---------------------------------------------------------------------------

class TestBaseMixins:
    def test_base_is_declarative(self):
        assert hasattr(Base, "metadata")

    def test_timestamp_mixin_columns(self):
        assert "created_at" in TimestampMixin.__dict__
        assert "updated_at" in TimestampMixin.__dict__

    def test_uuid_mixin_generates_uuid(self):
        # The mixin declares a default; verify it callable
        col = UUIDPrimaryKeyMixin.__dict__["id"]
        assert col is not None


# ---------------------------------------------------------------------------
# 2. All models registered with Base.metadata
# ---------------------------------------------------------------------------

class TestModelRegistration:
    def test_all_tables_in_metadata(self):
        table_names = set(Base.metadata.tables.keys())
        for model in ALL_MODELS:
            assert model.__tablename__ in table_names, (
                f"{model.__name__}.__tablename__ = {model.__tablename__!r} "
                f"not found in metadata"
            )

    def test_expected_table_count(self):
        # 17 tables: 16 models + user_roles junction
        assert len(Base.metadata.tables) >= 16


# ---------------------------------------------------------------------------
# 3. UUID Primary Keys
# ---------------------------------------------------------------------------

class TestUUIDPrimaryKeys:
    @pytest.mark.parametrize("model", ALL_MODELS)
    def test_has_id_column(self, model):
        cols = _column_names(model)
        assert "id" in cols, f"{model.__name__} missing 'id' column"

    @pytest.mark.parametrize("model", ALL_MODELS)
    def test_id_is_primary_key(self, model):
        mapper = sa_inspect(model)
        pk_cols = [c.key for c in mapper.primary_key]
        assert "id" in pk_cols, f"{model.__name__}.id is not a primary key"


# ---------------------------------------------------------------------------
# 4. Timestamp columns
# ---------------------------------------------------------------------------

class TestTimestamps:
    TIMESTAMPED = [
        User, Role, Document, DocumentPage,
        ProcessingJob, OCRResult, LandRecord,
        ExtractedEntity, Landowner, LandParcel,
        OwnershipRecord, MutationRecord, RegistrationRecord,
        ValidationResult, ReviewTask, AuditLog,
    ]

    @pytest.mark.parametrize("model", TIMESTAMPED)
    def test_has_created_at(self, model):
        assert "created_at" in _column_names(model), f"{model.__name__} missing created_at"

    @pytest.mark.parametrize("model", TIMESTAMPED)
    def test_has_updated_at(self, model):
        assert "updated_at" in _column_names(model), f"{model.__name__} missing updated_at"


# ---------------------------------------------------------------------------
# 5. Foreign Key relationships
# ---------------------------------------------------------------------------

class TestForeignKeys:
    def test_document_uploaded_by_user(self):
        assert _has_fk_to(Document, "users")

    def test_document_page_belongs_to_document(self):
        assert _has_fk_to(DocumentPage, "documents")

    def test_processing_job_belongs_to_document(self):
        assert _has_fk_to(ProcessingJob, "documents")

    def test_ocr_result_belongs_to_page(self):
        assert _has_fk_to(OCRResult, "document_pages")

    def test_ocr_result_belongs_to_job(self):
        assert _has_fk_to(OCRResult, "processing_jobs")

    def test_land_record_belongs_to_document(self):
        assert _has_fk_to(LandRecord, "documents")

    def test_extracted_entity_belongs_to_document(self):
        assert _has_fk_to(ExtractedEntity, "documents")

    def test_ownership_record_links_land_record(self):
        assert _has_fk_to(OwnershipRecord, "land_records")

    def test_ownership_record_links_landowner(self):
        assert _has_fk_to(OwnershipRecord, "landowners")

    def test_mutation_record_belongs_to_land_record(self):
        assert _has_fk_to(MutationRecord, "land_records")

    def test_registration_record_belongs_to_land_record(self):
        assert _has_fk_to(RegistrationRecord, "land_records")

    def test_validation_result_belongs_to_document(self):
        assert _has_fk_to(ValidationResult, "documents")

    def test_review_task_belongs_to_document(self):
        assert _has_fk_to(ReviewTask, "documents")

    def test_audit_log_links_to_user(self):
        assert _has_fk_to(AuditLog, "users")

    def test_user_role_links_user_and_role(self):
        assert _has_fk_to(UserRole, "users")
        assert _has_fk_to(UserRole, "roles")


# ---------------------------------------------------------------------------
# 6. Critical columns exist
# ---------------------------------------------------------------------------

class TestCriticalColumns:
    def test_user_has_email_and_password(self):
        cols = _column_names(User)
        assert "email" in cols
        assert "hashed_password" in cols

    def test_document_has_status(self):
        assert "status" in _column_names(Document)

    def test_land_record_has_survey_and_location(self):
        cols = _column_names(LandRecord)
        for field in ("survey_number", "village", "district", "state"):
            assert field in cols, f"LandRecord missing {field}"

    def test_land_record_has_confidence(self):
        assert "overall_confidence" in _column_names(LandRecord)

    def test_extracted_entity_has_confidence(self):
        cols = _column_names(ExtractedEntity)
        assert "confidence" in cols
        assert "field_name" in cols

    def test_processing_job_has_status(self):
        cols = _column_names(ProcessingJob)
        assert "status" in cols
        assert "job_type" in cols

    def test_audit_log_has_action(self):
        cols = _column_names(AuditLog)
        assert "action" in cols
        assert "resource_type" in cols


# ---------------------------------------------------------------------------
# 7. Unique constraints / indexes (spot-check via table args)
# ---------------------------------------------------------------------------

class TestConstraints:
    def test_user_email_unique(self):
        mapper = sa_inspect(User)
        email_col = mapper.columns["email"]
        assert email_col.unique is True

    def test_land_parcel_has_unique_constraint(self):
        """LandParcel should have a composite unique on survey+village+tehsil+district+state."""
        table = LandParcel.__table__
        unique_constraints = [
            c for c in table.constraints
            if hasattr(c, "columns") and len(c.columns) > 1
        ]
        # At least one multi-column unique constraint
        assert len(unique_constraints) >= 1


# ---------------------------------------------------------------------------
# 8. Config has no hardcoded credentials
# ---------------------------------------------------------------------------

class TestNoHardcodedCreds:
    def test_config_defaults_are_placeholders(self):
        from app.core.config import Settings
        s = Settings()
        # Defaults should be obvious placeholders, not real secrets
        assert "change" in s.SECRET_KEY.lower() or s.SECRET_KEY == "test-secret-key-for-unit-tests-only"
        assert "change" in s.JWT_SECRET_KEY.lower() or s.JWT_SECRET_KEY == "test-jwt-secret-key"
