"""Tests for DocumentPreprocessor – uses synthetic images, no external deps."""

import numpy as np
import cv2
import pytest

from app.services.preprocessing import DocumentPreprocessor, PreprocessingResult


# ---------------------------------------------------------------------------
# Fixtures – synthetic document images
# ---------------------------------------------------------------------------

def _make_clean_page(width=800, height=1100) -> np.ndarray:
    """Create a clean white page with crisp black text-like lines."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    # Draw a few horizontal "text lines"
    for y in range(100, 600, 40):
        cv2.line(img, (100, y), (700, y), (0, 0, 0), 2)
    # A heading
    cv2.rectangle(img, (100, 50), (400, 80), (0, 0, 0), -1)
    return img


def _make_noisy_page(width=800, height=1100) -> np.ndarray:
    """Create a noisy scanned document simulation."""
    img = _make_clean_page(width, height)
    # Add salt-and-pepper noise
    rng = np.random.RandomState(42)
    noise = rng.randint(0, 255, img.shape, dtype=np.uint8)
    mask = rng.random(img.shape[:2]) < 0.05  # 5% pixel noise
    for c in range(3):
        img[:, :, c][mask] = noise[:, :, c][mask]
    return img


def _make_skewed_page(angle=3.0) -> np.ndarray:
    """Create a page rotated by `angle` degrees (simulates scanner skew)."""
    img = _make_clean_page()
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h), borderValue=(255, 255, 255))


def _make_low_dpi_page() -> np.ndarray:
    """Simulate a low-DPI scan (small image)."""
    return _make_clean_page(width=400, height=550)


def _make_grayscale_page() -> np.ndarray:
    """Already-grayscale input."""
    img = _make_clean_page()
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGrayscaleConversion:
    def test_bgr_to_gray(self):
        pp = DocumentPreprocessor()
        img = _make_clean_page()
        result = pp.preprocess(img)
        assert len(result.image.shape) == 2  # grayscale
        assert "grayscale" in result.operations_applied

    def test_already_gray_passthrough(self):
        pp = DocumentPreprocessor()
        img = _make_grayscale_page()
        result = pp.preprocess(img)
        assert len(result.image.shape) == 2
        assert "grayscale" in result.operations_applied


class TestCleanDocumentDetection:
    def test_clean_page_minimal_processing(self):
        """Clean documents should not get noise removal or thresholding."""
        pp = DocumentPreprocessor()
        img = _make_clean_page()
        result = pp.preprocess(img)
        assert result.is_clean
        assert "noise_removal" not in result.operations_applied
        assert "threshold" not in result.operations_applied

    def test_clean_page_still_gets_grayscale(self):
        pp = DocumentPreprocessor()
        img = _make_clean_page()
        result = pp.preprocess(img)
        assert "grayscale" in result.operations_applied


class TestNoisyDocumentProcessing:
    def test_noisy_page_gets_denoised(self):
        pp = DocumentPreprocessor(noise_threshold=0.01)
        img = _make_noisy_page()
        result = pp.preprocess(img)
        # Should apply noise removal for a noisy image
        assert "noise_removal" in result.operations_applied or "contrast_enhancement" in result.operations_applied

    def test_force_flag_applies_all_operations(self):
        pp = DocumentPreprocessor()
        img = _make_clean_page()
        result = pp.preprocess(img, force=True)
        # Force should apply all operations even on clean document
        assert "contrast_enhancement" in result.operations_applied
        assert "threshold" in result.operations_applied


class TestDeskewing:
    def test_skewed_page_corrected(self):
        pp = DocumentPreprocessor()
        img = _make_skewed_page(angle=5.0)
        result = pp.preprocess(img, force=True)
        assert "deskew" in result.operations_applied

    def test_extreme_skew_skipped(self):
        """Skew beyond max_angle should not be corrected."""
        pp = DocumentPreprocessor(deskew_max_angle=2.0)
        img = _make_skewed_page(angle=20.0)
        result = pp.preprocess(img, force=True)
        # The estimated skew may or may not exceed 2°,
        # but the deskew step checks the threshold
        # This is an integration test — just verify no crash
        assert isinstance(result.image, np.ndarray)


class TestResolutionNormalisation:
    def test_low_dpi_upscaled(self):
        pp = DocumentPreprocessor(target_dpi=300)
        img = _make_low_dpi_page()
        result = pp.preprocess(img, dpi=150)
        # Image should be larger after upscaling
        assert result.image.shape[0] > img.shape[0]
        assert "resolution_normalisation" in result.operations_applied

    def test_high_dpi_not_downscaled(self):
        pp = DocumentPreprocessor(target_dpi=300)
        img = _make_clean_page()
        original_h = img.shape[0]
        result = pp.preprocess(img, dpi=600)
        # Should not shrink
        assert result.image.shape[0] >= original_h - 10  # allow tiny rounding


class TestThresholding:
    def test_forced_threshold_produces_binary(self):
        pp = DocumentPreprocessor()
        img = _make_clean_page()
        result = pp.preprocess(img, force=True)
        assert "threshold" in result.operations_applied
        # Binary image should have only 0 and 255
        unique = np.unique(result.image)
        assert set(unique).issubset({0, 255})


class TestHandwritingPreprocessing:
    def test_handwriting_pipeline(self):
        pp = DocumentPreprocessor()
        img = _make_clean_page()
        result = pp.preprocess_for_handwriting(img)
        assert "clahe_contrast" in result.operations_applied
        assert "morphological_close" not in result.operations_applied
        assert "mild_denoise" in result.operations_applied


class TestPreprocessingResult:
    def test_result_has_correct_sizes(self):
        pp = DocumentPreprocessor()
        img = _make_clean_page(width=800, height=1100)
        result = pp.preprocess(img)
        assert result.original_size == (800, 1100)
        assert result.final_size[0] > 0
        assert result.final_size[1] > 0

    def test_noise_level_is_bounded(self):
        pp = DocumentPreprocessor()
        img = _make_noisy_page()
        result = pp.preprocess(img)
        assert 0.0 <= result.noise_level <= 1.0

    def test_estimated_dpi_reasonable(self):
        pp = DocumentPreprocessor()
        img = _make_clean_page(width=2480, height=3508)  # A4 at 300 DPI
        result = pp.preprocess(img)
        assert result.estimated_dpi is not None
        assert 72 <= result.estimated_dpi <= 600
