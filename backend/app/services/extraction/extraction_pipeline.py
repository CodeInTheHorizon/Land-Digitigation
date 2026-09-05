"""Extraction pipeline orchestrator.

Wires together:
  DocumentClassifier → EntityExtractor → FieldMapper → ConfidenceEngine → ValidationEngine

Operates on the output of the Phase 1 OCR pipeline (PipelineResult).
Pure business logic — no database or I/O dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.services.classifier import ClassificationResult, DocumentClassifier
from app.services.confidence import ConfidenceBreakdown, ConfidenceEngine
from app.services.extraction.field_mapper import FieldMapper, MappedRecord
from app.services.nlp.entity_extractor import EntityExtractor, ExtractionResult
from app.services.validation import ValidationEngine, ValidationResult
from app.services.extraction.structured_record import enrich_record, structured_data

logger = get_logger(__name__)


@dataclass
class ExtractionPipelineResult:
    """Complete result of the extraction pipeline."""

    classification: Optional[ClassificationResult] = None
    extraction: Optional[ExtractionResult] = None
    mapped_record: Optional[MappedRecord] = None
    confidence: Optional[ConfidenceBreakdown] = None
    validation: Optional[ValidationResult] = None
    processing_time_ms: int = 0
    errors: List[str] = field(default_factory=list)
    structured_data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class ExtractionPipeline:
    """Orchestrates the full extraction pipeline.

    Stateless — instantiate, call ``extract()``, discard.
    Each service is created once and reused across calls.
    """

    def __init__(self) -> None:
        self.classifier = DocumentClassifier()
        self.entity_extractor = EntityExtractor()
        self.field_mapper = FieldMapper()
        self.confidence_engine = ConfidenceEngine()
        self.validation_engine = ValidationEngine()

    def extract(
        self,
        full_text: str,
        *,
        page_texts: Optional[List[str]] = None,
        page_count: int = 1,
        ocr_confidence: float = 0.0,
    ) -> ExtractionPipelineResult:
        """Run the full extraction pipeline on OCR text.

        Parameters
        ----------
        full_text : str
            Concatenated OCR text from all pages.
        page_texts : list of str, optional
            Per-page OCR text for page-level extraction.
        page_count : int
            Number of pages in the document.
        ocr_confidence : float
            Average OCR confidence (0–1).
        """
        start = time.monotonic()
        result = ExtractionPipelineResult()

        # --- Stage 1: Document Classification ---
        try:
            result.classification = self.classifier.classify(
                full_text, page_count=page_count,
            )
            logger.info(
                "extraction.classified",
                category=result.classification.category.value,
                confidence=result.classification.confidence,
            )
        except Exception as exc:
            logger.error("extraction.classification_failed", error=str(exc))
            result.errors.append(f"Classification failed: {exc}")

        doc_type = (
            result.classification.category.value
            if result.classification
            else None
        )

        # --- Stage 2: Entity Extraction ---
        try:
            if page_texts:
                # Per-page extraction with provenance
                page_results = self.entity_extractor.extract_multi_page(
                    [(text, i + 1) for i, text in enumerate(page_texts)]
                )
                result.extraction = self.entity_extractor.merge_results(page_results)
            else:
                result.extraction = self.entity_extractor.extract(
                    full_text, page_number=1,
                )
            logger.info(
                "extraction.entities_extracted",
                count=result.extraction.entity_count,
            )
        except Exception as exc:
            logger.error("extraction.entity_extraction_failed", error=str(exc))
            result.errors.append(f"Entity extraction failed: {exc}")

        # --- Stage 3: Field Mapping & Normalization ---
        if result.extraction:
            try:
                result.mapped_record = self.field_mapper.map_entities(
                    result.extraction,
                    document_type=doc_type,
                )
                additional, result.warnings = enrich_record(result.mapped_record, full_text)
                result.structured_data = structured_data(
                    result.mapped_record.fields, result.mapped_record.persons,
                    document_type=doc_type, additional=additional, raw_text=full_text,
                )
                logger.info(
                    "extraction.fields_mapped",
                    field_count=result.mapped_record.field_count,
                    person_count=len(result.mapped_record.persons),
                )
            except Exception as exc:
                logger.error("extraction.field_mapping_failed", error=str(exc))
                result.errors.append(f"Field mapping failed: {exc}")

        # --- Stage 4: Confidence Scoring ---
        if result.mapped_record:
            try:
                provenance_dicts = [
                    {
                        "field_name": p.field_name,
                        "confidence": p.confidence,
                        "extraction_method": p.extraction_method,
                        "context": p.context,
                    }
                    for p in result.mapped_record.provenance
                ]
                result.confidence = self.confidence_engine.score(
                    result.mapped_record.fields,
                    ocr_confidence=ocr_confidence,
                    provenance=provenance_dicts,
                )
                logger.info(
                    "extraction.confidence_scored",
                    overall=result.confidence.overall,
                    low_fields=len(result.confidence.low_confidence_fields),
                )
            except Exception as exc:
                logger.error("extraction.confidence_scoring_failed", error=str(exc))
                result.errors.append(f"Confidence scoring failed: {exc}")

        # --- Stage 5: Deterministic Validation ---
        if result.mapped_record:
            try:
                validation_input = dict(result.mapped_record.fields)
                validation_input["persons"] = result.mapped_record.persons

                # Inject confidence data for threshold checks
                if result.confidence:
                    validation_input["field_confidences"] = result.confidence.to_dict().get("fields", {})

                result.validation = self.validation_engine.validate(validation_input)
                logger.info(
                    "extraction.validated",
                    status=result.validation.status,
                    passed=result.validation.passed_count,
                    failed=result.validation.failed_count,
                    warnings=result.validation.warning_count,
                    reviews=result.validation.review_count,
                )
            except Exception as exc:
                logger.error("extraction.validation_failed", error=str(exc))
                result.errors.append(f"Validation failed: {exc}")

        result.processing_time_ms = int((time.monotonic() - start) * 1000)
        if not full_text.strip():
            result.warnings.append("No readable OCR text was found. Upload a clearer scan or review manually.")
        elif not result.mapped_record or not any(v is not None for k, v in result.mapped_record.fields.items() if k != "document_type"):
            result.warnings.append("No reliable land fields were found; the original text is available for review.")
        if not result.structured_data:
            result.structured_data = structured_data({}, [], document_type=doc_type, raw_text=full_text)

        logger.info(
            "extraction.pipeline_completed",
            time_ms=result.processing_time_ms,
            errors=len(result.errors),
        )

        return result
