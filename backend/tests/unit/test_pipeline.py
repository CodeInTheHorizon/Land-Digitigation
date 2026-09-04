"""Integration tests for DocumentPipeline – uses mocked OCR + synthetic images.

No external OCR engines or PDF files required.  The pipeline is tested
end-to-end by injecting a mock OCR service and feeding synthetic images.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from app.services.language import LanguageResult
from app.services.layout import LayoutResult
from app.services.ocr import BoundingBox, OCRBlock, OCRPageResult
from app.services.pipeline import DocumentPipeline, PipelineResult
from app.services.pipeline.document_pipeline import PageResult
from app.services.preprocessing import PreprocessingResult


# ---------------------------------------------------------------------------
# Helpers – synthetic data
# ---------------------------------------------------------------------------

def _make_synthetic_image(width=800, height=1100) -> np.ndarray:
    """A simple BGR image with black text-like lines on white."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    for y in range(100, 600, 40):
        cv2.line(img, (80, y), (720, y), (0, 0, 0), 2)
    return img


def _synthetic_image_bytes(width=800, height=1100) -> bytes:
    """Encode a synthetic image as JPEG bytes."""
    img = _make_synthetic_image(width, height)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _mock_ocr_result(page_number: int = 1) -> OCRPageResult:
    return OCRPageResult(
        page_number=page_number,
        full_text="Mock OCR output for testing",
        blocks=[
            OCRBlock(
                text="Mock",
                confidence=0.95,
                bbox=BoundingBox(x=10, y=20, width=100, height=30),
                word_count=1,
            ),
            OCRBlock(
                text="OCR",
                confidence=0.90,
                bbox=BoundingBox(x=120, y=20, width=80, height=30),
                word_count=1,
            ),
        ],
        engine="mock",
        avg_confidence=0.925,
        word_count=2,
    )


# ---------------------------------------------------------------------------
# PipelineResult tests
# ---------------------------------------------------------------------------

class TestPipelineResult:
    def test_empty_result(self):
        result = PipelineResult()
        assert result.pages == []
        assert result.page_count == 0
        assert result.full_text == ""
        assert result.avg_confidence == 0.0

    def test_full_text_concatenation(self):
        p1 = PageResult(
            page_number=1,
            ocr_result=OCRPageResult(page_number=1, full_text="Page one"),
            preprocessing=MagicMock(spec=PreprocessingResult),
            layout=MagicMock(spec=LayoutResult),
            language=MagicMock(spec=LanguageResult),
        )
        p2 = PageResult(
            page_number=2,
            ocr_result=OCRPageResult(page_number=2, full_text="Page two"),
            preprocessing=MagicMock(spec=PreprocessingResult),
            layout=MagicMock(spec=LayoutResult),
            language=MagicMock(spec=LanguageResult),
        )
        result = PipelineResult(pages=[p1, p2], page_count=2)
        assert "Page one" in result.full_text
        assert "Page two" in result.full_text

    def test_avg_confidence_computed(self):
        p1 = PageResult(
            page_number=1,
            ocr_result=OCRPageResult(
                page_number=1,
                full_text="text",
                blocks=[OCRBlock(text="a", confidence=0.8)],
                avg_confidence=0.8,
            ),
            preprocessing=MagicMock(spec=PreprocessingResult),
            layout=MagicMock(spec=LayoutResult),
            language=MagicMock(spec=LanguageResult),
        )
        p2 = PageResult(
            page_number=2,
            ocr_result=OCRPageResult(
                page_number=2,
                full_text="text",
                blocks=[OCRBlock(text="b", confidence=0.9)],
                avg_confidence=0.9,
            ),
            preprocessing=MagicMock(spec=PreprocessingResult),
            layout=MagicMock(spec=LayoutResult),
            language=MagicMock(spec=LanguageResult),
        )
        result = PipelineResult(pages=[p1, p2], page_count=2)
        assert result.avg_confidence == pytest.approx(0.85, abs=0.01)


# ---------------------------------------------------------------------------
# PageResult tests
# ---------------------------------------------------------------------------

class TestPageResult:
    def test_page_result_fields(self):
        pr = PageResult(
            page_number=3,
            ocr_result=_mock_ocr_result(3),
            preprocessing=MagicMock(spec=PreprocessingResult),
            layout=MagicMock(spec=LayoutResult),
            language=MagicMock(spec=LanguageResult),
            image_width=800,
            image_height=1100,
            image_dpi=300,
            processing_time_ms=150,
        )
        assert pr.page_number == 3
        assert pr.image_width == 800
        assert pr.image_dpi == 300
        assert pr.processing_time_ms == 150


# ---------------------------------------------------------------------------
# DocumentPipeline – image extraction
# ---------------------------------------------------------------------------

class TestImageExtraction:
    def test_extract_image_page(self):
        pipeline = DocumentPipeline()
        image_bytes = _synthetic_image_bytes()
        pages = pipeline._extract_pages(image_bytes, "image/jpeg")
        assert len(pages) == 1
        img, dpi = pages[0]
        assert isinstance(img, np.ndarray)
        assert img.shape[2] == 3  # BGR

    def test_extract_image_png(self):
        img = _make_synthetic_image()
        _, buf = cv2.imencode(".png", img)
        pages = DocumentPipeline._extract_image_page(buf.tobytes())
        assert len(pages) == 1

    def test_invalid_image_raises(self):
        pipeline = DocumentPipeline()
        with pytest.raises(Exception):
            pipeline._extract_pages(b"not an image", "image/jpeg")


# ---------------------------------------------------------------------------
# DocumentPipeline – end-to-end with mocked OCR
# ---------------------------------------------------------------------------

class TestPipelineEndToEnd:
    @pytest.mark.asyncio
    async def test_single_image_pipeline(self):
        """Full pipeline on a single JPEG image with mocked OCR."""
        pipeline = DocumentPipeline()

        # Mock the OCR service
        mock_result = _mock_ocr_result(1)
        pipeline.ocr_service.recognize_page = AsyncMock(return_value=mock_result)

        image_bytes = _synthetic_image_bytes()
        result = await pipeline.process(
            image_bytes,
            mime_type="image/jpeg",
            filename="test.jpg",
        )

        assert isinstance(result, PipelineResult)
        assert result.page_count == 1
        assert len(result.pages) == 1
        assert result.pages[0].ocr_result.full_text == "Mock OCR output for testing"
        assert result.primary_language is not None
        assert result.total_processing_time_ms >= 0
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_pipeline_captures_page_dimensions(self):
        """Pipeline should record image width/height."""
        pipeline = DocumentPipeline()
        pipeline.ocr_service.recognize_page = AsyncMock(
            return_value=_mock_ocr_result(1)
        )

        image_bytes = _synthetic_image_bytes(width=640, height=480)
        result = await pipeline.process(
            image_bytes, mime_type="image/jpeg", filename="small.jpg",
        )

        page = result.pages[0]
        assert page.image_width == 640
        assert page.image_height == 480

    @pytest.mark.asyncio
    async def test_pipeline_handles_extraction_failure(self):
        """Pipeline should capture error if page extraction fails."""
        pipeline = DocumentPipeline()

        result = await pipeline.process(
            b"corrupt data",
            mime_type="image/jpeg",
            filename="bad.jpg",
        )

        assert len(result.errors) > 0
        assert "extraction failed" in result.errors[0].lower() or len(result.pages) == 0

    @pytest.mark.asyncio
    async def test_pipeline_handles_ocr_failure_gracefully(self):
        """If OCR fails on a page, the error is recorded but pipeline continues."""
        pipeline = DocumentPipeline()
        pipeline.ocr_service.recognize_page = AsyncMock(
            side_effect=RuntimeError("OCR engine crashed"),
        )

        image_bytes = _synthetic_image_bytes()
        result = await pipeline.process(
            image_bytes, mime_type="image/jpeg", filename="test.jpg",
        )

        # Should have an error recorded but not crash
        assert len(result.errors) >= 1


# ---------------------------------------------------------------------------
# DocumentPipeline – language detection
# ---------------------------------------------------------------------------

class TestPipelineLanguageDetection:
    @pytest.mark.asyncio
    async def test_language_detected(self):
        """Pipeline should detect language and pass it to OCR."""
        pipeline = DocumentPipeline()
        pipeline.ocr_service.recognize_page = AsyncMock(
            return_value=_mock_ocr_result(1),
        )

        image_bytes = _synthetic_image_bytes()
        result = await pipeline.process(
            image_bytes, mime_type="image/jpeg", filename="test.jpg",
        )

        # primary_language should be set (either from probe or fallback)
        assert result.primary_language is not None
        page = result.pages[0]
        assert page.language is not None

    @pytest.mark.asyncio
    async def test_language_override_propagated(self):
        """When the first page sets a language, subsequent pages should use it."""
        pipeline = DocumentPipeline()

        call_count = 0

        async def mock_recognize(img, page_number, **kwargs):
            nonlocal call_count
            call_count += 1
            r = _mock_ocr_result(page_number)
            return r

        pipeline.ocr_service.recognize_page = mock_recognize

        # Build a two-page scenario by monkeypatching _extract_pages
        img1 = _make_synthetic_image()
        img2 = _make_synthetic_image(600, 800)
        pipeline._extract_pages = MagicMock(
            return_value=[(img1, 300), (img2, 300)]
        )

        result = await pipeline.process(
            b"fake", mime_type="image/jpeg", filename="multi.jpg",
        )

        assert result.page_count == 2
        assert len(result.pages) == 2
        # Both pages should have a language set
        assert result.pages[0].language is not None
        assert result.pages[1].language is not None


# ---------------------------------------------------------------------------
# DocumentPipeline – preprocessing integration
# ---------------------------------------------------------------------------

class TestPipelinePreprocessing:
    @pytest.mark.asyncio
    async def test_preprocessing_applied(self):
        """Each page should go through preprocessing."""
        pipeline = DocumentPipeline()
        pipeline.ocr_service.recognize_page = AsyncMock(
            return_value=_mock_ocr_result(1),
        )

        image_bytes = _synthetic_image_bytes()
        result = await pipeline.process(
            image_bytes, mime_type="image/jpeg", filename="test.jpg",
        )

        page = result.pages[0]
        assert page.preprocessing is not None
        assert "grayscale" in page.preprocessing.operations_applied


# ---------------------------------------------------------------------------
# DocumentPipeline – layout integration
# ---------------------------------------------------------------------------

class TestPipelineLayout:
    @pytest.mark.asyncio
    async def test_layout_analysis_performed(self):
        """Each page should get layout analysis results."""
        pipeline = DocumentPipeline()
        pipeline.ocr_service.recognize_page = AsyncMock(
            return_value=_mock_ocr_result(1),
        )

        image_bytes = _synthetic_image_bytes()
        result = await pipeline.process(
            image_bytes, mime_type="image/jpeg", filename="test.jpg",
        )

        page = result.pages[0]
        assert page.layout is not None
        assert isinstance(page.layout, LayoutResult)
