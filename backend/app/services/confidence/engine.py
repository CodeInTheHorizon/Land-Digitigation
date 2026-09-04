"""Composite confidence scoring engine.

Combines multiple confidence signals into a single per-field and
per-record score:

  1. OCR confidence     — how well the OCR engine read the text
  2. Extraction confidence — how well the pattern matched
  3. Pattern confidence  — does the value look like the expected format?
  4. Cross-field confidence — do related fields agree?
  5. Context confidence  — was the value found near relevant keywords?

Pure business logic — no database or I/O dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FieldConfidence:
    """Confidence breakdown for a single field."""

    field_name: str
    ocr_confidence: float = 0.0
    extraction_confidence: float = 0.0
    pattern_confidence: float = 0.0
    cross_field_confidence: float = 0.0
    context_confidence: float = 0.0
    composite: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "ocr": round(self.ocr_confidence, 4),
            "extraction": round(self.extraction_confidence, 4),
            "pattern": round(self.pattern_confidence, 4),
            "cross_field": round(self.cross_field_confidence, 4),
            "context": round(self.context_confidence, 4),
            "composite": round(self.composite, 4),
        }


@dataclass
class ConfidenceBreakdown:
    """Full confidence breakdown for a record."""

    field_scores: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall: float = 0.0
    field_count: int = 0
    low_confidence_fields: List[str] = field(default_factory=list)

    LOW_THRESHOLD = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 4),
            "field_count": self.field_count,
            "low_confidence_fields": self.low_confidence_fields,
            "fields": {k: v.to_dict() for k, v in self.field_scores.items()},
        }


# Weights for combining signals
_WEIGHTS = {
    "ocr": 0.25,
    "extraction": 0.30,
    "pattern": 0.20,
    "cross_field": 0.15,
    "context": 0.10,
}

# Pattern validators per field type
_FIELD_PATTERNS: Dict[str, str] = {
    "survey_number": r"^[\dA-Z/\-\.]+$",
    "khasra_number": r"^[\dA-Z/\-\.]+$",
    "khata_number": r"^[\d/\-]+$",
    "plot_number": r"^[\dA-Z/\-\.]+$",
    "area": r"^[\d,]+\.?\d*$",
    "registration_number": r"^[\dA-Za-z/\-]+$",
    "mutation_number": r"^[\dA-Za-z/\-]+$",
    "mutation_date": r"^\d{4}-\d{2}-\d{2}$",
    "registration_date": r"^\d{4}-\d{2}-\d{2}$",
}

# Cross-field consistency rules: (field_a, field_b) → check
_CROSS_FIELD_PAIRS = [
    ("survey_number", "village"),   # Survey number should come with a village
    ("khasra_number", "village"),
    ("area", "area_unit"),          # Area should have a unit
    ("village", "district"),        # Location hierarchy
    ("district", "state"),
]


class ConfidenceEngine:
    """Compute composite confidence scores for extracted land records.

    Thread-safe and stateless.
    """

    def score(
        self,
        record_fields: Dict[str, Any],
        *,
        ocr_confidence: float = 0.0,
        provenance: Optional[List[Dict[str, Any]]] = None,
    ) -> ConfidenceBreakdown:
        """Compute confidence for all fields in a record.

        Parameters
        ----------
        record_fields : dict
            Field name → value mapping from FieldMapper.
        ocr_confidence : float
            Average OCR confidence for the document (0–1).
        provenance : list of dicts, optional
            Provenance records from FieldMapper, each containing
            field_name, confidence, extraction_method, context.
        """
        prov_by_field: Dict[str, Dict[str, Any]] = {}
        if provenance:
            for p in provenance:
                prov_by_field[p.get("field_name", "")] = p

        breakdown = ConfidenceBreakdown()

        for field_name, value in record_fields.items():
            if value is None:
                continue

            prov = prov_by_field.get(field_name, {})
            fc = self._score_field(
                field_name, value,
                ocr_confidence=ocr_confidence,
                extraction_conf=prov.get("confidence", 0.5),
                extraction_method=prov.get("extraction_method", ""),
                context=prov.get("context", ""),
                all_fields=record_fields,
            )
            breakdown.field_scores[field_name] = fc

            if fc.composite < ConfidenceBreakdown.LOW_THRESHOLD:
                breakdown.low_confidence_fields.append(field_name)

        # Overall confidence: weighted average of field composites
        if breakdown.field_scores:
            composites = [fc.composite for fc in breakdown.field_scores.values()]
            breakdown.overall = round(sum(composites) / len(composites), 4)
        breakdown.field_count = len(breakdown.field_scores)

        return breakdown

    def _score_field(
        self,
        field_name: str,
        value: Any,
        *,
        ocr_confidence: float,
        extraction_conf: float,
        extraction_method: str,
        context: str,
        all_fields: Dict[str, Any],
    ) -> FieldConfidence:
        """Score a single field."""
        fc = FieldConfidence(field_name=field_name)

        # 1. OCR confidence (passed through)
        fc.ocr_confidence = min(1.0, max(0.0, ocr_confidence))

        # 2. Extraction confidence (from the entity extractor)
        fc.extraction_confidence = min(1.0, max(0.0, extraction_conf))

        # 3. Pattern confidence — does value match expected format?
        fc.pattern_confidence = self._pattern_score(field_name, value)

        # 4. Cross-field confidence — do related fields exist and agree?
        fc.cross_field_confidence = self._cross_field_score(field_name, all_fields)

        # 5. Context confidence — was value found near relevant keywords?
        fc.context_confidence = self._context_score(field_name, context)

        # Weighted composite
        fc.composite = round(
            fc.ocr_confidence * _WEIGHTS["ocr"]
            + fc.extraction_confidence * _WEIGHTS["extraction"]
            + fc.pattern_confidence * _WEIGHTS["pattern"]
            + fc.cross_field_confidence * _WEIGHTS["cross_field"]
            + fc.context_confidence * _WEIGHTS["context"],
            4,
        )

        return fc

    @staticmethod
    def _pattern_score(field_name: str, value: Any) -> float:
        """Check if value matches the expected pattern for its field."""
        pattern = _FIELD_PATTERNS.get(field_name)
        if not pattern:
            # No pattern defined — assume acceptable
            return 0.7

        str_value = str(value).strip()
        if not str_value:
            return 0.0

        if re.match(pattern, str_value):
            return 1.0

        # Partial match: some characters are valid
        valid_chars = sum(1 for c in str_value if re.match(r"[\dA-Za-z/\-\.]", c))
        ratio = valid_chars / len(str_value) if str_value else 0.0
        return round(ratio * 0.7, 4)  # Cap at 0.7 for partial match

    @staticmethod
    def _cross_field_score(field_name: str, all_fields: Dict[str, Any]) -> float:
        """Check if related fields are present and consistent."""
        related_present = 0
        related_total = 0

        for field_a, field_b in _CROSS_FIELD_PAIRS:
            if field_name == field_a:
                related_total += 1
                if field_b in all_fields and all_fields[field_b]:
                    related_present += 1
            elif field_name == field_b:
                related_total += 1
                if field_a in all_fields and all_fields[field_a]:
                    related_present += 1

        if related_total == 0:
            return 0.7  # No cross-field rules — neutral

        return round(related_present / related_total, 4)

    @staticmethod
    def _context_score(field_name: str, context: str) -> float:
        """Score based on contextual keywords near the extracted value."""
        if not context:
            return 0.5  # No context available — neutral

        context_lower = context.lower()

        # Field-specific context keywords
        _CONTEXT_KEYWORDS: Dict[str, List[str]] = {
            "survey_number": ["survey", "सर्वे", "no", "number"],
            "khasra_number": ["khasra", "खसरा", "no", "number"],
            "khata_number": ["khata", "खाता", "no", "number"],
            "village": ["village", "gram", "ग्राम", "गांव", "mouza"],
            "tehsil": ["tehsil", "taluka", "तहसील"],
            "district": ["district", "zila", "जिला"],
            "area": ["area", "क्षेत्रफल", "रकबा", "total"],
            "mutation_date": ["mutation", "नामांतरण", "date", "दिनांक"],
            "registration_date": ["registration", "पंजीकरण", "date", "दिनांक"],
        }

        keywords = _CONTEXT_KEYWORDS.get(field_name, [])
        if not keywords:
            return 0.6

        found = sum(1 for kw in keywords if kw in context_lower)
        return round(min(1.0, found / max(1, len(keywords) * 0.5)), 4)
