"""Layout analysis for scanned document pages.

Detects and classifies regions (text blocks, tables, headers, stamps/seals)
using contour analysis and heuristics.  Designed for Indian land records
which commonly contain:
  - Printed tabular data (khasra, khatauni columns)
  - Headers / official stamps
  - Handwritten notes / signatures
  - Mixed-language text blocks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Region:
    """A detected region on a document page."""

    x: int
    y: int
    width: int
    height: int
    region_type: str = "text"
    # text | table | header | footer | stamp | handwriting | image
    confidence: float = 1.0
    label: Optional[str] = None

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        return self.width / max(self.height, 1)

    def crop_from(self, image: np.ndarray) -> np.ndarray:
        """Extract this region from an image."""
        return image[self.y : self.y + self.height, self.x : self.x + self.width]


@dataclass
class LayoutResult:
    """Result of layout analysis for one page."""

    regions: List[Region] = field(default_factory=list)
    page_width: int = 0
    page_height: int = 0
    has_tables: bool = False
    has_stamps: bool = False
    estimated_columns: int = 1

    @property
    def text_regions(self) -> List[Region]:
        return [r for r in self.regions if r.region_type == "text"]

    @property
    def table_regions(self) -> List[Region]:
        return [r for r in self.regions if r.region_type == "table"]


class LayoutAnalyzer:
    """Contour-based document layout analyzer.

    Uses morphological operations and contour detection to identify
    distinct regions on a page, then classifies them by geometry.
    """

    def __init__(
        self,
        min_region_fraction: float = 0.001,
        merge_distance: int = 15,
    ) -> None:
        """
        Parameters
        ----------
        min_region_fraction : float
            Minimum region area as a fraction of total page area.
        merge_distance : int
            Maximum pixel gap between regions to merge.
        """
        self.min_region_fraction = min_region_fraction
        self.merge_distance = merge_distance

    def analyze(self, image: np.ndarray) -> LayoutResult:
        """Detect and classify regions on a document page.

        Parameters
        ----------
        image : np.ndarray
            Grayscale or BGR image.

        Returns
        -------
        LayoutResult
            Detected regions sorted top-to-bottom, left-to-right.
        """
        h, w = image.shape[:2]

        result = LayoutResult(page_width=w, page_height=h)

        gray = self._to_gray(image)

        # Binarise with Otsu
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # Detect text blocks
        text_regions = self._detect_text_regions(binary, w, h)

        # Detect table regions (horizontal + vertical line intersection)
        table_regions = self._detect_table_regions(binary, w, h)

        # Detect circular / seal-like regions (stamps)
        stamp_regions = self._detect_stamps(gray, w, h)

        # Merge and de-duplicate
        all_regions = text_regions + table_regions + stamp_regions
        merged = self._merge_overlapping(all_regions)

        # Sort reading order: top-to-bottom, left-to-right
        merged.sort(key=lambda r: (r.y, r.x))

        result.regions = merged
        result.has_tables = any(r.region_type == "table" for r in merged)
        result.has_stamps = any(r.region_type == "stamp" for r in merged)
        result.estimated_columns = self._estimate_columns(text_regions, w)

        logger.debug(
            "layout.analyzed",
            regions=len(merged),
            tables=result.has_tables,
            stamps=result.has_stamps,
            columns=result.estimated_columns,
        )

        return result

    # ------------------------------------------------------------------
    # Region detection strategies
    # ------------------------------------------------------------------

    def _detect_text_regions(
        self, binary: np.ndarray, page_w: int, page_h: int,
    ) -> List[Region]:
        """Detect text blocks by dilating characters into connected blobs."""
        # Horizontal dilation merges characters into words/lines
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
        dilated = cv2.dilate(binary, kernel_h, iterations=2)

        # Vertical dilation merges lines into paragraphs
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 15))
        dilated = cv2.dilate(dilated, kernel_v, iterations=1)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        min_area = page_w * page_h * self.min_region_fraction
        regions: List[Region] = []

        for contour in contours:
            x, y, rw, rh = cv2.boundingRect(contour)
            if rw * rh < min_area:
                continue

            region_type = self._classify_text_region(
                x, y, rw, rh, page_w, page_h,
            )
            regions.append(
                Region(x=x, y=y, width=rw, height=rh, region_type=region_type)
            )

        return regions

    def _detect_table_regions(
        self, binary: np.ndarray, page_w: int, page_h: int,
    ) -> List[Region]:
        """Detect tables by finding intersections of horizontal and vertical lines."""
        # Detect horizontal lines
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (page_w // 8, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

        # Detect vertical lines
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, page_h // 8))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

        # Intersection of horizontal and vertical lines → table grid
        grid = cv2.bitwise_and(h_lines, v_lines)

        # Dilate intersections to form connected table regions
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 50))
        table_mask = cv2.dilate(grid, kernel, iterations=3)

        contours, _ = cv2.findContours(
            table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        min_area = page_w * page_h * 0.01  # Tables are at least 1% of page
        regions: List[Region] = []

        for contour in contours:
            x, y, rw, rh = cv2.boundingRect(contour)
            if rw * rh < min_area:
                continue
            regions.append(
                Region(
                    x=x, y=y, width=rw, height=rh,
                    region_type="table", confidence=0.8,
                )
            )

        return regions

    def _detect_stamps(
        self, gray: np.ndarray, page_w: int, page_h: int,
    ) -> List[Region]:
        """Detect circular stamps/seals using Hough circle detection."""
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)

        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=page_w // 8,
            param1=100,
            param2=50,
            minRadius=int(page_w * 0.02),
            maxRadius=int(page_w * 0.15),
        )

        regions: List[Region] = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for circle in circles[0]:
                cx, cy, r = int(circle[0]), int(circle[1]), int(circle[2])
                x = max(0, cx - r)
                y = max(0, cy - r)
                w = min(2 * r, page_w - x)
                h = min(2 * r, page_h - y)
                regions.append(
                    Region(
                        x=x, y=y, width=w, height=h,
                        region_type="stamp", confidence=0.7,
                    )
                )

        return regions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3 and image.shape[2] >= 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    @staticmethod
    def _classify_text_region(
        x: int, y: int, w: int, h: int,
        page_w: int, page_h: int,
    ) -> str:
        """Heuristic classification based on position and geometry."""
        aspect = w / max(h, 1)

        # Header: wide, thin, near top
        if y < page_h * 0.1 and aspect > 3:
            return "header"

        # Footer: wide, thin, near bottom
        if y + h > page_h * 0.9 and aspect > 3:
            return "footer"

        return "text"

    def _merge_overlapping(self, regions: List[Region]) -> List[Region]:
        """Merge regions that overlap significantly."""
        if len(regions) <= 1:
            return regions

        # Sort by area descending so larger regions absorb smaller ones
        regions.sort(key=lambda r: r.area, reverse=True)
        merged: List[Region] = []
        used = [False] * len(regions)

        for i, r1 in enumerate(regions):
            if used[i]:
                continue
            cx, cy, cw, ch = r1.x, r1.y, r1.width, r1.height
            for j in range(i + 1, len(regions)):
                if used[j]:
                    continue
                r2 = regions[j]
                if self._overlap_ratio(
                    Region(x=cx, y=cy, width=cw, height=ch), r2
                ) > 0.5:
                    # Absorb r2 — expand bounding box to union
                    new_x = min(cx, r2.x)
                    new_y = min(cy, r2.y)
                    cw = max(cx + cw, r2.x + r2.width) - new_x
                    ch = max(cy + ch, r2.y + r2.height) - new_y
                    cx, cy = new_x, new_y
                    used[j] = True
            merged.append(
                Region(x=cx, y=cy, width=cw, height=ch,
                       region_type=r1.region_type, confidence=r1.confidence)
            )

        return merged

    @staticmethod
    def _overlap_ratio(r1: Region, r2: Region) -> float:
        """Compute intersection-over-smaller-area ratio."""
        x1 = max(r1.x, r2.x)
        y1 = max(r1.y, r2.y)
        x2 = min(r1.x + r1.width, r2.x + r2.width)
        y2 = min(r1.y + r1.height, r2.y + r2.height)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        smaller = min(r1.area, r2.area)
        return intersection / max(smaller, 1)

    @staticmethod
    def _estimate_columns(
        text_regions: List[Region], page_w: int,
    ) -> int:
        """Estimate number of text columns from region x-positions."""
        if len(text_regions) < 2:
            return 1

        # Look at centre-x of each region
        centres = sorted(r.x + r.width // 2 for r in text_regions)
        if not centres:
            return 1

        # Cluster centres: if most are in the left or right half, it's 1 column
        mid = page_w // 2
        left = sum(1 for c in centres if c < mid * 0.7)
        right = sum(1 for c in centres if c > mid * 1.3)

        if left > 0 and right > 0 and right >= len(centres) * 0.2:
            return 2
        return 1
