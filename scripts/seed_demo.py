"""Insert clearly synthetic demo records without touching existing application data."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base import Base
from app.models import Document, LandRecord, Landowner, OwnershipRecord, MutationRecord, RegistrationRecord
from app.models.user import User
from app.core.security import get_password_hash

engine = create_engine(settings.SYNC_DATABASE_URL)
Base.metadata.create_all(engine)
with Session(engine) as db:
    user = db.scalar(select(User).where(User.email == "demo@example.com"))
    if not user:
        user = User(email="demo@example.com", full_name="Synthetic Demo Operator", hashed_password=get_password_hash("Demo1234!"), is_active=True)
        db.add(user); db.flush()
    if not db.scalar(select(Document).where(Document.original_filename == "SYNTHETIC_demo_english.txt")):
        for filename, language, owner_name, survey, village in [
            ("SYNTHETIC_demo_english.txt", "en", "Ramesh Kumar", "42/7", "Rampur"),
            ("SYNTHETIC_demo_hindi.txt", "hi", "रमेश कुमार", "18/2", "रामपुर"),
        ]:
            doc = Document(original_filename=filename, safe_filename=filename, mime_type="text/plain", file_size_bytes=0, storage_path=f"demo/{filename}", status="review_needed", detected_language=language, document_type="ownership_record", uploaded_by=user.id)
            db.add(doc); db.flush()
            owner = Landowner(name=owner_name, normalized_name=owner_name.casefold())
            db.add(owner); db.flush()
            record = LandRecord(document_id=doc.id, village=village, tehsil="Demo Tehsil", district="Demo District", state="Demo State", survey_number=survey, khasra_number=survey, khata_number="K-100", plot_number="P-1", area=2.5, area_unit="acre", document_type="ownership_record", overall_confidence=0.91, status="draft")
            db.add(record); db.flush()
            db.add(OwnershipRecord(land_record_id=record.id, landowner_id=owner.id, ownership_type="sole", ownership_percentage=100, is_current=True))
            db.add(MutationRecord(land_record_id=record.id, mutation_number="M-2024-01", mutation_type="sale"))
            db.add(RegistrationRecord(land_record_id=record.id, registration_number="REG-2024-01", transaction_type="sale"))
    db.commit()
print("Synthetic demo data is ready: demo@example.com / Demo1234!")
