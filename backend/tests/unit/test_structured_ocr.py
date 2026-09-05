"""English/Hindi extraction and pipeline regressions; no external OCR service."""

import io
import json
from unittest.mock import AsyncMock

import numpy as np
import pytest
from PIL import Image

from app.services.extraction.extraction_pipeline import ExtractionPipeline
from app.services.ocr import OCRBlock, OCRPageResult


ENGLISH = """Owner: Ram Singh
Father: Mohan Singh
Address: 12 Main Road, Lucknow
Survey No: 123 / 4-A
Village: Rampur
Tehsil: Sadar
District: Lucknow
Area: 2.5 hectare
Crop: Wheat"""
HINDI = """भूमिस्वामी का नाम: राम सिंह पुत्र मोहन सिंह
खसरा: १२३/४
खाता: ४५
ग्राम: रामपुर
जिला: लखनऊ
रकबा: २.५ हेक्टेयर
फसल: गेहूं"""


def extract(text):
    result = ExtractionPipeline().extract(text, ocr_confidence=0.9)
    assert not result.errors
    return result


def test_english_labeled_fields_and_owner_relationship():
    data = extract(ENGLISH).structured_data
    assert data["survey_number"] == "123/4-A"
    assert data["owner_details"] == [{"name": "Ram Singh", "father_or_husband_name": "Mohan Singh", "address": "12 Main Road, Lucknow"}]
    assert data["area"] == {"value": 2.5, "unit": "hectare"}
    assert data["additional_fields"]["Crop"] == ["Wheat"]
    assert data["state"] is None
    assert data["khasra_number"] is None
    assert data["raw_text"] == ENGLISH


def test_hindi_original_text_and_digits():
    data = extract(HINDI).structured_data
    assert data["owner_details"][0]["name"] == "राम सिंह"
    assert data["owner_details"][0]["father_or_husband_name"] == "मोहन सिंह"
    assert data["khasra_number"] == "123/4"
    assert data["khata_number"] == "45"
    assert data["village"] == "रामपुर"
    assert data["additional_fields"]["फसल"] == ["गेहूं"]
    assert data["raw_text"] == HINDI
    assert "राम सिंह" in json.dumps(data, ensure_ascii=False)


def test_split_labels_and_vertical_pairs():
    data = extract("S u r v e y N o: 12-3/A\nVillage\nRampur\nDistrict: Lucknow").structured_data
    assert data["survey_number"] == "12-3/A"
    assert data["village"] == "Rampur"


def test_unknown_label_is_not_forced_into_a_known_prefix():
    data = extract("Village code: 123\nCrop: Wheat; District: Lucknow").structured_data
    assert data["village"] is None
    assert data["additional_fields"]["Village code"] == ["123"]
    assert data["additional_fields"]["Crop"] == ["Wheat"]
    assert data["district"] == "Lucknow"


def test_table_and_multiple_owners():
    data = extract("Owner | Father | Khasra No\nRam Singh | Mohan Singh | 12/4\nSita Devi | Hari Singh | 12/4").structured_data
    assert [p["name"] for p in data["owner_details"]] == ["Ram Singh", "Sita Devi"]
    assert data["khasra_number"] == "12/4"


def test_conflicts_are_not_silently_assigned():
    result = extract("Survey No: 123\nSurvey No: 456")
    assert result.structured_data["survey_number"] is None
    assert result.structured_data["additional_fields"]["survey_number_candidates"] == ["123", "456"]
    assert any("Conflicting survey_number" in warning for warning in result.warnings)


def test_blank_and_garbage_do_not_become_fields():
    result = extract("Owner: 12345\nVillage: 9876\nKhata: ???\nDistrict: Lucknow")
    assert result.structured_data["owner_details"][0]["name"] is None
    assert result.structured_data["village"] is None
    assert result.structured_data["khata_number"] is None
    assert result.structured_data["district"] == "Lucknow"
    assert result.warnings


def test_empty_document_has_null_values_and_warning():
    result = extract("")
    assert result.structured_data["survey_number"] is None
    assert result.structured_data["area"]["value"] is None
    assert result.structured_data["owner_details"] == []
    assert result.warnings


def test_unlabeled_date_is_not_registration():
    data = extract("Inspection: 15/03/2023").structured_data
    assert data["registration_details"]["registration_date"] is None
    data = extract("SALE DEED\nRegistration No: 123\nDate of birth: 15/03/1990").structured_data
    assert data["registration_details"]["registration_date"] is None


def test_owner_does_not_swallow_next_line():
    data = extract("Owner:\nVillage: Rampur\nDistrict: Lucknow").structured_data
    assert not any(p["name"] for p in data["owner_details"])
    assert data["village"] == "Rampur"


def test_orientation_requires_confident_osd(monkeypatch):
    import pytesseract
    from app.services.preprocessing import DocumentPreprocessor
    image = np.arange(6, dtype=np.uint8).reshape(2, 3)
    monkeypatch.setattr(pytesseract, "image_to_osd", lambda *a, **kw: {"rotate": 90, "orientation_conf": 18})
    corrected, rotation = DocumentPreprocessor._correct_orientation(image)
    assert rotation == 90
    np.testing.assert_array_equal(corrected, np.rot90(image, -1))
    monkeypatch.setattr(pytesseract, "image_to_osd", lambda *a, **kw: {"rotate": 90, "orientation_conf": 2})
    unchanged, rotation = DocumentPreprocessor._correct_orientation(image)
    assert rotation == 0
    np.testing.assert_array_equal(unchanged, image)


def test_bounded_upscaling_and_gentle_handwriting():
    from app.services.preprocessing import DocumentPreprocessor
    preprocessor = DocumentPreprocessor()
    image = np.full((100, 200), 180, dtype=np.uint8)
    assert preprocessor._normalise_resolution(image, 1).shape == (200, 400)
    result = preprocessor.preprocess_for_handwriting(image)
    assert "threshold" not in result.operations_applied
    assert "morphological_close" not in result.operations_applied


def page_text(text):
    return OCRPageResult(page_number=1, full_text=text, avg_confidence=0.9,
                         blocks=[OCRBlock(text=text, confidence=0.9)])


@pytest.mark.asyncio
@pytest.mark.parametrize("text,language", [(ENGLISH, "en"), (HINDI, "hi")])
async def test_image_to_structured_result_with_mocked_engine(text, language):
    from app.services.pipeline import DocumentPipeline
    image = Image.new("RGB", (100, 150), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    pipeline = DocumentPipeline()
    pipeline.ocr_service.recognize_page = AsyncMock(side_effect=lambda *a, **kw: page_text(text))
    result = await pipeline.process(buffer.getvalue(), mime_type="image/png")
    assert len(result.pages) == 1
    assert result.primary_language == language
    assert extract(result.full_text).structured_data["raw_text"] == text


@pytest.mark.asyncio
async def test_mixed_pages_do_not_inherit_first_language():
    from app.services.pipeline import DocumentPipeline
    pipeline = DocumentPipeline()
    image = np.full((30, 40), 255, dtype=np.uint8)
    pipeline._extract_pages = lambda *a: iter([(image, 300), (image, 300)])
    pipeline.ocr_service.recognize_page = AsyncMock(side_effect=[page_text(ENGLISH), page_text(ENGLISH), page_text(HINDI), page_text(HINDI)])
    result = await pipeline.process(b"fixture")
    assert result.primary_language == "mixed"
    assert [page.ocr_result.detected_language for page in result.pages] == ["en", "hi"]


@pytest.mark.asyncio
async def test_lazy_page_failure_preserves_completed_pages():
    from app.services.pipeline import DocumentPipeline
    pipeline = DocumentPipeline()
    def pages(*args):
        yield np.full((30, 40), 255, dtype=np.uint8), 300
        raise ValueError("bad second page")
    pipeline._extract_pages = pages
    pipeline.ocr_service.recognize_page = AsyncMock(side_effect=lambda *a, **kw: page_text(ENGLISH))
    result = await pipeline.process(b"fixture")
    assert result.full_text == ENGLISH
    assert result.errors


@pytest.mark.asyncio
async def test_unknown_language_uses_configured_multilingual_fallback(monkeypatch):
    from app.services.pipeline import DocumentPipeline
    from app.core.config import settings
    monkeypatch.setattr(settings, "OCR_LANGUAGES", "eng,hin")
    pipeline = DocumentPipeline()
    pipeline.ocr_service.recognize_page = AsyncMock(side_effect=[page_text(""), page_text("")])
    await pipeline._process_page(np.full((30, 40), 255, dtype=np.uint8), page_number=1, dpi=300)
    assert pipeline.ocr_service.recognize_page.call_args.kwargs["languages"] == "eng+hin"


@pytest.mark.asyncio
async def test_empty_primary_uses_fallback(monkeypatch):
    from types import SimpleNamespace
    from app.services.ocr.ocr_service import OCRService
    from app.core.config import settings
    monkeypatch.setattr(settings, "OCR_PRIMARY_ENGINE", "primary_fixture")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ENGINE", "fallback_fixture")
    service = OCRService()
    service._engines["primary_fixture"] = SimpleNamespace(name="primary_fixture", recognize=AsyncMock(return_value=page_text("")))
    service._engines["fallback_fixture"] = SimpleNamespace(name="fallback_fixture", recognize=AsyncMock(return_value=page_text(HINDI)))
    result = await service.recognize_page(np.zeros((20, 20), dtype=np.uint8), 1, languages="eng+hin")
    assert result.full_text == HINDI


def test_low_confidence_raw_text_is_preserved(monkeypatch):
    from app.services.ocr.ocr_service import OCRService
    from app.core.config import settings
    monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.5)
    result = OCRService._filter_low_confidence(OCRPageResult(page_number=1, full_text="uncertain original text",
        blocks=[OCRBlock(text="uncertain", confidence=0.1)]))
    assert result.full_text == "uncertain original text"
    assert result.avg_confidence == 0


@pytest.mark.asyncio
async def test_upload_and_structured_api_response(tmp_path, monkeypatch):
    import uuid
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.main import app
    from app.db.base import Base
    from app.db.session import get_db
    from app.core.dependencies import get_current_user
    from app.models.user import User
    from app.models.document import Document, DocumentPage
    from app.models.land_record import ExtractionResult
    from app.services.storage import LocalStorageService
    from app.api.v1.endpoints import documents

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user = User(id=uuid.uuid4(), email="fixture@example.test", full_name="Fixture", hashed_password="test-only")
    async with sessions() as db:
        db.add(user)
        await db.commit()
    async def test_db():
        async with sessions() as db:
            yield db
            await db.commit()
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(documents, "get_storage_service", lambda: LocalStorageService(str(tmp_path / "uploads")))
    try:
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/api/v1/documents/upload", files={"file": ("bad.exe", b"data")})).status_code == 400
            assert (await client.post("/api/v1/documents/upload", files={"file": ("empty.png", b"")})).status_code == 400
            upload = await client.post("/api/v1/documents/upload", files={"file": ("record.png", buffer.getvalue(), "image/png")})
            assert upload.status_code == 201
            document_id = uuid.UUID(upload.json()["id"])
            result = extract(HINDI)
            async with sessions() as db:
                doc = await db.get(Document, document_id)
                doc.detected_language = "hi"
                doc.processing_metadata = {"structured_data": result.structured_data, "warnings": []}
                db.add(DocumentPage(document_id=document_id, page_number=1, raw_text=HINDI))
                db.add(ExtractionResult(document_id=document_id, mapped_fields=result.mapped_record.fields,
                    persons=result.mapped_record.persons, document_category="khasra"))
                await db.commit()
            response = await client.get(f"/api/v1/extraction/{document_id}")
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert body["detected_language"] == "hi"
            assert body["structured_data"]["document_language"] == "hi"
            assert body["structured_data"]["khasra_number"] == "123/4"
            assert body["structured_data"]["survey_number"] is None
            assert body["raw_text"] == HINDI
            assert "mapped_record" in body  # Backward compatibility.
            assert list((tmp_path / "uploads").rglob("*.png"))
            app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
            assert (await client.get(f"/api/v1/extraction/{document_id}")).status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        await engine.dispose()
