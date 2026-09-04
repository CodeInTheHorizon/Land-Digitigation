"""SQLAlchemy ORM models – import everything here so Alembic picks them up."""

from app.models.user import User, Role, UserRole  # noqa: F401
from app.models.document import Document, DocumentPage  # noqa: F401
from app.models.processing import ProcessingJob, OCRResult  # noqa: F401
from app.models.land_record import (  # noqa: F401
    LandRecord,
    ExtractedEntity,
    Landowner,
    LandParcel,
    OwnershipRecord,
    MutationRecord,
    RegistrationRecord,
)
from app.models.review import ValidationResult, ReviewTask  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
