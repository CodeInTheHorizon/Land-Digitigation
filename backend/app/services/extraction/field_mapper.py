"""Field mapping — maps extracted entities to LandRecord schema fields.

Takes EntitySpan objects from the NLP layer and maps them to the
structured LandRecord dict that the database layer expects.
Applies normalization and handles multi-value fields.

Pure business logic — no database or I/O dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

from app.services.nlp.entity_extractor import EntitySpan, EntityType, ExtractionResult
from app.services.extraction.normalizer import FieldNormalizer


@dataclass
class FieldProvenance:
    """Provenance for a single mapped field."""

    field_name: str
    raw_value: str
    normalized_value: Any
    confidence: float
    source_entity_type: str
    extraction_method: str
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    context: Optional[str] = None


@dataclass
class MappedRecord:
    """A structured land record assembled from extracted entities."""

    fields: Dict[str, Any] = field(default_factory=dict)
    provenance: List[FieldProvenance] = field(default_factory=list)
    persons: List[Dict[str, Any]] = field(default_factory=list)
    unmapped_entities: List[EntitySpan] = field(default_factory=list)

    @property
    def field_count(self) -> int:
        return len([v for v in self.fields.values() if v is not None])

    def get_confidence(self, field_name: str) -> Optional[float]:
        """Get the confidence for a specific field."""
        for p in self.provenance:
            if p.field_name == field_name:
                return p.confidence
        return None


# Entity type → LandRecord field name mapping
_ENTITY_TO_FIELD: Dict[EntityType, str] = {
    EntityType.SURVEY_NUMBER: "survey_number",
    EntityType.KHASRA_NUMBER: "khasra_number",
    EntityType.KHATA_NUMBER: "khata_number",
    EntityType.PLOT_NUMBER: "plot_number",
    EntityType.VILLAGE: "village",
    EntityType.TEHSIL: "tehsil",
    EntityType.DISTRICT: "district",
    EntityType.STATE: "state",
    EntityType.AREA: "area",
    EntityType.LAND_CLASSIFICATION: "land_classification",
    EntityType.OWNERSHIP_TYPE: "ownership_type",
    EntityType.REGISTRATION_NUMBER: "registration_number",
    EntityType.MUTATION_NUMBER: "mutation_number",
    EntityType.DOCUMENT_NUMBER: "document_number",
}


class FieldMapper:
    """Map extracted entities to LandRecord schema fields.

    Applies normalization, resolves conflicts (multiple entities for
    the same field), and tracks provenance.

    Thread-safe and stateless.
    """

    def __init__(self) -> None:
        self.normalizer = FieldNormalizer()

    def map_entities(
        self,
        extraction: ExtractionResult,
        *,
        document_type: Optional[str] = None,
    ) -> MappedRecord:
        """Map extraction results to a structured land record.

        Parameters
        ----------
        extraction : ExtractionResult
            Entities from the NLP entity extractor.
        document_type : str, optional
            Classification result — influences field mapping priorities.
        """
        record = MappedRecord()

        # Group entities by target field
        field_candidates: Dict[str, List[EntitySpan]] = {}
        person_entities: List[EntitySpan] = []
        date_entities: List[EntitySpan] = []
        amount_entities: List[EntitySpan] = []

        for entity in extraction.entities:
            if entity.entity_type == EntityType.PERSON:
                person_entities.append(entity)
                continue
            if entity.entity_type == EntityType.DATE:
                date_entities.append(entity)
                continue
            if entity.entity_type == EntityType.AMOUNT:
                amount_entities.append(entity)
                continue

            target_field = _ENTITY_TO_FIELD.get(entity.entity_type)
            if target_field:
                field_candidates.setdefault(target_field, []).append(entity)
            else:
                record.unmapped_entities.append(entity)

        # Resolve each field: pick highest-confidence entity
        for field_name, candidates in field_candidates.items():
            best = max(candidates, key=lambda e: e.confidence)
            normalized = self._normalize_field(field_name, best)

            record.fields[field_name] = normalized
            record.provenance.append(FieldProvenance(
                field_name=field_name,
                raw_value=best.value,
                normalized_value=normalized,
                confidence=best.confidence,
                source_entity_type=best.entity_type.value,
                extraction_method=best.extraction_method,
                page_number=best.page_number,
                char_start=best.char_start,
                char_end=best.char_end,
                context=best.context,
            ))

            # Handle area + unit compound
            if field_name == "area" and best.secondary_value:
                unit = self.normalizer.normalize_area_unit(best.secondary_value)
                record.fields["area_unit"] = unit
                record.provenance.append(FieldProvenance(
                    field_name="area_unit",
                    raw_value=best.secondary_value,
                    normalized_value=unit,
                    confidence=best.confidence,
                    source_entity_type=best.entity_type.value,
                    extraction_method=best.extraction_method,
                    page_number=best.page_number,
                    char_start=best.char_start,
                    char_end=best.char_end,
                ))

        # Map person entities
        for person_ent in person_entities:
            # Relationship names and sellers are evidence, not automatically owners.
            if re.match(r"(?:s/o|d/o|w/o|son\s+of|daughter\s+of|wife\s+of|पुत्र|पुत्री|पत्नी|seller|vendor|विक्रेता)", person_ent.raw_text, re.I):
                record.unmapped_entities.append(person_ent)
                continue
            name = self.normalizer.normalize_name(person_ent.value)
            if name and not any(c.isdigit() for c in name):
                record.persons.append({
                    "name": name,
                    "raw_name": person_ent.value,
                    "confidence": person_ent.confidence,
                    "page_number": person_ent.page_number,
                    "context": person_ent.context,
                })

        # Map dates based on document type context
        self._map_dates(record, date_entities, document_type)

        # Map amounts based on document type context
        self._map_amounts(record, amount_entities, document_type)

        # Set document_type if provided
        if document_type:
            record.fields["document_type"] = document_type

        return record

    def _normalize_field(self, field_name: str, entity: EntitySpan) -> Any:
        """Normalize a field value based on its field name."""
        value = entity.value

        if field_name in ("survey_number", "khasra_number", "khata_number", "plot_number"):
            return self.normalizer.normalize_survey_number(value)

        if field_name in ("village", "tehsil", "district", "state"):
            return self.normalizer.normalize_name(value)

        if field_name == "area":
            return self.normalizer.normalize_number(value)

        if field_name == "land_classification":
            return self.normalizer.normalize_land_classification(value)

        if field_name == "ownership_type":
            return self.normalizer.normalize_ownership_type(value)

        if field_name in ("registration_number", "mutation_number", "document_number"):
            return self.normalizer.normalize_text(value)

        return self.normalizer.normalize_text(value)

    def _map_dates(
        self,
        record: MappedRecord,
        date_entities: List[EntitySpan],
        document_type: Optional[str],
    ) -> None:
        """Map date entities to appropriate fields based on document type."""
        if not date_entities:
            return

        # Sort by confidence
        sorted_dates = sorted(date_entities, key=lambda e: -e.confidence)

        for date_ent in sorted_dates:
            normalized = self.normalizer.normalize_date(date_ent.value)
            if not normalized:
                continue

            # Determine which date field based on context and document type
            field_name = self._infer_date_field(date_ent, document_type)
            if not field_name:
                record.unmapped_entities.append(date_ent)
            if field_name and field_name not in record.fields:
                record.fields[field_name] = normalized
                record.provenance.append(FieldProvenance(
                    field_name=field_name,
                    raw_value=date_ent.value,
                    normalized_value=normalized,
                    confidence=date_ent.confidence,
                    source_entity_type=EntityType.DATE.value,
                    extraction_method=date_ent.extraction_method,
                    page_number=date_ent.page_number,
                    char_start=date_ent.char_start,
                    char_end=date_ent.char_end,
                    context=date_ent.context,
                ))

    def _map_amounts(
        self,
        record: MappedRecord,
        amount_entities: List[EntitySpan],
        document_type: Optional[str],
    ) -> None:
        """Map amount entities to appropriate fields based on document type."""
        if not amount_entities:
            return

        sorted_amounts = sorted(amount_entities, key=lambda e: -e.confidence)

        for amt_ent in sorted_amounts:
            normalized = self.normalizer.normalize_amount(amt_ent.value)
            if normalized is None:
                continue

            field_name = self._infer_amount_field(amt_ent, document_type)
            if field_name and field_name not in record.fields:
                record.fields[field_name] = normalized
                record.provenance.append(FieldProvenance(
                    field_name=field_name,
                    raw_value=amt_ent.value,
                    normalized_value=normalized,
                    confidence=amt_ent.confidence,
                    source_entity_type=EntityType.AMOUNT.value,
                    extraction_method=amt_ent.extraction_method,
                    page_number=amt_ent.page_number,
                    char_start=amt_ent.char_start,
                    char_end=amt_ent.char_end,
                    context=amt_ent.context,
                ))

    @staticmethod
    def _infer_date_field(entity: EntitySpan, document_type: Optional[str]) -> Optional[str]:
        """Infer which date field an entity belongs to from context."""
        context = (entity.context or "").lower()
        before = context.split(entity.value.lower(), 1)[0].splitlines()
        nearby = before[-1] if before else ""
        if re.search(r"birth|inspection|जन्म|निरीक्षण", nearby):
            return None
        if re.search(r"(?:mutation|नामांतरण|dakhil|दाखिल).{0,45}(?:dated?|on|दिनांक|तिथि)\s*[:.-]?\s*$", nearby):
            return "mutation_date"
        if re.search(r"(?:registration|registered|पंजीकरण|रजिस्ट्री).{0,45}(?:dated?|on|दिनांक|तिथि)\s*[:.-]?\s*$", nearby):
            return "registration_date"
        return None

    @staticmethod
    def _infer_amount_field(entity: EntitySpan, document_type: Optional[str]) -> Optional[str]:
        """Infer which amount field an entity belongs to from context."""
        context = (entity.context or "").lower()

        if any(kw in context for kw in ["stamp", "duty", "स्टाम्प", "शुल्क"]):
            return "stamp_duty"
        if any(kw in context for kw in [
            "consideration", "sale", "price", "amount", "value",
            "मूल्य", "बिक्री", "रकम",
        ]):
            return "consideration_amount"

        # Fallback: first amount is consideration
        if document_type in ("sale_deed", "registration"):
            return "consideration_amount"

        return None
