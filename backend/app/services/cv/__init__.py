"""Computer Vision preprocessing and layout analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Region:
    """A detected region on a page."""
    x: int
    y: int
    width: int
    height: int
    region_type: str = "text"  # text | table | image | header | footer | stamp | handwriting
    confidence: float = 1.0


class ImagePreprocessor:
    """Prepare scanned document images for better OCR accuracy."""

    @staticmethod
    def preprocess(image: np.ndarray) -> np.ndarray:
        """Standard preprocessing pipeline for document images."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Adaptive thresholding for better text contrast
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Deskew
        binary = ImagePreprocessor._deskew(binary)

        return binary

    @staticmethod
    def _deskew(image: np.ndarray) -> np.ndarray:
        """Correct skew in scanned images."""
        coords = np.column_stack(np.where(image > 0))
        if len(coords) < 10:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5:
            return image

        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    @staticmethod
    def enhance_for_handwriting(image: np.ndarray) -> np.ndarray:
        """Enhanced preprocessing for handwritten documents."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # CLAHE for local contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Morphological operations to connect broken strokes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)

        return enhanced


class LayoutAnalyzer:
    """Simple rule-based layout analysis using contour detection."""

    @staticmethod
    def detect_regions(image: np.ndarray) -> List[Region]:
        """Detect text, table, and image regions on a page."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Dilate to merge nearby text into blocks
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 10))
        dilated = cv2.dilate(binary, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = image.shape[:2]
        min_area = (w * h) * 0.001  # ignore tiny regions

        regions: List[Region] = []
        for contour in contours:
            x, y, rw, rh = cv2.boundingRect(contour)
            area = rw * rh
            if area < min_area:
                continue

            aspect = rw / max(rh, 1)
            region_type = "text"
            if aspect > 3 and rh < h * 0.05:
                region_type = "header"
            elif rw > w * 0.6 and rh > h * 0.1:
                region_type = "table"

            regions.append(Region(x=x, y=y, width=rw, height=rh, region_type=region_type))

        # Sort top-to-bottom, left-to-right
        regions.sort(key=lambda r: (r.y, r.x))
        return regions
