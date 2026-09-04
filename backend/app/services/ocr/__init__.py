"""OCR abstraction layer – engine-agnostic interface.

Engines implement OCREngine.  The OCRService selects the right engine
for the detected language and falls back automatically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class BoundingBox:
    """Pixel-coordinate bounding box for an OCR block."""

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class OCRBlock:
    """A single recognised text block with spatial and confidence info."""

    text: str
    confidence: float
    bbox: BoundingBox = field(default_factory=BoundingBox)
    block_type: str = "text"  # text | table | header | footer | handwriting | stamp
    language: Optional[str] = None
    word_count: int = 0

    # Legacy accessors for model compatibility
    @property
    def bbox_x(self) -> int:
        return self.bbox.x

    @property
    def bbox_y(self) -> int:
        return self.bbox.y

    @property
    def bbox_width(self) -> int:
        return self.bbox.width

    @property
    def bbox_height(self) -> int:
        return self.bbox.height


@dataclass
class OCRPageResult:
    """OCR output for one page."""

    page_number: int
    full_text: str
    blocks: List[OCRBlock] = field(default_factory=list)
    detected_language: Optional[str] = None
    engine: str = "unknown"
    avg_confidence: float = 0.0
    word_count: int = 0
    processing_time_ms: int = 0


class OCREngine(ABC):
    """Interface that every OCR engine adapter must implement."""

    name: str = "base"

    @property
    def supported_languages(self) -> List[str]:
        """ISO-639-1 codes this engine supports."""
        return []

    @abstractmethod
    async def recognize(
        self,
        image: np.ndarray,
        *,
        languages: str = "eng",
        page_segmentation_mode: int | None = None,
    ) -> OCRPageResult:
        """Run OCR on a single page image (grayscale or BGR numpy array).

        Parameters
        ----------
        image : np.ndarray
            Input image.
        languages : str
            '+'-separated Tesseract-style language string (e.g. 'eng+hin').
        page_segmentation_mode : int, optional
            Tesseract PSM value (engine-specific; ignored if unsupported).
        """
        ...

    def supports_language(self, lang_code: str) -> bool:
        return lang_code in self.supported_languages


__all__ = [
    "BoundingBox",
    "OCRBlock",
    "OCREngine",
    "OCRPageResult",
]
