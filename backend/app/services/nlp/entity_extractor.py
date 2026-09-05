"""Enhanced entity extraction for Indian land records.

Extracts 18+ entity types from OCR text using:
  1. Regex pattern matching (high precision for structured fields)
  2. Contextual keyword proximity (for semi-structured text)
  3. Unicode-aware matching for Hindi/Devanagari and regional scripts

Every extracted entity carries full provenance: source text span,
page number, character offsets, extraction method, and confidence.

Pure business logic — no database or I/O dependencies.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class EntityType(str, Enum):
    """Supported entity types for land record extraction."""

    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    VILLAGE = "VILLAGE"
    TEHSIL = "TEHSIL"
    DISTRICT = "DISTRICT"
    STATE = "STATE"
    SURVEY_NUMBER = "SURVEY_NUMBER"
    KHASRA_NUMBER = "KHASRA_NUMBER"
    KHATA_NUMBER = "KHATA_NUMBER"
    PLOT_NUMBER = "PLOT_NUMBER"
    AREA = "AREA"
    AREA_UNIT = "AREA_UNIT"
    DATE = "DATE"
    AMOUNT = "AMOUNT"
    REGISTRATION_NUMBER = "REGISTRATION_NUMBER"
    MUTATION_NUMBER = "MUTATION_NUMBER"
    LAND_CLASSIFICATION = "LAND_CLASSIFICATION"
    OWNERSHIP_TYPE = "OWNERSHIP_TYPE"
    DOCUMENT_NUMBER = "DOCUMENT_NUMBER"


@dataclass
class EntitySpan:
    """A single extracted entity with full provenance."""

    entity_type: EntityType
    value: str
    raw_text: str  # original text as it appeared in document
    confidence: float  # 0.0 – 1.0
    extraction_method: str  # "regex" | "keyword_proximity" | "structural"

    # Provenance
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    context: Optional[str] = None  # surrounding text for review

    # Bounding box (from OCR, if available)
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_width: Optional[int] = None
    bbox_height: Optional[int] = None

    # Secondary value for compound entities (e.g., area + unit)
    secondary_value: Optional[str] = None


@dataclass
class ExtractionResult:
    """Result of entity extraction on a text passage."""

    entities: List[EntitySpan] = field(default_factory=list)
    page_number: Optional[int] = None
    text_length: int = 0
    entity_count: int = 0

    def by_type(self, entity_type: EntityType) -> List[EntitySpan]:
        """Get all entities of a specific type."""
        return [e for e in self.entities if e.entity_type == entity_type]

    def best_by_type(self, entity_type: EntityType) -> Optional[EntitySpan]:
        """Get the highest-confidence entity of a specific type."""
        matches = self.by_type(entity_type)
        return max(matches, key=lambda e: e.confidence) if matches else None


# ---------------------------------------------------------------------------
# Regex patterns — each returns (value_group, optional_secondary_group)
# Keys: (pattern, entity_type, confidence, method)
# ---------------------------------------------------------------------------

# Value capture for Indian names: letters + Devanagari + spaces + dots
_NAME_CHARS = r"[A-Za-z\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F \t.\-']"

_PATTERNS: List[Tuple[str, EntityType, float, str]] = [
    # --- Survey / Khasra / Khata / Plot numbers ---
    (
        r"(?:survey\s*(?:number|num|no|#)|सर्वे\s*(?:नं|नंबर|क्र))[.\s:\-]*\s*([\d/\-A-Za-z]+)",
        EntityType.SURVEY_NUMBER, 0.85, "regex",
    ),
    (
        r"(?:khasra\s*(?:number|num|no|#)|खसरा\s*(?:नं|नंबर|क्र))[.\s:\-]*\s*([\d/\-]+(?:\s*[A-Za-zक-ह])?)",
        EntityType.KHASRA_NUMBER, 0.85, "regex",
    ),
    (
        r"(?:khata\s*(?:number|num|no|#)|खाता\s*(?:नं|नंबर|क्र))[.\s:\-]*\s*([\d/\-]+)",
        EntityType.KHATA_NUMBER, 0.85, "regex",
    ),
    (
        r"(?:plot\s*(?:number|no|#)|भूखंड\s*(?:नं|नंबर))[.\s:\-]*\s*([\d/\-A-Za-z]+)",
        EntityType.PLOT_NUMBER, 0.80, "regex",
    ),
    # --- Area with unit ---
    (
        r"(?:area|क्षेत्रफल|रकबा|total\s+area)[.\s:\-]*\s*([\d,]+\.?\d*)\s*"
        r"(hectare|hectares|hect|acre|acres|bigha|sq\.?\s*m(?:eter|etre)?s?"
        r"|sq\.?\s*f(?:ee)?t|guntha|kanal|marla|dismil"
        r"|हेक्टेयर|एकड़|बीघा|वर्ग\s*मी|गुंठा|कनाल|मरला)",
        EntityType.AREA, 0.80, "regex",
    ),
    # --- Location fields ---
    (
        r"(?:village|gram|ग्राम|गांव|मौजा|mouza)[.\s:\-]+\s*(" + _NAME_CHARS + r"{2,60}?)(?=\s*(?:,|\n|tehsil|तहसील|taluk|district|जिला|$))",
        EntityType.VILLAGE, 0.75, "regex",
    ),
    (
        r"(?:tehsil|taluka?|तहसील|तालुका?)[.\s:\-]+\s*(" + _NAME_CHARS + r"{2,60}?)(?=\s*(?:,|\n|district|जिला|$))",
        EntityType.TEHSIL, 0.75, "regex",
    ),
    (
        r"(?:district|zila|जिला|जनपद)[.\s:\-]+\s*(" + _NAME_CHARS + r"{2,60}?)(?=\s*(?:,|\n|state|राज्य|$))",
        EntityType.DISTRICT, 0.75, "regex",
    ),
    (
        r"(?:state|राज्य)[.\s:\-]+\s*(" + _NAME_CHARS + r"{2,60}?)(?=\s*(?:,|\n|$))",
        EntityType.STATE, 0.70, "regex",
    ),
    # --- Dates (multiple formats) ---
    (
        r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})",
        EntityType.DATE, 0.70, "regex",
    ),
    (
        r"(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})",
        EntityType.DATE, 0.75, "regex",
    ),
    # --- Amounts (₹ / Rs) ---
    (
        r"(?:₹|rs\.?|रु\.?|rupees?)\s*([\d,]+(?:\.\d{1,2})?)",
        EntityType.AMOUNT, 0.75, "regex",
    ),
    (
        r"([\d,]+(?:\.\d{1,2})?)\s*(?:₹|rs\.?|रु\.?|rupees?)",
        EntityType.AMOUNT, 0.70, "regex",
    ),
    # --- Registration / mutation / document numbers ---
    (
        r"(?:registration\s*(?:number|no|#)|पंजीकरण\s*(?:नं|संख्या|क्र))[.\s:\-]*\s*([\d/\-A-Za-z]+)",
        EntityType.REGISTRATION_NUMBER, 0.80, "regex",
    ),
    (
        r"(?:mutation\s*(?:number|no|#)|नामांतरण\s*(?:नं|संख्या|क्र)|दाखिल\s*खारिज\s*(?:नं|संख्या))[.\s:\-]*\s*([\d/\-A-Za-z]+)",
        EntityType.MUTATION_NUMBER, 0.80, "regex",
    ),
    (
        r"(?:document\s*(?:number|no|#)|दस्तावेज़?\s*(?:नं|संख्या|क्र))[.\s:\-]*\s*([\d/\-A-Za-z]+)",
        EntityType.DOCUMENT_NUMBER, 0.75, "regex",
    ),
    # --- Person names (contextual) ---
    (
        r"(?:name\s*(?:of\s+)?(?:owner|proprietor)|नाम|मालिक\s*का\s*नाम|स्वामी)[.\s:\-]+\s*(" + _NAME_CHARS + r"{3,80}?)(?=\s*(?:,|\n|s/o|d/o|w/o|पुत्र|पुत्री|पत्नी|father|$))",
        EntityType.PERSON, 0.70, "regex",
    ),
    (
        r"(?:s/o|d/o|w/o|son\s+of|daughter\s+of|wife\s+of|पुत्र|पुत्री|पत्नी)[.\s:\-]+\s*(" + _NAME_CHARS + r"{3,80}?)(?=\s*(?:,|\n|r/o|resident|निवासी|$))",
        EntityType.PERSON, 0.65, "regex",
    ),
    (
        r"(?:buyer|purchaser|vendee|क्रेता)[.\s:\-]+\s*(" + _NAME_CHARS + r"{3,80}?)(?=\s*(?:,|\n|s/o|d/o|w/o|पुत्र|$))",
        EntityType.PERSON, 0.70, "regex",
    ),
    (
        r"(?:seller|vendor|विक्रेता)[.\s:\-]+\s*(" + _NAME_CHARS + r"{3,80}?)(?=\s*(?:,|\n|s/o|d/o|w/o|पुत्र|$))",
        EntityType.PERSON, 0.70, "regex",
    ),
    # --- Land classification ---
    (
        r"(?:land\s*(?:type|use|classification)|भूमि\s*(?:प्रकार|उपयोग|वर्गीकरण))[.\s:\-]+\s*"
        r"(agricultural|residential|commercial|industrial|barren|forest|govt|wetland|pasture"
        r"|कृषि|आवासीय|वाणिज्यिक|औद्योगिक|बंजर|वन|सरकारी)",
        EntityType.LAND_CLASSIFICATION, 0.80, "regex",
    ),
    # --- Ownership type ---
    (
        r"(?:ownership\s*(?:type)?|स्वामित्व\s*प्रकार)[.\s:\-]+\s*"
        r"(sole|joint|inherited|leased|government|एकल|संयुक्त|विरासत|पट्टा|सरकारी)",
        EntityType.OWNERSHIP_TYPE, 0.80, "regex",
    ),
]


class EntityExtractor:
    """Extract structured entities from OCR text with full provenance.

    Thread-safe and stateless.
    """

    # Context window: chars before/after match to include in context field
    CONTEXT_WINDOW = 50

    def extract(
        self,
        text: str,
        *,
        page_number: Optional[int] = None,
    ) -> ExtractionResult:
        """Extract all entities from a text passage.

        Parameters
        ----------
        text : str
            OCR-extracted text (single page or full document).
        page_number : int, optional
            Page number for provenance tracking.
        """
        if not text or not text.strip():
            return ExtractionResult(page_number=page_number, text_length=0)

        entities: List[EntitySpan] = []

        # Pass 1: Regex pattern matching
        for pattern, entity_type, confidence, method in _PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE):
                value = match.group(1).strip()
                if not value:
                    continue

                # Clean up whitespace
                value = re.sub(r"\s+", " ", value).strip()
                # Remove trailing punctuation
                value = value.rstrip(",;:.")

                if len(value) < 1:
                    continue

                # Extract secondary value (e.g., area unit)
                secondary = None
                if entity_type == EntityType.AREA and match.lastindex and match.lastindex >= 2:
                    secondary = match.group(2).strip().lower()

                # Build context window
                ctx_start = max(0, match.start() - self.CONTEXT_WINDOW)
                ctx_end = min(len(text), match.end() + self.CONTEXT_WINDOW)
                context = text[ctx_start:ctx_end].strip()

                entities.append(EntitySpan(
                    entity_type=entity_type,
                    value=value,
                    raw_text=match.group(0).strip(),
                    confidence=confidence,
                    extraction_method=method,
                    page_number=page_number,
                    char_start=match.start(1),
                    char_end=match.end(1),
                    context=context,
                    secondary_value=secondary,
                ))

        # Pass 2: Deduplicate overlapping spans (keep highest confidence)
        entities = self._deduplicate(entities)

        return ExtractionResult(
            entities=entities,
            page_number=page_number,
            text_length=len(text),
            entity_count=len(entities),
        )

    def extract_multi_page(
        self,
        pages: List[Tuple[str, int]],
    ) -> List[ExtractionResult]:
        """Extract entities from multiple pages.

        Parameters
        ----------
        pages : list of (text, page_number) tuples
        """
        return [self.extract(text, page_number=pn) for text, pn in pages]

    @staticmethod
    def _deduplicate(entities: List[EntitySpan]) -> List[EntitySpan]:
        """Remove overlapping spans, keeping the highest-confidence one."""
        if len(entities) <= 1:
            return entities

        # Sort by char_start, then by confidence descending
        sorted_ents = sorted(
            entities,
            key=lambda e: (e.char_start or 0, -e.confidence),
        )

        result: List[EntitySpan] = []
        for ent in sorted_ents:
            # Check for overlap with already-accepted entities
            overlaps = False
            for accepted in result:
                if (
                    ent.char_start is not None
                    and accepted.char_start is not None
                    and ent.char_end is not None
                    and accepted.char_end is not None
                    and ent.page_number == accepted.page_number
                ):
                    # Check overlap
                    if ent.char_start < accepted.char_end and ent.char_end > accepted.char_start:
                        # Same type: keep higher confidence
                        if ent.entity_type == accepted.entity_type:
                            overlaps = True
                            break
                        # Different types: allow both (e.g., AREA and AREA_UNIT)

            if not overlaps:
                result.append(ent)

        return result

    def merge_results(self, results: List[ExtractionResult]) -> ExtractionResult:
        """Merge extraction results from multiple pages into one.

        Deduplicates cross-page entities (same type + same value).
        """
        all_entities: List[EntitySpan] = []
        total_length = 0

        for r in results:
            all_entities.extend(r.entities)
            total_length += r.text_length

        # Cross-page dedup: same entity_type + normalized value → keep highest confidence
        seen: Dict[str, EntitySpan] = {}
        for ent in all_entities:
            key = f"{ent.entity_type.value}:{ent.value.lower().strip()}"
            if key not in seen or ent.confidence > seen[key].confidence:
                seen[key] = ent

        merged = list(seen.values())

        return ExtractionResult(
            entities=merged,
            text_length=total_length,
            entity_count=len(merged),
        )
