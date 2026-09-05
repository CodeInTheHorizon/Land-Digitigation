"""OCR orchestration – language-aware engine selection with fallback.

Selects the best engine based on detected language and config,
with automatic fallback on primary engine failure.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ocr import OCREngine, OCRPageResult
from app.services.ocr.easyocr_engine import EasyOCREngine
from app.services.ocr.tesseract_engine import TesseractEngine

logger = get_logger(__name__)

_ENGINE_REGISTRY: dict[str, type[OCREngine]] = {
    "tesseract": TesseractEngine,
    "easyocr": EasyOCREngine,
}


class OCRService:
    """High-level OCR service with engine selection and fallback logic.

    Configured via environment variables:
      - OCR_PRIMARY_ENGINE: default engine (tesseract / easyocr)
      - OCR_FALLBACK_ENGINE: fallback if primary fails or lacks language support
      - OCR_MIN_CONFIDENCE: discard blocks below this confidence
    """

    def __init__(self) -> None:
        self._engines: dict[str, OCREngine] = {}

    def _get_engine(self, name: str) -> OCREngine:
        if name not in self._engines:
            cls = _ENGINE_REGISTRY.get(name)
            if cls is None:
                raise ValueError(f"Unknown OCR engine: {name!r}")
            self._engines[name] = cls()
        return self._engines[name]

    @staticmethod
    def register_engine(name: str, cls: type[OCREngine]) -> None:
        """Register a new OCR engine at runtime (for plugins / custom engines)."""
        _ENGINE_REGISTRY[name] = cls

    @staticmethod
    def _fallback_name(current: str) -> str:
        """Fallback engine for `current`, or "" when no fallback is configured."""
        fallback = settings.ocr_fallback_engine
        if not fallback:
            return ""
        name = fallback if current == settings.OCR_PRIMARY_ENGINE else settings.OCR_PRIMARY_ENGINE
        return "" if name == current else name

    def _select_engine(self, language: Optional[str]) -> OCREngine:
        """Choose the best engine based on detected language and config."""
        primary = self._get_engine(settings.OCR_PRIMARY_ENGINE)

        if language and not primary.supports_language(language) and settings.ocr_fallback_engine:
            fallback = self._get_engine(settings.ocr_fallback_engine)
            if fallback.supports_language(language):
                logger.info(
                    "ocr.engine_fallback",
                    language=language,
                    primary=primary.name,
                    fallback=fallback.name,
                )
                return fallback

        return primary

    async def recognize_page(
        self,
        image: np.ndarray,
        page_number: int,
        *,
        languages: str = "eng",
        language_hint: Optional[str] = None,
    ) -> OCRPageResult:
        """Run OCR on a single page, with automatic fallback on failure.

        Parameters
        ----------
        image : np.ndarray
            Preprocessed page image.
        page_number : int
            1-based page number.
        languages : str
            Tesseract-style '+'-separated language string.
        language_hint : str, optional
            ISO-639-1 primary language code for engine selection.
        """
        engine = self._select_engine(language_hint)

        try:
            result = await engine.recognize(image, languages=languages)
            if not result.full_text.strip() or result.avg_confidence < settings.OCR_MIN_CONFIDENCE:
                fallback_name = self._fallback_name(engine.name)
                if fallback_name:
                    try:
                        alternative = await self._get_engine(fallback_name).recognize(image, languages=languages)
                        if alternative.full_text.strip() and (not result.full_text.strip() or alternative.avg_confidence > result.avg_confidence):
                            result = alternative
                    except Exception:
                        pass  # Preserve partial primary text if fallback is unavailable.
            result.page_number = page_number
            result.detected_language = language_hint
            result = self._filter_low_confidence(result)
            return result
        except Exception as exc:
            logger.warning(
                "ocr.primary_failed",
                engine=engine.name,
                error=str(exc),
            )

            # Try fallback engine
            fallback_name = self._fallback_name(engine.name)
            if not fallback_name:
                logger.error("ocr.no_fallback_configured", engine=engine.name)
                raise RuntimeError(f"OCR failed ({engine.name}): {exc}") from exc
            try:
                fallback = self._get_engine(fallback_name)
                result = await fallback.recognize(image, languages=languages)
                result.page_number = page_number
                result.detected_language = language_hint
                result = self._filter_low_confidence(result)
                return result
            except Exception as fallback_exc:
                logger.error(
                    "ocr.fallback_failed",
                    engine=fallback_name,
                    primary_error=str(exc),
                    fallback_error=str(fallback_exc),
                )
                raise RuntimeError(
                    f"Both OCR engines failed. "
                    f"Primary ({engine.name}): {exc}; "
                    f"Fallback ({fallback_name}): {fallback_exc}"
                ) from fallback_exc

    @staticmethod
    def _filter_low_confidence(result: OCRPageResult) -> OCRPageResult:
        """Remove blocks below the configured minimum confidence."""
        min_conf = settings.OCR_MIN_CONFIDENCE
        if min_conf <= 0:
            return result

        filtered = [b for b in result.blocks if b.confidence >= min_conf]
        if len(filtered) != len(result.blocks):
            logger.debug(
                "ocr.filtered_low_confidence",
                original=len(result.blocks),
                kept=len(filtered),
                threshold=min_conf,
            )
        result.blocks = filtered

        # Keep the engine's page text: Tesseract blocks are individual words,
        # so joining them with newlines destroys lines, paragraphs and tables.
        # Filtering applies to block evidence and confidence statistics only.
        if filtered:
            result.avg_confidence = round(
                sum(b.confidence for b in filtered) / len(filtered), 4
            )
            result.word_count = sum(b.word_count for b in filtered)
        else:
            # Keep original text for review even when no block is reliable.
            result.avg_confidence = 0.0
            result.word_count = 0

        return result
