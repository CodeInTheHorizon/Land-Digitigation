"""Tests for OCR service abstraction – engine interface, service orchestration.

Tests use mock engines to avoid requiring Tesseract / EasyOCR installed.
"""

import numpy as np
import pytest
from app.core.config import settings

from app.services.ocr import BoundingBox, OCRBlock, OCREngine, OCRPageResult
from app.services.ocr.ocr_service import OCRService, _ENGINE_REGISTRY


def test_confidence_filter_preserves_page_layout(monkeypatch):
    from app.services.ocr.ocr_service import settings
    monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.3)
    text = "जिला: करौली\nतहसील: टोडाभीम\n\nSurvey 123   Area 2.5"
    result = OCRPageResult(page_number=1, full_text=text, blocks=[
        OCRBlock(text="जिला:", confidence=0.9, word_count=1),
        OCRBlock(text="करौली", confidence=0.8, word_count=1),
        OCRBlock(text="noise", confidence=0.1, word_count=1),
    ])
    filtered = OCRService._filter_low_confidence(result)
    assert filtered.full_text == text
    assert len(filtered.blocks) == 2
    assert filtered.word_count == 2
    assert filtered.avg_confidence == 0.85


# ---------------------------------------------------------------------------
# Mock OCR engine for testing
# ---------------------------------------------------------------------------

class MockOCREngine(OCREngine):
    """A test engine that returns predictable results."""

    name = "mock"
    _supported = ["en", "hi"]

    def __init__(self, fail: bool = False):
        self._fail = fail

    @property
    def supported_languages(self):
        return self._supported

    async def recognize(self, image, *, languages="eng", page_segmentation_mode=None):
        if self._fail:
            raise RuntimeError("Mock engine failure")
        return OCRPageResult(
            page_number=0,
            full_text="Mock OCR output text",
            blocks=[
                OCRBlock(
                    text="Mock",
                    confidence=0.95,
                    bbox=BoundingBox(x=10, y=20, width=100, height=30),
                    word_count=1,
                ),
                OCRBlock(
                    text="text",
                    confidence=0.88,
                    bbox=BoundingBox(x=120, y=20, width=80, height=30),
                    word_count=1,
                ),
            ],
            engine="mock",
            avg_confidence=0.915,
            word_count=2,
        )


class MockFailEngine(OCREngine):
    """Engine that always fails — used to test fallback."""

    name = "mock_fail"

    @property
    def supported_languages(self):
        return ["en"]

    async def recognize(self, image, *, languages="eng", page_segmentation_mode=None):
        raise RuntimeError("This engine always fails")


# ---------------------------------------------------------------------------
# OCRBlock tests
# ---------------------------------------------------------------------------

class TestOCRBlock:
    def test_block_creation(self):
        block = OCRBlock(
            text="hello",
            confidence=0.9,
            bbox=BoundingBox(x=10, y=20, width=100, height=30),
        )
        assert block.text == "hello"
        assert block.confidence == 0.9
        assert block.bbox_x == 10
        assert block.bbox_y == 20
        assert block.bbox_width == 100
        assert block.bbox_height == 30

    def test_default_bbox(self):
        block = OCRBlock(text="test", confidence=0.5)
        assert block.bbox_x == 0
        assert block.bbox_y == 0


# ---------------------------------------------------------------------------
# OCRPageResult tests
# ---------------------------------------------------------------------------

class TestOCRPageResult:
    def test_result_creation(self):
        result = OCRPageResult(
            page_number=1,
            full_text="Hello world",
            engine="tesseract",
            avg_confidence=0.92,
            word_count=2,
        )
        assert result.page_number == 1
        assert result.full_text == "Hello world"
        assert result.engine == "tesseract"

    def test_empty_result(self):
        result = OCRPageResult(page_number=1, full_text="")
        assert result.blocks == []
        assert result.avg_confidence == 0.0


# ---------------------------------------------------------------------------
# OCREngine interface tests
# ---------------------------------------------------------------------------

class TestOCREngineInterface:
    def test_mock_engine_supports_language(self):
        engine = MockOCREngine()
        assert engine.supports_language("en")
        assert engine.supports_language("hi")
        assert not engine.supports_language("ja")

    @pytest.mark.asyncio
    async def test_mock_engine_recognize(self):
        engine = MockOCREngine()
        img = np.zeros((100, 200), dtype=np.uint8)
        result = await engine.recognize(img)
        assert result.full_text == "Mock OCR output text"
        assert len(result.blocks) == 2
        assert result.engine == "mock"


# ---------------------------------------------------------------------------
# OCRService orchestration tests
# ---------------------------------------------------------------------------

class TestOCRService:
    @pytest.fixture(autouse=True)
    def _register_mock_engines(self, monkeypatch):
        """Register mock engines for testing."""
        monkeypatch.setattr(settings, "OCR_PRIMARY_ENGINE", "mock")
        monkeypatch.setattr(settings, "OCR_FALLBACK_ENGINE", "mock_fail")
        _ENGINE_REGISTRY["mock"] = MockOCREngine
        _ENGINE_REGISTRY["mock_fail"] = MockFailEngine
        yield
        _ENGINE_REGISTRY.pop("mock", None)
        _ENGINE_REGISTRY.pop("mock_fail", None)

    @pytest.mark.asyncio
    async def test_recognize_page(self):
        service = OCRService()
        service._engines["mock"] = MockOCREngine()
        img = np.zeros((100, 200), dtype=np.uint8)
        result = await service.recognize_page(img, page_number=1, languages="eng")
        assert result.page_number == 1
        assert result.full_text == "Mock OCR output text"
        assert len(result.blocks) == 2

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, monkeypatch):
        """When primary engine fails, the service should try the fallback."""
        monkeypatch.setattr(settings, "OCR_PRIMARY_ENGINE", "mock_fail")
        monkeypatch.setattr(settings, "OCR_FALLBACK_ENGINE", "mock")

        service = OCRService()
        service._engines["mock_fail"] = MockFailEngine()
        service._engines["mock"] = MockOCREngine()

        img = np.zeros((100, 200), dtype=np.uint8)
        result = await service.recognize_page(img, page_number=1)
        # Should have fallen back to MockOCREngine
        assert result.engine == "mock"
        assert result.full_text == "Mock OCR output text"

    @pytest.mark.asyncio
    async def test_low_confidence_filtering(self, monkeypatch):
        """Blocks below OCR_MIN_CONFIDENCE should be filtered."""
        monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.90)

        service = OCRService()
        service._engines["mock"] = MockOCREngine()

        img = np.zeros((100, 200), dtype=np.uint8)
        result = await service.recognize_page(img, page_number=1)

        # MockOCREngine returns blocks with 0.95 and 0.88 confidence
        # With min_confidence=0.90, the 0.88 block should be filtered
        assert len(result.blocks) == 1
        assert result.blocks[0].confidence >= 0.90

    def test_register_custom_engine(self):
        """Custom engines can be registered at runtime."""
        OCRService.register_engine("custom", MockOCREngine)
        assert "custom" in _ENGINE_REGISTRY
        _ENGINE_REGISTRY.pop("custom")

    def test_unknown_engine_raises(self):
        service = OCRService()
        with pytest.raises(ValueError, match="Unknown OCR engine"):
            service._get_engine("nonexistent_engine")


# ---------------------------------------------------------------------------
# Engine registration extensibility
# ---------------------------------------------------------------------------

class TestEngineExtensibility:
    def test_engine_registry_has_defaults(self):
        """Default engines (tesseract, easyocr) should be registered."""
        from app.services.ocr.ocr_service import _ENGINE_REGISTRY
        assert "tesseract" in _ENGINE_REGISTRY
        assert "easyocr" in _ENGINE_REGISTRY
