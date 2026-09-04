"""Tesseract OCR engine adapter.

Supports English + all major Indian languages via Tesseract language packs.
Captures word-level bounding boxes and confidence scores.
"""

from __future__ import annotations

import time
from typing import List, Optional

import numpy as np

from app.services.ocr import BoundingBox, OCRBlock, OCREngine, OCRPageResult

# ISO-639-1 → Tesseract language codes
_LANG_MAP = {
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
    "sa": "san",  # Sanskrit
    "ur": "urd",  # Urdu
}


class TesseractEngine(OCREngine):
    """Adapter for pytesseract / Tesseract-OCR.

    Uses image_to_data for structured output (bounding boxes + confidence
    per word), and image_to_string for the full page text.
    """

    name = "tesseract"

    @property
    def supported_languages(self) -> List[str]:
        return list(_LANG_MAP.keys())

    async def recognize(
        self,
        image: np.ndarray,
        *,
        languages: str = "eng",
        page_segmentation_mode: int | None = None,
    ) -> OCRPageResult:
        import pytesseract
        from PIL import Image

        start = time.monotonic()

        pil_image = Image.fromarray(image)

        # Build config string
        config = ""
        if page_segmentation_mode is not None:
            config = f"--psm {page_segmentation_mode}"

        # Structured word-level data
        data = pytesseract.image_to_data(
            pil_image, lang=languages, config=config,
            output_type=pytesseract.Output.DICT,
        )

        blocks: List[OCRBlock] = []
        confidences: List[float] = []
        total_words = 0

        n_items = len(data["text"])
        for i in range(n_items):
            word = data["text"][i].strip()
            if not word:
                continue
            conf = float(data["conf"][i])
            if conf < 0:
                continue

            conf_norm = conf / 100.0
            confidences.append(conf_norm)
            total_words += 1

            blocks.append(
                OCRBlock(
                    text=word,
                    confidence=conf_norm,
                    bbox=BoundingBox(
                        x=data["left"][i],
                        y=data["top"][i],
                        width=data["width"][i],
                        height=data["height"][i],
                    ),
                    language=None,
                    word_count=1,
                )
            )

        # Full-page text (preserves layout better than joining words)
        full_text = pytesseract.image_to_string(
            pil_image, lang=languages, config=config,
        )

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return OCRPageResult(
            page_number=0,  # caller sets actual page number
            full_text=full_text.strip(),
            blocks=blocks,
            detected_language=None,
            engine=self.name,
            avg_confidence=round(avg_conf, 4),
            word_count=total_words,
            processing_time_ms=elapsed_ms,
        )
