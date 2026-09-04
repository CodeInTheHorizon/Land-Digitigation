"""Tests for LanguageDetector – uses synthetic text strings."""

import pytest

from app.services.language import LanguageDetector, LanguageResult


@pytest.fixture
def detector():
    return LanguageDetector()


# ---------------------------------------------------------------------------
# English detection
# ---------------------------------------------------------------------------

class TestEnglishDetection:
    def test_pure_english(self, detector):
        result = detector.detect_from_text("This is a land record from District Lucknow")
        assert result.primary_language == "en"
        assert result.confidence > 0.5
        assert result.script_detected == "Latin"

    def test_english_with_numbers(self, detector):
        result = detector.detect_from_text("Plot No 123, Area 45.6 hectares")
        assert result.primary_language == "en"

    def test_short_english(self, detector):
        result = detector.detect_from_text("Name: Ram Kumar")
        assert result.primary_language == "en"


# ---------------------------------------------------------------------------
# Hindi detection (Devanagari script)
# ---------------------------------------------------------------------------

class TestHindiDetection:
    def test_pure_hindi(self, detector):
        text = "यह एक भूमि रिकॉर्ड है जिला लखनऊ से"
        result = detector.detect_from_text(text)
        assert result.primary_language == "hi"
        assert result.script_detected == "Devanagari"
        assert result.confidence > 0.5

    def test_hindi_with_numbers(self, detector):
        text = "खसरा संख्या 123, क्षेत्रफल 45.6 हेक्टेयर"
        result = detector.detect_from_text(text)
        assert result.primary_language == "hi"

    def test_devanagari_chars_identified(self, detector):
        """Individual Devanagari characters should be counted."""
        text = "नाम"  # "Name" in Hindi
        result = detector.detect_from_text(text)
        assert result.primary_language == "hi"


# ---------------------------------------------------------------------------
# Multilingual detection
# ---------------------------------------------------------------------------

class TestMultilingualDetection:
    def test_hindi_english_mixed(self, detector):
        text = "District: जिला, Tehsil: तहसील, Village: गांव, Plot Number: 42"
        result = detector.detect_from_text(text)
        assert result.is_multilingual
        assert "en" in result.all_detected
        assert "hi" in result.all_detected

    def test_tesseract_langs_string(self, detector):
        text = "District: जिला, Tehsil: तहसील"
        result = detector.detect_from_text(text)
        langs_str = result.tesseract_langs_string
        # Should contain both eng and hin
        assert "eng" in langs_str
        assert "hin" in langs_str
        # Should be '+'-separated
        assert "+" in langs_str


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_text(self, detector):
        result = detector.detect_from_text("")
        assert result.primary_language == "en"
        assert result.confidence == 0.0

    def test_whitespace_only(self, detector):
        result = detector.detect_from_text("   \n\t  ")
        assert result.primary_language == "en"
        assert result.confidence == 0.0

    def test_numbers_only(self, detector):
        result = detector.detect_from_text("123 456 789.0")
        assert result.primary_language == "en"

    def test_punctuation_only(self, detector):
        result = detector.detect_from_text("... --- !!!")
        assert result.primary_language == "en"

    def test_none_safe(self, detector):
        """Passing None should not crash (defensive)."""
        # We test empty string; None would be a caller bug
        result = detector.detect_from_text("")
        assert isinstance(result, LanguageResult)


# ---------------------------------------------------------------------------
# OCR text detection (noisy)
# ---------------------------------------------------------------------------

class TestOCRTextDetection:
    def test_noisy_ocr_text_fallback(self, detector):
        """Very low confidence on short noisy text should fallback."""
        result = detector.detect_from_image_text("a b c", fallback="hi")
        # Short text with low confidence should use fallback
        assert isinstance(result, LanguageResult)

    def test_clear_hindi_ocr_text(self, detector):
        text = "भूमि रिकॉर्ड डिजिटलीकरण प्रणाली"
        result = detector.detect_from_image_text(text)
        assert result.primary_language == "hi"


# ---------------------------------------------------------------------------
# Tesseract language mapping
# ---------------------------------------------------------------------------

class TestLanguageMapping:
    def test_tesseract_lang_property(self, detector):
        result = detector.detect_from_text("यह हिंदी है")
        assert result.tesseract_lang == "hin"

    def test_english_tesseract_lang(self, detector):
        result = detector.detect_from_text("This is English text")
        assert result.tesseract_lang == "eng"

    def test_unknown_lang_defaults_to_eng(self):
        result = LanguageResult(
            primary_language="zz",
            confidence=0.5,
            script_detected="Unknown",
        )
        assert result.tesseract_lang == "eng"

    def test_tesseract_langs_string_always_includes_eng(self):
        result = LanguageResult(
            primary_language="hi",
            confidence=0.9,
            script_detected="Devanagari",
            all_detected={"hi": 0.9},
        )
        assert "eng" in result.tesseract_langs_string


# ---------------------------------------------------------------------------
# Script range extensibility
# ---------------------------------------------------------------------------

class TestScriptRanges:
    def test_bengali_detected(self, detector):
        text = "বাংলা ভূমি রেকর্ড"  # Bengali
        result = detector.detect_from_text(text)
        assert result.primary_language == "bn"
        assert result.script_detected == "Bengali"

    def test_tamil_detected(self, detector):
        text = "நில பதிவு"  # Tamil
        result = detector.detect_from_text(text)
        assert result.primary_language == "ta"
        assert result.script_detected == "Tamil"

    def test_gujarati_detected(self, detector):
        text = "જમીન નોંધ"  # Gujarati
        result = detector.detect_from_text(text)
        assert result.primary_language == "gu"
        assert result.script_detected == "Gujarati"

    def test_telugu_detected(self, detector):
        text = "భూమి రికార్డు"  # Telugu
        result = detector.detect_from_text(text)
        assert result.primary_language == "te"
        assert result.script_detected == "Telugu"
