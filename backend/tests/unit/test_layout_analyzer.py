"""Tests for LayoutAnalyzer – uses synthetic images with drawn regions."""

import cv2
import numpy as np
import pytest

from app.services.layout import LayoutAnalyzer, Region, LayoutResult


# ---------------------------------------------------------------------------
# Fixtures – synthetic document images with known layout
# ---------------------------------------------------------------------------

def _make_text_block_page(width=800, height=1100) -> np.ndarray:
    """White page with a few distinct black text-like blocks."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Header block — wide, thin, near top
    cv2.rectangle(img, (50, 30), (750, 60), (0, 0, 0), -1)

    # Two text paragraphs in the middle
    for y_start in [150, 400]:
        for y in range(y_start, y_start + 180, 12):
            cv2.line(img, (80, y), (720, y), (0, 0, 0), 2)

    # Footer — wide, thin, near bottom
    cv2.rectangle(img, (80, 1050), (720, 1075), (0, 0, 0), -1)
    return img


def _make_table_page(width=800, height=1100) -> np.ndarray:
    """White page with a grid of horizontal and vertical lines (table)."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Draw a table grid
    x_start, x_end = 100, 700
    y_start, y_end = 200, 700
    cols = 5
    rows = 8
    col_step = (x_end - x_start) // cols
    row_step = (y_end - y_start) // rows

    # Horizontal lines
    for r in range(rows + 1):
        y = y_start + r * row_step
        cv2.line(img, (x_start, y), (x_end, y), (0, 0, 0), 2)

    # Vertical lines
    for c in range(cols + 1):
        x = x_start + c * col_step
        cv2.line(img, (x, y_start), (x, y_end), (0, 0, 0), 2)

    return img


def _make_stamp_page(width=800, height=1100) -> np.ndarray:
    """White page with a drawn circle (simulated stamp)."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    # Draw a thick circle (stamp-like)
    cv2.circle(img, (600, 900), 60, (0, 0, 0), 3)
    cv2.circle(img, (600, 900), 55, (80, 80, 80), 2)
    return img


def _make_empty_page(width=800, height=1100) -> np.ndarray:
    """Blank white page."""
    return np.ones((height, width, 3), dtype=np.uint8) * 255


def _make_two_column_page(width=800, height=1100) -> np.ndarray:
    """Page with text blocks in two distinct columns."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Left column text blocks
    for y in range(150, 800, 12):
        cv2.line(img, (50, y), (350, y), (0, 0, 0), 2)

    # Right column text blocks
    for y in range(150, 800, 12):
        cv2.line(img, (450, y), (750, y), (0, 0, 0), 2)

    return img


# ---------------------------------------------------------------------------
# Region dataclass tests
# ---------------------------------------------------------------------------

class TestRegion:
    def test_area(self):
        r = Region(x=10, y=20, width=100, height=50)
        assert r.area == 5000

    def test_aspect_ratio(self):
        r = Region(x=0, y=0, width=200, height=100)
        assert r.aspect_ratio == 2.0

    def test_aspect_ratio_zero_height(self):
        r = Region(x=0, y=0, width=100, height=0)
        assert r.aspect_ratio == 100.0  # width / max(0, 1)

    def test_crop_from(self):
        img = np.zeros((100, 200), dtype=np.uint8)
        img[10:30, 20:60] = 255
        r = Region(x=20, y=10, width=40, height=20)
        crop = r.crop_from(img)
        assert crop.shape == (20, 40)
        assert np.all(crop == 255)

    def test_default_type(self):
        r = Region(x=0, y=0, width=10, height=10)
        assert r.region_type == "text"

    def test_label(self):
        r = Region(x=0, y=0, width=10, height=10, label="title")
        assert r.label == "title"


# ---------------------------------------------------------------------------
# LayoutResult tests
# ---------------------------------------------------------------------------

class TestLayoutResult:
    def test_empty_result(self):
        result = LayoutResult()
        assert result.regions == []
        assert result.text_regions == []
        assert result.table_regions == []
        assert not result.has_tables
        assert not result.has_stamps

    def test_text_regions_filter(self):
        result = LayoutResult(
            regions=[
                Region(x=0, y=0, width=100, height=50, region_type="text"),
                Region(x=0, y=100, width=100, height=50, region_type="table"),
                Region(x=0, y=200, width=100, height=50, region_type="text"),
            ]
        )
        assert len(result.text_regions) == 2
        assert len(result.table_regions) == 1


# ---------------------------------------------------------------------------
# LayoutAnalyzer – text region detection
# ---------------------------------------------------------------------------

class TestTextRegionDetection:
    def test_detects_text_blocks(self):
        analyzer = LayoutAnalyzer()
        img = _make_text_block_page()
        result = analyzer.analyze(img)
        assert len(result.regions) > 0
        assert result.page_width == 800
        assert result.page_height == 1100

    def test_classifies_header(self):
        """A wide, thin block near the top should be classified as header."""
        analyzer = LayoutAnalyzer()
        img = _make_text_block_page()
        result = analyzer.analyze(img)
        header_regions = [r for r in result.regions if r.region_type == "header"]
        # The drawn header block should be detected
        assert len(header_regions) >= 1
        # Header should be near the top
        for r in header_regions:
            assert r.y < 1100 * 0.15

    def test_classifies_footer(self):
        """A wide, thin block near the bottom should be classified as footer."""
        analyzer = LayoutAnalyzer()
        img = _make_text_block_page()
        result = analyzer.analyze(img)
        footer_regions = [r for r in result.regions if r.region_type == "footer"]
        assert len(footer_regions) >= 1
        for r in footer_regions:
            assert r.y + r.height > 1100 * 0.85


class TestEmptyPage:
    def test_blank_page_no_regions(self):
        analyzer = LayoutAnalyzer()
        img = _make_empty_page()
        result = analyzer.analyze(img)
        # A blank page should have no significant regions
        assert len(result.regions) == 0

    def test_blank_page_dimensions(self):
        analyzer = LayoutAnalyzer()
        img = _make_empty_page(width=640, height=480)
        result = analyzer.analyze(img)
        assert result.page_width == 640
        assert result.page_height == 480


# ---------------------------------------------------------------------------
# LayoutAnalyzer – table detection
# ---------------------------------------------------------------------------

class TestTableDetection:
    def test_detects_table_grid(self):
        analyzer = LayoutAnalyzer()
        img = _make_table_page()
        result = analyzer.analyze(img)
        assert result.has_tables
        table_regions = [r for r in result.regions if r.region_type == "table"]
        assert len(table_regions) >= 1

    def test_table_region_geometry(self):
        """Detected table should roughly cover the drawn grid area."""
        analyzer = LayoutAnalyzer()
        img = _make_table_page()
        result = analyzer.analyze(img)
        table_regions = [r for r in result.regions if r.region_type == "table"]
        if table_regions:
            t = table_regions[0]
            # Should be a substantial region
            assert t.area > 50000


# ---------------------------------------------------------------------------
# LayoutAnalyzer – stamp detection
# ---------------------------------------------------------------------------

class TestStampDetection:
    def test_stamp_page(self):
        """A page with a drawn circle may detect stamps (Hough is noisy)."""
        analyzer = LayoutAnalyzer()
        img = _make_stamp_page()
        result = analyzer.analyze(img)
        # Stamp detection is heuristic; just verify no crash
        assert isinstance(result, LayoutResult)


# ---------------------------------------------------------------------------
# LayoutAnalyzer – column estimation
# ---------------------------------------------------------------------------

class TestColumnEstimation:
    def test_single_column(self):
        analyzer = LayoutAnalyzer()
        img = _make_text_block_page()
        result = analyzer.analyze(img)
        assert result.estimated_columns == 1

    def test_two_columns_detected(self):
        analyzer = LayoutAnalyzer()
        img = _make_two_column_page()
        result = analyzer.analyze(img)
        # Should detect 2 columns (text blocks on left and right)
        assert result.estimated_columns == 2


# ---------------------------------------------------------------------------
# LayoutAnalyzer – reading order
# ---------------------------------------------------------------------------

class TestReadingOrder:
    def test_regions_sorted_top_to_bottom(self):
        analyzer = LayoutAnalyzer()
        img = _make_text_block_page()
        result = analyzer.analyze(img)
        if len(result.regions) >= 2:
            for i in range(len(result.regions) - 1):
                r1 = result.regions[i]
                r2 = result.regions[i + 1]
                # Should be sorted by y first, then x
                assert (r1.y, r1.x) <= (r2.y, r2.x)


# ---------------------------------------------------------------------------
# LayoutAnalyzer – grayscale handling
# ---------------------------------------------------------------------------

class TestGrayscaleInput:
    def test_grayscale_image_accepted(self):
        """Analyzer should handle grayscale input without crashing."""
        analyzer = LayoutAnalyzer()
        img = cv2.cvtColor(_make_text_block_page(), cv2.COLOR_BGR2GRAY)
        result = analyzer.analyze(img)
        assert isinstance(result, LayoutResult)
        assert len(result.regions) > 0


# ---------------------------------------------------------------------------
# LayoutAnalyzer – merge overlapping
# ---------------------------------------------------------------------------

class TestMergeOverlapping:
    def test_non_overlapping_kept(self):
        analyzer = LayoutAnalyzer()
        r1 = Region(x=0, y=0, width=100, height=100, region_type="text")
        r2 = Region(x=500, y=500, width=100, height=100, region_type="text")
        merged = analyzer._merge_overlapping([r1, r2])
        assert len(merged) == 2

    def test_fully_overlapping_merged(self):
        analyzer = LayoutAnalyzer()
        r1 = Region(x=0, y=0, width=200, height=200, region_type="text")
        r2 = Region(x=10, y=10, width=50, height=50, region_type="text")
        merged = analyzer._merge_overlapping([r1, r2])
        assert len(merged) == 1

    def test_single_region_passthrough(self):
        analyzer = LayoutAnalyzer()
        r = Region(x=0, y=0, width=100, height=100)
        merged = analyzer._merge_overlapping([r])
        assert len(merged) == 1

    def test_empty_list(self):
        analyzer = LayoutAnalyzer()
        merged = analyzer._merge_overlapping([])
        assert merged == []


# ---------------------------------------------------------------------------
# LayoutAnalyzer – overlap ratio
# ---------------------------------------------------------------------------

class TestOverlapRatio:
    def test_no_overlap(self):
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=200, y=200, width=100, height=100)
        assert LayoutAnalyzer._overlap_ratio(r1, r2) == 0.0

    def test_full_containment(self):
        r1 = Region(x=0, y=0, width=200, height=200)
        r2 = Region(x=50, y=50, width=50, height=50)
        ratio = LayoutAnalyzer._overlap_ratio(r1, r2)
        assert ratio == 1.0  # intersection == smaller area

    def test_partial_overlap(self):
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=50, y=50, width=100, height=100)
        ratio = LayoutAnalyzer._overlap_ratio(r1, r2)
        assert 0.0 < ratio < 1.0
