"""Image preprocessing pipeline for scanned documents.

Operations (applied selectively based on image quality analysis):
  - Grayscale conversion
  - Resolution normalisation (upscale low-DPI scans)
  - Noise estimation & removal
  - Contrast enhancement (CLAHE)
  - Deskewing
  - Adaptive thresholding

Clean documents are detected and skipped to avoid degrading quality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PreprocessingResult:
    """Result of preprocessing a single page image."""

    image: np.ndarray
    operations_applied: List[str] = field(default_factory=list)
    original_size: tuple = (0, 0)
    final_size: tuple = (0, 0)
    estimated_dpi: Optional[int] = None
    noise_level: float = 0.0
    skew_angle: float = 0.0
    is_clean: bool = False


class DocumentPreprocessor:
    """Smart document image preprocessor.

    Analyses image quality before applying each operation so that
    clean digital documents are not degraded by unnecessary filters.
    """

    def __init__(
        self,
        target_dpi: int | None = None,
        noise_threshold: float | None = None,
        deskew_max_angle: float | None = None,
    ) -> None:
        self.target_dpi = target_dpi or settings.PREPROCESS_TARGET_DPI
        self.noise_threshold = noise_threshold or settings.PREPROCESS_NOISE_THRESHOLD
        self.deskew_max_angle = deskew_max_angle or settings.PREPROCESS_DESKEW_MAX_ANGLE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preprocess(
        self,
        image: np.ndarray,
        *,
        dpi: int | None = None,
        force: bool = False,
    ) -> PreprocessingResult:
        """Run the full preprocessing pipeline.

        Parameters
        ----------
        image : np.ndarray
            Input image in BGR or grayscale.
        dpi : int, optional
            Source DPI if known (from PDF metadata).
        force : bool
            When True, apply all operations regardless of quality analysis.
        """
        # Guard against empty / zero-dimension images
        if image is None or image.size == 0 or 0 in image.shape[:2]:
            raise ValueError(
                f"Cannot preprocess empty or zero-dimension image "
                f"(shape={getattr(image, 'shape', None)})"
            )

        result = PreprocessingResult(
            image=image,
            original_size=(image.shape[1], image.shape[0]),
        )

        # Step 1: Grayscale
        gray = self._to_grayscale(image)
        result.operations_applied.append("grayscale")
        result.image = gray

        # Step 2: Quality analysis (decides what else to do)
        noise_level = self._estimate_noise(gray)
        result.noise_level = noise_level

        skew_angle = self._estimate_skew(gray)
        result.skew_angle = skew_angle

        is_clean = noise_level < self.noise_threshold and abs(skew_angle) < 0.5
        result.is_clean = is_clean

        if is_clean and not force:
            logger.debug(
                "preprocess.clean_document",
                noise=noise_level,
                skew=skew_angle,
            )
            # Even clean docs get resolution normalisation
            result.image = self._normalise_resolution(gray, dpi)
            if dpi and dpi < self.target_dpi:
                result.operations_applied.append("resolution_normalisation")
            result.final_size = (result.image.shape[1], result.image.shape[0])
            result.estimated_dpi = dpi or self._guess_dpi(image)
            return result

        # Step 3: Resolution normalisation
        current = self._normalise_resolution(gray, dpi)
        if dpi and dpi < self.target_dpi:
            result.operations_applied.append("resolution_normalisation")
        result.image = current

        # Step 4: Noise removal (only if noisy)
        if noise_level >= self.noise_threshold or force:
            current = self._remove_noise(current)
            result.operations_applied.append("noise_removal")
            result.image = current

        # Step 5: Contrast enhancement
        current = self._enhance_contrast(current)
        result.operations_applied.append("contrast_enhancement")
        result.image = current

        # Step 6: Deskew (only if measurable skew)
        if (abs(skew_angle) >= 0.5 and abs(skew_angle) <= self.deskew_max_angle) or force:
            current = self._deskew(current, skew_angle)
            result.operations_applied.append("deskew")
            result.image = current

        # Step 7: Adaptive thresholding → binary
        current = self._threshold(current)
        result.operations_applied.append("threshold")
        result.image = current

        result.final_size = (current.shape[1], current.shape[0])
        result.estimated_dpi = dpi or self._guess_dpi(image)
        return result

    def preprocess_for_handwriting(self, image: np.ndarray) -> PreprocessingResult:
        """Enhanced pipeline for handwritten documents."""
        result = PreprocessingResult(
            image=image,
            original_size=(image.shape[1], image.shape[0]),
        )

        gray = self._to_grayscale(image)
        result.operations_applied.append("grayscale")

        # CLAHE for local contrast — crucial for ink-on-paper
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        result.operations_applied.append("clahe_contrast")

        # Morphological closing to connect broken pen strokes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        closed = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
        result.operations_applied.append("morphological_close")

        # Mild denoising (preserve stroke detail)
        denoised = cv2.fastNlMeansDenoising(closed, h=5)
        result.operations_applied.append("mild_denoise")

        result.image = denoised
        result.final_size = (denoised.shape[1], denoised.shape[0])
        return result

    # ------------------------------------------------------------------
    # Individual operations
    # ------------------------------------------------------------------

    @staticmethod
    def _to_grayscale(image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            if image.shape[2] == 4:
                # BGRA → BGR → Gray
                bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
                return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            if image.shape[2] == 3:
                return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image.copy()

    def _normalise_resolution(
        self, image: np.ndarray, dpi: int | None
    ) -> np.ndarray:
        """Upscale if DPI is below target. Never downscale."""
        if dpi is None or dpi >= self.target_dpi:
            return image
        scale = self.target_dpi / dpi
        if scale <= 1.0:
            return image
        h, w = image.shape[:2]
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def _estimate_noise(gray: np.ndarray) -> float:
        """Estimate noise level using Laplacian variance (normalised 0–1).

        Low value = clean document, high = noisy scan.
        """
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        # Normalise: typical document range 0–5000, cap at 1.0
        variance = float(laplacian.var())
        # Invert logic: high variance on a *document* usually means text edges,
        # not noise.  True noise shows in the *median* absolute deviation of
        # the high-frequency band.
        # Use a simpler proxy: percentage of near-median pixels in the
        # Laplacian that have high magnitude.
        abs_lap = np.abs(laplacian)
        median_val = float(np.median(abs_lap))
        if median_val < 1.0:
            return 0.0
        # Fraction of pixels with Laplacian > 2× median (noise-like)
        high_freq = float(np.mean(abs_lap > 2 * median_val))
        return round(min(high_freq, 1.0), 4)

    @staticmethod
    def _estimate_skew(gray: np.ndarray) -> float:
        """Estimate page skew angle in degrees using projection profile."""
        # Quick approach: use Hough lines on edge image
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=100,
            minLineLength=gray.shape[1] // 4, maxLineGap=10,
        )
        if lines is None or len(lines) == 0:
            return 0.0

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            dy = y2 - y1
            if abs(dx) < 1:
                continue
            angle = np.degrees(np.arctan2(dy, dx))
            # Only consider near-horizontal lines (text lines)
            if abs(angle) < 45:
                angles.append(angle)

        if not angles:
            return 0.0

        return float(np.median(angles))

    @staticmethod
    def _remove_noise(gray: np.ndarray) -> np.ndarray:
        """Non-local means denoising — good for scanned documents."""
        return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    @staticmethod
    def _enhance_contrast(gray: np.ndarray) -> np.ndarray:
        """CLAHE — adaptive histogram equalisation."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    @staticmethod
    def _deskew(gray: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by -angle to correct skew."""
        if abs(angle) < 0.1:
            return gray
        h, w = gray.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
        return cv2.warpAffine(
            gray, matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    @staticmethod
    def _threshold(gray: np.ndarray) -> np.ndarray:
        """Adaptive Gaussian thresholding for binarisation."""
        return cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=4,
        )

    @staticmethod
    def _guess_dpi(image: np.ndarray) -> int:
        """Rough DPI guess based on image dimensions (A4 assumption)."""
        h, w = image.shape[:2]
        # A4 is 210 × 297 mm ≈ 8.27 × 11.69 inches
        longer = max(h, w)
        dpi_estimate = int(longer / 11.69)
        return max(72, min(dpi_estimate, 600))
