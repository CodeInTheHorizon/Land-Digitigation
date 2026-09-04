"""EasyOCR engine adapter – better for handwritten and multilingual text.

EasyOCR uses deep learning models and handles many Indian scripts
out of the box.  Readers are cached per language combination.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Set

import numpy as np

from app.services.ocr import BoundingBox, OCRBlock, OCREngine, OCRPageResult

# Tesseract 3-letter codes → EasyOCR 2-letter codes
_TESS_TO_EASY: Dict[str, str] = {
    "eng": "en",
    "hin": "hi",
    "mar": "mr",
    "ben": "bn",
    "guj": "gu",
    "pan": "pa",
    "tam": "ta",
    "tel": "te",
    "kan": "kn",
    "mal": "ml",
}

# EasyOCR native codes (2-letter) for supported_languages
_EASY_LANGS = list(_TESS_TO_EASY.values())


class EasyOCREngine(OCREngine):
    """Adapter for EasyOCR – supports many Indian scripts out of the box.

    Lazily initialises a reader for each unique language combination
    and caches it for the lifetime of the process.
    """

    name = "easyocr"

    def __init__(self) -> None:
        self._readers: Dict[str, object] = {}

    @property
    def supported_languages(self) -> List[str]:
        return list(_EASY_LANGS)

    def _get_reader(self, languages: str):
        """Lazy-init a reader for the requested language combination.

        Parameters
        ----------
        languages : str
            '+'-separated Tesseract-style string (e.g. 'eng+hin').
            Converted to EasyOCR language codes internally.
        """
        import easyocr

        key = languages
        if key not in self._readers:
            # Convert Tesseract 3-letter codes → EasyOCR 2-letter codes
            lang_set: Set[str] = set()
            for code in languages.split("+"):
                easy = _TESS_TO_EASY.get(code, code)
                lang_set.add(easy)

            # EasyOCR always needs English for mixed scripts
            lang_set.add("en")

            self._readers[key] = easyocr.Reader(
                sorted(lang_set), gpu=False, verbose=False,
            )
        return self._readers[key]

    async def recognize(
        self,
        image: np.ndarray,
        *,
        languages: str = "eng",
        page_segmentation_mode: int | None = None,
    ) -> OCRPageResult:
        start = time.monotonic()

        reader = self._get_reader(languages)
        results = reader.readtext(image)  # type: ignore[attr-defined]

        blocks: List[OCRBlock] = []
        confidences: List[float] = []
        total_words = 0

        for bbox_points, text, conf in results:
            text = text.strip()
            if not text:
                continue

            # bbox_points is [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
            xs = [p[0] for p in bbox_points]
            ys = [p[1] for p in bbox_points]
            x, y = int(min(xs)), int(min(ys))
            w, h = int(max(xs) - x), int(max(ys) - y)

            confidences.append(conf)
            word_count = len(text.split())
            total_words += word_count

            blocks.append(
                OCRBlock(
                    text=text,
                    confidence=round(conf, 4),
                    bbox=BoundingBox(x=x, y=y, width=w, height=h),
                    language=None,
                    word_count=word_count,
                )
            )

        full_text = "\n".join(b.text for b in blocks)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return OCRPageResult(
            page_number=0,
            full_text=full_text,
            blocks=blocks,
            detected_language=None,
            engine=self.name,
            avg_confidence=round(avg_conf, 4),
            word_count=total_words,
            processing_time_ms=elapsed_ms,
        )
