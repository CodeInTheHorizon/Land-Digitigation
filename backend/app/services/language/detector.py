"""Language detection — script-based (image) and statistical (text).

Priority: English, Hindi.
Extensible: add an entry to SCRIPT_RANGES for any new Indian language.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Unicode script ranges for Indian languages
# ---------------------------------------------------------------------------

SCRIPT_RANGES: Dict[str, List[Tuple[int, int]]] = {
    # ISO-639-1 code → list of (start, end) codepoint ranges (inclusive)
    "hi": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],          # Devanagari (Hindi, Marathi, Sanskrit)
    "bn": [(0x0980, 0x09FF)],                              # Bengali
    "pa": [(0x0A00, 0x0A7F)],                              # Gurmukhi (Punjabi)
    "gu": [(0x0A80, 0x0AFF)],                              # Gujarati
    "or": [(0x0B00, 0x0B7F)],                              # Odia
    "ta": [(0x0B80, 0x0BFF)],                              # Tamil
    "te": [(0x0C00, 0x0C7F)],                              # Telugu
    "kn": [(0x0C80, 0x0CFF)],                              # Kannada
    "ml": [(0x0D00, 0x0D7F)],                              # Malayalam
    "mr": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],           # Marathi uses Devanagari
}

# Devanagari is shared by Hindi, Marathi, Sanskrit.  We default to Hindi
# unless statistical detection says otherwise.
_DEVANAGARI_LANGS = {"hi", "mr"}

# Map ISO-639-1 → Tesseract language codes
LANG_TO_TESSERACT: Dict[str, str] = {
    "en": "eng",
    "hi": "hin",
    "mr": "mar",
    "bn": "ben",
    "gu": "guj",
    "pa": "pan",
    "ta": "tam",
    "te": "tel",
    "kn": "kan",
    "ml": "mal",
    "or": "ori",
}


@dataclass
class LanguageResult:
    """Result of language detection."""

    primary_language: str  # ISO-639-1 code
    confidence: float      # 0.0 – 1.0
    script_detected: str   # Unicode script name
    all_detected: Dict[str, float] = field(default_factory=dict)  # lang → share
    is_multilingual: bool = False

    @property
    def tesseract_lang(self) -> str:
        """Return Tesseract language pack name."""
        return LANG_TO_TESSERACT.get(self.primary_language, "eng")

    @property
    def tesseract_langs_string(self) -> str:
        """Return '+'-separated Tesseract language string for all detected languages.

        Example: 'eng+hin' for English + Hindi.
        """
        langs = set()
        for lang in self.all_detected:
            tess = LANG_TO_TESSERACT.get(lang)
            if tess:
                langs.add(tess)
        if not langs:
            langs.add("eng")
        # Always include English as many Indian documents have English mixed in
        langs.add("eng")
        return "+".join(sorted(langs))


class LanguageDetector:
    """Detect document language from text or image OCR output.

    Uses two complementary strategies:
    1. **Script-based** (Unicode range analysis) — fast, works on any text.
    2. **Statistical** (langdetect library) — better for Latin-script disambiguation.
    """

    def detect_from_text(self, text: str) -> LanguageResult:
        """Detect language from extracted text.

        Works even on small amounts of text by combining script analysis
        with statistical detection.
        """
        if not text or not text.strip():
            return LanguageResult(
                primary_language="en",
                confidence=0.0,
                script_detected="Unknown",
                all_detected={"en": 1.0},
            )

        # Phase 1: Script-based detection
        script_counts = self._count_scripts(text)
        total_chars = sum(script_counts.values())

        if total_chars == 0:
            return LanguageResult(
                primary_language="en",
                confidence=0.5,
                script_detected="Latin",
                all_detected={"en": 1.0},
            )

        # Build language share map
        lang_shares: Dict[str, float] = {}
        for lang, count in script_counts.items():
            lang_shares[lang] = count / total_chars

        # Phase 2: Statistical refinement for Latin text or Devanagari ambiguity
        # Also refine when Devanagari is dominant — helps distinguish Hindi vs Marathi.
        devanagari_share = lang_shares.get("hi", 0.0)
        latin_share = lang_shares.get("en", 0.0)
        if latin_share > 0.5 or devanagari_share > 0.3:
            stat_result = self._statistical_detect(text)
            if stat_result:
                # Blend: give script detection 60% weight, statistical 40%
                for lang, conf in stat_result.items():
                    if lang in lang_shares:
                        lang_shares[lang] = lang_shares[lang] * 0.6 + conf * 0.4
                    else:
                        lang_shares[lang] = conf * 0.4

        # Determine primary language
        primary = max(lang_shares, key=lang_shares.get)  # type: ignore[arg-type]
        confidence = lang_shares[primary]

        # Check for multilingual
        significant_langs = {k: v for k, v in lang_shares.items() if v >= 0.1}
        is_multilingual = len(significant_langs) > 1

        # Determine script name
        script_name = self._get_script_name(primary)

        logger.debug(
            "language.detected",
            primary=primary,
            confidence=confidence,
            multilingual=is_multilingual,
            shares=lang_shares,
        )

        return LanguageResult(
            primary_language=primary,
            confidence=round(confidence, 3),
            script_detected=script_name,
            all_detected=lang_shares,
            is_multilingual=is_multilingual,
        )

    def detect_from_image_text(
        self,
        text: str,
        *,
        fallback: str = "en",
    ) -> LanguageResult:
        """Detect language from OCR-extracted text.

        More tolerant of noise than detect_from_text — uses higher
        thresholds before overriding the fallback.
        """
        result = self.detect_from_text(text)

        # OCR text can be noisy; require higher confidence to override fallback
        if result.confidence < 0.3:
            result.primary_language = fallback
            result.confidence = 0.5

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_scripts(text: str) -> Dict[str, int]:
        """Count characters belonging to each script."""
        counts: Dict[str, int] = {}
        latin_count = 0

        for char in text:
            cp = ord(char)

            # Skip whitespace, punctuation, digits
            if unicodedata.category(char)[0] in ("Z", "P", "N", "C", "S"):
                continue

            # Check Indian scripts — skip Devanagari-sharing languages
            # in the per-character loop; count Devanagari once under "hi".
            # Statistical detection later disambiguates Hindi vs Marathi.
            found = False
            for lang, ranges in SCRIPT_RANGES.items():
                if lang in _DEVANAGARI_LANGS and lang != "hi":
                    # Skip "mr" entry — Devanagari chars counted under "hi"
                    continue
                for start, end in ranges:
                    if start <= cp <= end:
                        counts[lang] = counts.get(lang, 0) + 1
                        found = True
                        break
                if found:
                    break

            if not found:
                # Assume Latin / English
                if unicodedata.category(char)[0] == "L":
                    latin_count += 1

        if latin_count > 0:
            counts["en"] = latin_count

        return counts

    @staticmethod
    def _statistical_detect(text: str) -> Optional[Dict[str, float]]:
        """Use langdetect library for statistical detection."""
        try:
            from langdetect import detect_langs

            results = detect_langs(text)
            return {r.lang: r.prob for r in results}
        except Exception:
            return None

    @staticmethod
    def _get_script_name(lang: str) -> str:
        """Human-readable script name for a language code."""
        script_names = {
            "en": "Latin",
            "hi": "Devanagari",
            "mr": "Devanagari",
            "bn": "Bengali",
            "pa": "Gurmukhi",
            "gu": "Gujarati",
            "or": "Odia",
            "ta": "Tamil",
            "te": "Telugu",
            "kn": "Kannada",
            "ml": "Malayalam",
        }
        return script_names.get(lang, "Unknown")
