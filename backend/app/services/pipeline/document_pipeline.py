"""End-to-end document intelligence pipeline.

Stages:
  1. Retrieve uploaded document from storage
  2. Extract PDF pages (or treat single image as one page)
  3. Convert pages to images
  4. Preprocess images (smart — skips clean documents)
  5. Detect language
  6. Analyse layout (regions)
  7. Run OCR per page
  8. Capture text, confidence, bounding boxes
  9. Return structured results (caller persists to DB)

This module is pure business logic — no database imports.
The Celery task (tasks/pipeline.py) handles DB persistence.
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.core.config import settings
from app.core.logging import get_logger
from app.services.language import LanguageDetector, LanguageResult
from app.services.layout import LayoutAnalyzer, LayoutResult
from app.services.ocr import OCRPageResult
from app.services.ocr.ocr_service import OCRService
from app.services.preprocessing import DocumentPreprocessor, PreprocessingResult

logger = get_logger(__name__)


@dataclass
class PageResult:
    """Processing result for a single page."""

    page_number: int
    ocr_result: OCRPageResult
    preprocessing: PreprocessingResult
    layout: LayoutResult
    language: LanguageResult
    image_width: int = 0
    image_height: int = 0
    image_dpi: Optional[int] = None
    processing_time_ms: int = 0


@dataclass
class PipelineResult:
    """Full pipeline result for a document."""

    pages: List[PageResult] = field(default_factory=list)
    page_count: int = 0
    primary_language: Optional[str] = None
    total_processing_time_ms: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Concatenated text from all pages."""
        return "\n\n".join(
            p.ocr_result.full_text for p in self.pages if p.ocr_result.full_text
        )

    @property
    def avg_confidence(self) -> float:
        confs = [p.ocr_result.avg_confidence for p in self.pages if p.ocr_result.blocks]
        return round(sum(confs) / len(confs), 4) if confs else 0.0


class DocumentPipeline:
    """Orchestrates the full document processing pipeline.

    Stateless — instantiate, call ``process()``, discard.
    """

    def __init__(self) -> None:
        self.preprocessor = DocumentPreprocessor()
        self.language_detector = LanguageDetector()
        self.layout_analyzer = LayoutAnalyzer()
        self.ocr_service = OCRService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(
        self,
        file_bytes: bytes,
        *,
        mime_type: str = "application/pdf",
        filename: str = "document",
    ) -> PipelineResult:
        """Run the full pipeline on raw document bytes.

        Parameters
        ----------
        file_bytes : bytes
            Raw file content (PDF or image).
        mime_type : str
            MIME type of the file.
        filename : str
            Original filename (for logging).
        """
        pipeline_start = time.monotonic()
        result = PipelineResult()

        logger.info(
            "pipeline.start",
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(file_bytes),
        )

        # Step 1: Extract page images lazily (generator for PDFs)
        try:
            page_iter = self._extract_pages(file_bytes, mime_type)
        except Exception as exc:
            error_msg = "Document pages could not be read. Upload a readable PDF or image."
            logger.error("pipeline.extraction_failed", error=str(exc))
            result.errors.append(error_msg)
            return result

        # Step 2: Process each page one at a time to limit memory.
        # Probe each page independently; multilingual bundles can switch scripts.
        probe_language: Optional[str] = None
        page_count = 0

        iterator = iter(page_iter)
        while True:
            try:
                page_img, dpi = next(iterator)
            except StopIteration:
                break
            except Exception:
                result.errors.append("Unable to read one or more document pages.")
                break
            page_count += 1
            try:
                page_result = await self._process_page(page_img, page_number=page_count, dpi=dpi)
                result.pages.append(page_result)
                if page_result.language.confidence >= 0.6:
                    probe_language = probe_language or page_result.language.primary_language
                else:
                    result.errors.append(f"Page {page_count}: language could not be confidently identified.")
                if not page_result.ocr_result.full_text.strip():
                    result.errors.append(f"Page {page_count}: no readable OCR text found.")
            except Exception:
                result.errors.append(f"Page {page_count}: OCR failed; other pages may still be usable.")

        result.page_count = page_count
        languages = {p.language.primary_language for p in result.pages if p.language.confidence >= 0.6}
        result.primary_language = "mixed" if len(languages) > 1 else probe_language
        result.total_processing_time_ms = int(
            (time.monotonic() - pipeline_start) * 1000
        )

        logger.info(
            "pipeline.completed",
            pages=result.page_count,
            language=result.primary_language,
            confidence=result.avg_confidence,
            time_ms=result.total_processing_time_ms,
            errors=len(result.errors),
        )

        return result

    # ------------------------------------------------------------------
    # Page-level processing
    # ------------------------------------------------------------------

    async def _process_page(
        self,
        image: np.ndarray,
        *,
        page_number: int,
        dpi: Optional[int] = None,
        language_override: Optional[str] = None,
    ) -> PageResult:
        """Process a single page image through the full pipeline."""
        page_start = time.monotonic()

        h, w = image.shape[:2]

        # 1. Preprocess
        preprocess_result = self.preprocessor.preprocess(image, dpi=dpi)
        processed_img = preprocess_result.image

        # 2. Layout analysis (on original grayscale for better contours)
        layout_result = self.layout_analyzer.analyze(processed_img)

        # 3. Language detection
        # Do a quick OCR pass on a small region to detect language,
        # unless we already have a language from a previous page.
        if language_override:
            lang_result = LanguageResult(
                primary_language=language_override,
                confidence=0.9,
                script_detected=self.language_detector._get_script_name(language_override),
                all_detected={language_override: 0.9},
            )
        else:
            lang_result = await self._detect_language(processed_img)

        # 4. Run OCR with detected language
        languages = {code.strip() for code in settings.OCR_LANGUAGES.replace(",", "+").split("+") if code.strip()}
        if lang_result.confidence >= 0.6:
            languages.update(lang_result.tesseract_langs_string.split("+"))
        languages_str = "+".join(sorted(languages)) or "eng+hin"
        ocr_result = await self.ocr_service.recognize_page(
            processed_img,
            page_number,
            languages=languages_str,
            language_hint=lang_result.primary_language,
        )
        if ocr_result.full_text.strip():
            lang_result = self.language_detector.detect_from_image_text(ocr_result.full_text)
        ocr_result.detected_language = lang_result.primary_language if lang_result.confidence >= 0.6 else None

        elapsed_ms = int((time.monotonic() - page_start) * 1000)

        logger.debug(
            "pipeline.page_processed",
            page=page_number,
            language=lang_result.primary_language,
            confidence=ocr_result.avg_confidence,
            words=ocr_result.word_count,
            regions=len(layout_result.regions),
            time_ms=elapsed_ms,
        )

        return PageResult(
            page_number=page_number,
            ocr_result=ocr_result,
            preprocessing=preprocess_result,
            layout=layout_result,
            language=lang_result,
            image_width=processed_img.shape[1],
            image_height=processed_img.shape[0],
            image_dpi=dpi,
            processing_time_ms=elapsed_ms,
        )

    async def _detect_language(self, image: np.ndarray) -> LanguageResult:
        """Quick OCR + language detection on a sample region."""
        # Take the top-centre 30% of the image for language sampling
        h, w = image.shape[:2]
        y_end = max(1, int(h * 0.3))
        x_start = int(w * 0.1)
        x_end = max(x_start + 1, int(w * 0.9))
        sample = image[0:y_end, x_start:x_end]

        try:
            # Quick Tesseract pass with eng+hin
            quick_result = await self.ocr_service.recognize_page(
                sample,
                page_number=0,
                languages=settings.OCR_LANGUAGES.replace(",", "+"),
            )
            if quick_result.full_text.strip():
                return self.language_detector.detect_from_image_text(
                    quick_result.full_text
                )
        except Exception as exc:
            logger.debug("pipeline.language_probe_failed", error=str(exc))

        # Unknown language: retain the configured multilingual OCR fallback.
        return LanguageResult(
            primary_language="en",
            confidence=0.0,
            script_detected="Unknown",
            all_detected={},
        )

    # ------------------------------------------------------------------
    # PDF / image extraction
    # ------------------------------------------------------------------

    def _extract_pages(
        self, file_bytes: bytes, mime_type: str,
    ) -> Iterator[Tuple[np.ndarray, Optional[int]]]:
        """Extract page images from a document.

        Yields
        ------
        (image, dpi) tuples.  ``dpi`` is None for images where the
        source DPI is unknown.  PDF pages are yielded one at a time
        so that only one page image is in memory at once.
        """
        if mime_type == "application/pdf":
            yield from self._extract_pdf_pages(file_bytes)
        else:
            yield from self._extract_image_page(file_bytes)

    @staticmethod
    def _extract_pdf_pages(
        pdf_bytes: bytes,
    ) -> Iterator[Tuple[np.ndarray, Optional[int]]]:
        """Extract pages from a PDF using PyMuPDF (fitz).

        Yields each page at the target DPI — only one page image is
        in memory at a time.
        """
        import fitz  # PyMuPDF

        target_dpi = settings.PREPROCESS_TARGET_DPI
        zoom = target_dpi / 72.0  # PDF default is 72 DPI
        matrix = fitz.Matrix(zoom, zoom)

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        try:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=matrix, alpha=False)

                # Convert pixmap to numpy array (RGB)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, 3
                )
                # Convert RGB → BGR for OpenCV
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                yield (img_bgr, target_dpi)
        finally:
            doc.close()

    @staticmethod
    def _extract_image_page(
        image_bytes: bytes,
    ) -> List[Tuple[np.ndarray, Optional[int]]]:
        """Load a single image file as one page."""
        pil_image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))

        # Try to get DPI from EXIF / image info
        dpi = None
        if hasattr(pil_image, "info") and "dpi" in pil_image.info:
            dpi_tuple = pil_image.info["dpi"]
            dpi = int(dpi_tuple[0]) if isinstance(dpi_tuple, tuple) else int(dpi_tuple)

        # Convert to numpy BGR
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        img = np.array(pil_image)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        return [(img_bgr, dpi)]
