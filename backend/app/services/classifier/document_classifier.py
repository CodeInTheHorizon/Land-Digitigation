"""Document classifier for Indian land records.

Classifies OCR-extracted text into one of 10 document categories using
a multi-signal scoring approach:
  1. Keyword frequency scoring (weighted)
  2. Header/title pattern matching (high-weight)
  3. Structural pattern detection (format-specific markers)

Pure business logic — no database or I/O dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class DocumentCategory(str, Enum):
    """The 10 supported land record document types."""

    LAND_OWNERSHIP = "land_ownership"
    KHASRA = "khasra"
    KHATA = "khata"
    MUTATION = "mutation"
    REGISTRATION = "registration"
    SALE_DEED = "sale_deed"
    LEASE = "lease"
    LAND_MAP = "land_map"
    TAX_REVENUE = "tax_revenue"
    MISCELLANEOUS = "miscellaneous"


@dataclass
class ClassificationResult:
    """Result of document classification."""

    category: DocumentCategory
    confidence: float  # 0.0 – 1.0
    scores: Dict[str, float] = field(default_factory=dict)
    matched_keywords: List[str] = field(default_factory=list)
    matched_headers: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Keyword dictionaries — English + Hindi/Devanagari
# Weight: (keyword, weight).  Higher weight = stronger signal.
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: Dict[DocumentCategory, List[Tuple[str, float]]] = {
    DocumentCategory.LAND_OWNERSHIP: [
        # English
        ("ownership certificate", 3.0),
        ("title deed", 3.0),
        ("record of rights", 3.0),
        ("land title", 2.5),
        ("right of ownership", 2.5),
        ("patta", 2.5),
        ("owner", 1.5),
        ("proprietor", 1.5),
        ("possession", 1.5),
        # Hindi
        ("अधिकार अभिलेख", 3.0),
        ("स्वामित्व", 2.5),
        ("पट्टा", 2.5),
        ("मालिक", 1.5),
        ("भूमि अधिकार", 2.5),
        ("जमाबंदी", 2.5),
    ],
    DocumentCategory.KHASRA: [
        ("khasra", 3.0),
        ("khasra number", 3.0),
        ("khasra no", 3.0),
        ("field book", 2.0),
        ("crop inspection", 2.0),
        ("girdawari", 2.5),
        ("fasal", 1.5),
        ("crop", 1.5),
        # Hindi
        ("खसरा", 3.0),
        ("खसरा नंबर", 3.0),
        ("गिरदावरी", 2.5),
        ("फसल", 1.5),
        ("खसरा खतौनी", 3.0),
    ],
    DocumentCategory.KHATA: [
        ("khata", 3.0),
        ("khata number", 3.0),
        ("khatauni", 3.0),
        ("khatauni number", 3.0),
        ("account", 1.0),
        ("ledger", 1.5),
        # Hindi
        ("खाता", 3.0),
        ("खतौनी", 3.0),
        ("खाता नंबर", 3.0),
        ("खतौनी नंबर", 3.0),
        ("नामांतरण", 1.5),
    ],
    DocumentCategory.MUTATION: [
        ("mutation", 3.0),
        ("mutation order", 3.0),
        ("mutation register", 3.0),
        ("transfer of ownership", 2.5),
        ("inheritance", 2.0),
        ("succession", 2.0),
        ("partition", 2.0),
        ("dakhil kharij", 3.0),
        # Hindi
        ("दाखिल खारिज", 3.0),
        ("नामांतरण", 3.0),
        ("हस्तांतरण", 2.5),
        ("विरासत", 2.0),
        ("उत्तराधिकार", 2.0),
        ("बटवारा", 2.0),
    ],
    DocumentCategory.REGISTRATION: [
        ("registration", 2.5),
        ("registered document", 3.0),
        ("sub registrar", 3.0),
        ("registration number", 3.0),
        ("registration office", 2.5),
        ("registered", 1.5),
        # Hindi
        ("पंजीकरण", 3.0),
        ("उप पंजीयक", 3.0),
        ("पंजीकृत", 2.0),
        ("रजिस्ट्री", 3.0),
    ],
    DocumentCategory.SALE_DEED: [
        ("sale deed", 3.0),
        ("conveyance deed", 3.0),
        ("deed of sale", 3.0),
        ("buyer", 2.0),
        ("seller", 2.0),
        ("vendee", 2.0),
        ("vendor", 2.0),
        ("consideration amount", 2.5),
        ("stamp duty", 2.0),
        ("sale price", 2.0),
        # Hindi
        ("बैनामा", 3.0),
        ("विक्रय पत्र", 3.0),
        ("क्रेता", 2.0),
        ("विक्रेता", 2.0),
        ("बिक्री", 2.0),
        ("मूल्य", 1.5),
        ("स्टाम्प शुल्क", 2.0),
    ],
    DocumentCategory.LEASE: [
        ("lease", 2.5),
        ("lease deed", 3.0),
        ("lease agreement", 3.0),
        ("lessee", 2.5),
        ("lessor", 2.5),
        ("rent", 2.0),
        ("lease period", 2.5),
        ("tenure", 2.0),
        # Hindi
        ("पट्टा", 2.5),  # also used for ownership patta — context matters
        ("किराया", 2.0),
        ("पट्टेदार", 2.5),
        ("अवधि", 1.5),
        ("लीज", 3.0),
    ],
    DocumentCategory.LAND_MAP: [
        ("map", 2.0),
        ("survey map", 3.0),
        ("plot map", 3.0),
        ("cadastral map", 3.0),
        ("tippan", 3.0),
        ("boundary", 2.0),
        ("north", 1.0),
        ("south", 1.0),
        ("east", 1.0),
        ("west", 1.0),
        ("scale", 1.5),
        # Hindi
        ("नक्शा", 3.0),
        ("भू-नक्शा", 3.0),
        ("सीमा", 2.0),
        ("टिप्पण", 3.0),
        ("उत्तर", 1.0),
        ("दक्षिण", 1.0),
        ("पूर्व", 1.0),
        ("पश्चिम", 1.0),
    ],
    DocumentCategory.TAX_REVENUE: [
        ("tax", 2.0),
        ("revenue", 2.0),
        ("tax receipt", 3.0),
        ("land revenue", 3.0),
        ("lagaan", 3.0),
        ("maalkhana", 2.5),
        ("assessment", 2.0),
        ("demand notice", 2.5),
        ("payment", 1.5),
        # Hindi
        ("कर", 2.0),
        ("राजस्व", 2.5),
        ("लगान", 3.0),
        ("मालखाना", 2.5),
        ("भू-राजस्व", 3.0),
        ("रसीद", 2.5),
        ("कर रसीद", 3.0),
        ("मांग पत्र", 2.5),
    ],
    DocumentCategory.MISCELLANEOUS: [
        # Fallback — low weights, broad terms
        ("land", 0.5),
        ("document", 0.3),
        ("certificate", 0.5),
        ("भूमि", 0.5),
        ("प्रमाण पत्र", 0.5),
    ],
}

# Header patterns — high-confidence signals found in document titles
_HEADER_PATTERNS: Dict[DocumentCategory, List[str]] = {
    DocumentCategory.LAND_OWNERSHIP: [
        r"record\s+of\s+rights",
        r"right\s+record",
        r"अधिकार\s*अभिलेख",
        r"jamabandi",
        r"जमाबंदी",
    ],
    DocumentCategory.KHASRA: [
        r"khasra\s*(girdawari|register|no)",
        r"खसरा\s*(गिरदावरी|रजिस्टर|नं)",
        r"field\s+book",
    ],
    DocumentCategory.KHATA: [
        r"khatauni",
        r"khata\s+number",
        r"खतौनी",
        r"खाता\s*नंबर",
    ],
    DocumentCategory.MUTATION: [
        r"mutation\s*(order|register|entry)",
        r"dakhil\s*kharij",
        r"दाखिल\s*खारिज",
        r"नामांतरण\s*(आदेश|रजिस्टर)",
    ],
    DocumentCategory.REGISTRATION: [
        r"registered\s+document",
        r"registration\s+certificate",
        r"sub\s*registrar",
        r"उप\s*पंजीयक",
    ],
    DocumentCategory.SALE_DEED: [
        r"sale\s+deed",
        r"conveyance\s+deed",
        r"deed\s+of\s+(sale|conveyance)",
        r"बैनामा",
        r"विक्रय\s*पत्र",
    ],
    DocumentCategory.LEASE: [
        r"lease\s+(deed|agreement)",
        r"लीज\s*(करार|समझौता)",
    ],
    DocumentCategory.LAND_MAP: [
        r"(survey|cadastral|plot)\s+map",
        r"(भू|सर्वे)\s*नक्शा",
        r"tippan",
        r"टिप्पण",
    ],
    DocumentCategory.TAX_REVENUE: [
        r"(land\s+)?revenue\s+receipt",
        r"tax\s+receipt",
        r"(भू\s*)?राजस्व\s*रसीद",
        r"कर\s*रसीद",
        r"lagaan",
    ],
}


class DocumentClassifier:
    """Classify a document from its OCR text into one of 10 land-record categories.

    Uses a weighted multi-signal approach:
      - Keyword frequency scoring (body text)
      - Header pattern matching (first ~500 chars, high weight)
      - Structural markers (tables, specific formatting)

    Thread-safe and stateless — instantiate once, call ``classify()`` repeatedly.
    """

    # Header text is the first N characters — title/heading area
    HEADER_CHAR_LIMIT = 500
    # Minimum confidence to avoid MISCELLANEOUS fallback
    MIN_CONFIDENCE_THRESHOLD = 0.15

    def classify(
        self,
        text: str,
        *,
        page_count: int = 1,
    ) -> ClassificationResult:
        """Classify document text into a category.

        Parameters
        ----------
        text : str
            Full OCR-extracted text (all pages concatenated).
        page_count : int
            Number of pages — used for structural heuristics.
        """
        if not text or not text.strip():
            return ClassificationResult(
                category=DocumentCategory.MISCELLANEOUS,
                confidence=0.0,
            )

        text_lower = text.lower()
        header_text = text_lower[: self.HEADER_CHAR_LIMIT]

        scores: Dict[str, float] = {}
        all_matched_keywords: Dict[str, List[str]] = {}
        all_matched_headers: Dict[str, List[str]] = {}

        for category in DocumentCategory:
            score = 0.0
            matched_kw: List[str] = []
            matched_hd: List[str] = []

            # --- Signal 1: Keyword scoring ---
            kw_list = _CATEGORY_KEYWORDS.get(category, [])
            for keyword, weight in kw_list:
                kw_lower = keyword.lower()
                count = text_lower.count(kw_lower)
                if count > 0:
                    # Diminishing returns: sqrt scaling for repeated hits
                    score += weight * (count ** 0.5)
                    matched_kw.append(keyword)

            # --- Signal 2: Header pattern matching (3x weight) ---
            hd_list = _HEADER_PATTERNS.get(category, [])
            for pattern in hd_list:
                if re.search(pattern, header_text, re.IGNORECASE | re.UNICODE):
                    score += 5.0  # Header match is a strong signal
                    matched_hd.append(pattern)

            # --- Signal 3: Structural heuristics ---
            score += self._structural_score(category, text_lower, page_count)

            scores[category.value] = round(score, 3)
            all_matched_keywords[category.value] = matched_kw
            all_matched_headers[category.value] = matched_hd

        # Normalize scores to 0–1 range
        max_score = max(scores.values()) if scores else 0.0
        if max_score > 0:
            normalized = {k: round(v / max_score, 4) for k, v in scores.items()}
        else:
            normalized = {k: 0.0 for k in scores}

        # Pick winner
        best_category_str = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_confidence = normalized[best_category_str]

        # Fall back to MISCELLANEOUS if confidence is too low
        if best_confidence < self.MIN_CONFIDENCE_THRESHOLD:
            best_category_str = DocumentCategory.MISCELLANEOUS.value
            best_confidence = 0.0

        best_category = DocumentCategory(best_category_str)

        return ClassificationResult(
            category=best_category,
            confidence=round(best_confidence, 4),
            scores=normalized,
            matched_keywords=all_matched_keywords.get(best_category_str, []),
            matched_headers=all_matched_headers.get(best_category_str, []),
        )

    @staticmethod
    def _structural_score(
        category: DocumentCategory,
        text_lower: str,
        page_count: int,
    ) -> float:
        """Bonus score from structural/format heuristics."""
        score = 0.0

        if category == DocumentCategory.KHASRA:
            # Khasra records often have tabular crop data
            if re.search(r"(rabi|kharif|zaid|रबी|खरीफ|जायद)", text_lower):
                score += 2.0

        elif category == DocumentCategory.SALE_DEED:
            # Sale deeds mention consideration, witnesses, stamp
            witnesses = len(re.findall(r"(witness|गवाह|साक्षी)", text_lower))
            if witnesses >= 2:
                score += 1.5
            if re.search(r"(stamp\s+duty|stamp\s+paper|स्टाम्प)", text_lower):
                score += 1.5

        elif category == DocumentCategory.LAND_MAP:
            # Maps are usually single-page, mention scale and directions
            if page_count == 1:
                score += 0.5
            directions = sum(
                1 for d in ["north", "south", "east", "west", "उत्तर", "दक्षिण", "पूर्व", "पश्चिम"]
                if d in text_lower
            )
            if directions >= 3:
                score += 2.0

        elif category == DocumentCategory.TAX_REVENUE:
            # Revenue receipts mention amounts with ₹ or Rs
            if re.search(r"(₹|rs\.?\s*\d|रु\.?\s*\d)", text_lower):
                score += 1.5

        elif category == DocumentCategory.MUTATION:
            # Mutation orders have from→to owner pattern
            if re.search(r"(from\s+.*?\s+to\s+|से\s+.*?\s+को\s+)", text_lower):
                score += 2.0

        return score
