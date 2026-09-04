"""NLP services – language detection and entity extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.services.nlp.entity_extractor import (
    EntityExtractor,
    EntitySpan,
    EntityType,
    ExtractionResult,
)

logger = get_logger(__name__)

__all__ = [
    "DetectedLanguage",
    "EntityExtractor",
    "EntitySpan",
    "EntityType",
    "ExtractedField",
    "ExtractionResult",
    "LanguageDetector",
    "LandRecordEntityExtractor",
]


@dataclass
class DetectedLanguage:
    code: str      # ISO-639 two-letter
    name: str
    confidence: float


@dataclass
class ExtractedField:
    """A structured field extracted from text."""
    field_name: str
    value: str
    confidence: float
    source: str = "nlp"  # nlp | llm | rule
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class LanguageDetector:
    """Detect the primary language of a text passage."""

    _LANG_NAMES = {
        "en": "English", "hi": "Hindi", "mr": "Marathi", "bn": "Bengali",
        "gu": "Gujarati", "pa": "Punjabi", "ta": "Tamil", "te": "Telugu",
        "kn": "Kannada", "ml": "Malayalam",
    }

    @staticmethod
    def detect(text: str) -> DetectedLanguage:
        from langdetect import detect_langs

        if not text.strip():
            return DetectedLanguage(code="en", name="English", confidence=0.0)

        try:
            results = detect_langs(text)
            top = results[0]
            code = str(top.lang)
            return DetectedLanguage(
                code=code,
                name=LanguageDetector._LANG_NAMES.get(code, code),
                confidence=top.prob,
            )
        except Exception:
            return DetectedLanguage(code="en", name="English", confidence=0.0)


class LandRecordEntityExtractor:
    """Rule-based + regex entity extraction for Indian land record fields."""

    # Common regex patterns for land record fields
    import re as _re

    _PATTERNS: Dict[str, str] = {
        "survey_number": r"(?:survey\s*(?:no|number|#)|सर्वे\s*(?:नं|नंबर))\s*[:\-]?\s*([\d/\-A-Za-z]+)",
        "khasra_number": r"(?:khasra\s*(?:no|number|#)|खसरा\s*(?:नं|नंबर))\s*[:\-]?\s*([\d/\-]+)",
        "khata_number": r"(?:khata\s*(?:no|number|#)|खाता\s*(?:नं|नंबर))\s*[:\-]?\s*([\d/\-]+)",
        "plot_number": r"(?:plot\s*(?:no|number|#)|भूखंड\s*(?:नं|नंबर))\s*[:\-]?\s*([\d/\-A-Za-z]+)",
        "area": r"(?:area|क्षेत्रफल|रकबा)\s*[:\-]?\s*([\d.,]+)\s*(hectare|acre|bigha|sq\.?\s*m|sq\.?\s*ft|हेक्टेयर|एकड़|बीघा)?",
        "village": r"(?:village|ग्राम|गांव|मौजा)\s*[:\-]?\s*([A-Za-zऀ-ॿঀ-৿઀-૿஀-௿ఀ-౿ಀ-೿ഀ-ൿ\s]+?)(?:\s*(?:tehsil|तहसील|district|जिला|$))",
        "tehsil": r"(?:tehsil|तहसील|taluka|तालुका)\s*[:\-]?\s*([A-Za-zऀ-ॿ\s]+?)(?:\s*(?:district|जिला|$))",
        "district": r"(?:district|जिला|जनपद)\s*[:\-]?\s*([A-Za-zऀ-ॿ\s]+?)(?:\s*(?:state|राज्य|$))",
    }

    def extract(self, text: str, page_number: Optional[int] = None) -> List[ExtractedField]:
        """Extract land-record fields from OCR text using regex patterns."""
        import re

        fields: List[ExtractedField] = []

        for field_name, pattern in self._PATTERNS.items():
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.UNICODE))
            for match in matches:
                value = match.group(1).strip()
                if not value:
                    continue
                fields.append(
                    ExtractedField(
                        field_name=field_name,
                        value=value,
                        confidence=0.7,  # regex-based = moderate confidence
                        source="nlp",
                        page_number=page_number,
                        char_start=match.start(1),
                        char_end=match.end(1),
                    )
                )

        return fields
