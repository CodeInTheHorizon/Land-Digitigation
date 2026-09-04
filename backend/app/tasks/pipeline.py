"""Document processing pipeline – the main Celery task.

Fetches a document from storage, runs it through the DocumentPipeline,
and persists OCR results back to the database.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.tasks import celery_app

logger = get_logger(__name__)

# Module-level engine singleton — avoids creating a new connection pool per task.
_sync_engine = None


def _get_sync_engine():
    """Return a module-level SQLAlchemy sync engine (created once)."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.SYNC_DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _sync_engine


def _run_async(coro):
    """Run an async function from synchronous Celery context.

    Uses asyncio.run() which works reliably in Python 3.10+.
    """
    return asyncio.run(coro)


@celery_app.task(bind=True, name="process_document", max_retries=2)
def process_document_task(self, job_id: str) -> dict:
    """Full document processing pipeline.

    Stages:
      1. Fetch document from storage
      2. Extract pages (PDF → images)
      3. Preprocess images
      4. Detect language
      5. Layout analysis
      6. Run OCR per page
      7. Store OCR results
      8. Update processing status
    """
    from sqlalchemy.orm import Session

    from app.models.document import Document, DocumentPage
    from app.models.processing import OCRResult, ProcessingJob
    from app.models.land_record import ExtractionResult as ExtractionResultModel
    from app.services.pipeline import DocumentPipeline
    from app.services.extraction import ExtractionPipeline
    from app.services.storage import get_storage_service

    start = time.monotonic()

    engine = _get_sync_engine()
    with Session(engine) as db:
        job = db.get(ProcessingJob, job_id)
        if not job:
            logger.error("pipeline.job_not_found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}

        doc = db.get(Document, job.document_id)
        if not doc:
            logger.error("pipeline.document_not_found", job_id=job_id)
            job.status = "failed"
            job.error_message = "Document record not found"
            db.commit()
            return {"status": "error", "message": "Document not found"}

        try:
            # -- Mark job as running -------------------------------------------
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.current_stage = "fetching_document"
            db.commit()

            # -- Stage 1: Fetch document from storage --------------------------
            storage = get_storage_service()
            file_bytes = _run_async(storage.download(doc.storage_path))

            # -- Stage 2–7: Run pipeline ---------------------------------------
            job.current_stage = "processing"
            db.commit()

            pipeline = DocumentPipeline()
            result = _run_async(
                pipeline.process(
                    file_bytes,
                    mime_type=doc.mime_type,
                    filename=doc.original_filename,
                )
            )

            # -- Stage 8: Persist results --------------------------------------
            job.current_stage = "storing_results"
            db.commit()

            # Update document metadata
            doc.page_count = result.page_count
            doc.detected_language = result.primary_language

            # Create DocumentPage + OCRResult records
            pages_processed = 0
            for page_result in result.pages:
                ocr = page_result.ocr_result

                # Create or update DocumentPage
                doc_page = DocumentPage(
                    document_id=doc.id,
                    page_number=page_result.page_number,
                    image_storage_path=None,  # could store preprocessed images
                    width=page_result.image_width,
                    height=page_result.image_height,
                    dpi=page_result.image_dpi,
                    raw_text=ocr.full_text,
                    ocr_engine=ocr.engine,
                    ocr_confidence=ocr.avg_confidence,
                    detected_language=ocr.detected_language,
                )
                db.add(doc_page)
                db.flush()

                # Create OCRResult records for each block
                for block in ocr.blocks:
                    ocr_result = OCRResult(
                        page_id=doc_page.id,
                        job_id=job.id,
                        ocr_engine=ocr.engine,
                        detected_language=ocr.detected_language,
                        block_type=block.block_type,
                        raw_text=block.text,
                        confidence=block.confidence,
                        bbox_x=block.bbox.x,
                        bbox_y=block.bbox.y,
                        bbox_width=block.bbox.width,
                        bbox_height=block.bbox.height,
                        metadata_={
                            "word_count": block.word_count,
                            "language": block.language,
                        },
                    )
                    db.add(ocr_result)

                pages_processed += 1

            # -- Stage 9: Run extraction pipeline ---------------------------------
            job.current_stage = "extracting"
            db.commit()

            extraction_pipeline = ExtractionPipeline()
            page_texts = [
                p.ocr_result.full_text
                for p in result.pages
                if p.ocr_result.full_text
            ]
            extraction_result = extraction_pipeline.extract(
                full_text=result.full_text,
                page_texts=page_texts,
                page_count=result.page_count,
                ocr_confidence=result.avg_confidence,
            )

            # Persist extraction result
            ext_record = ExtractionResultModel(
                document_id=doc.id,
                job_id=job.id,
                document_category=(
                    extraction_result.classification.category.value
                    if extraction_result.classification
                    else None
                ),
                classification_confidence=(
                    extraction_result.classification.confidence
                    if extraction_result.classification
                    else None
                ),
                classification_scores=(
                    extraction_result.classification.scores
                    if extraction_result.classification
                    else None
                ),
                entity_count=(
                    extraction_result.extraction.entity_count
                    if extraction_result.extraction
                    else 0
                ),
                field_count=(
                    extraction_result.mapped_record.field_count
                    if extraction_result.mapped_record
                    else 0
                ),
                mapped_fields=(
                    extraction_result.mapped_record.fields
                    if extraction_result.mapped_record
                    else None
                ),
                persons=(
                    extraction_result.mapped_record.persons
                    if extraction_result.mapped_record
                    else None
                ),
                overall_confidence=(
                    extraction_result.confidence.overall
                    if extraction_result.confidence
                    else None
                ),
                field_confidences=(
                    extraction_result.confidence.to_dict().get("fields")
                    if extraction_result.confidence
                    else None
                ),
                validation_status=(
                    extraction_result.validation.status
                    if extraction_result.validation
                    else "pending"
                ),
                validation_issues=(
                    [
                        {
                            "rule_name": i.rule_name,
                            "rule_type": i.rule_type,
                            "field_name": i.field_name,
                            "status": i.status,
                            "message": i.message,
                            "severity": i.severity,
                        }
                        for i in extraction_result.validation.issues
                    ]
                    if extraction_result.validation
                    else None
                ),
                passed_count=(
                    extraction_result.validation.passed_count
                    if extraction_result.validation
                    else 0
                ),
                failed_count=(
                    extraction_result.validation.failed_count
                    if extraction_result.validation
                    else 0
                ),
                warning_count=(
                    extraction_result.validation.warning_count
                    if extraction_result.validation
                    else 0
                ),
                review_count=(
                    extraction_result.validation.review_count
                    if extraction_result.validation
                    else 0
                ),
                provenance=(
                    [
                        {
                            "field_name": p.field_name,
                            "raw_value": p.raw_value,
                            "normalized_value": str(p.normalized_value) if p.normalized_value is not None else None,
                            "confidence": p.confidence,
                            "source_entity_type": p.source_entity_type,
                            "extraction_method": p.extraction_method,
                            "page_number": p.page_number,
                        }
                        for p in extraction_result.mapped_record.provenance
                    ]
                    if extraction_result.mapped_record
                    else None
                ),
                processing_time_ms=extraction_result.processing_time_ms,
            )
            db.add(ext_record)

            # Update document type from classification
            if extraction_result.classification:
                doc.document_type = extraction_result.classification.category.value

            entities_extracted = (
                extraction_result.extraction.entity_count
                if extraction_result.extraction
                else 0
            )

            # -- Finalize job --------------------------------------------------
            elapsed_ms = int((time.monotonic() - start) * 1000)

            job.current_stage = "completed"
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.processing_time_ms = elapsed_ms
            job.pages_processed = pages_processed
            job.entities_extracted = entities_extracted
            job.stage_metadata = {
                "primary_language": result.primary_language,
                "avg_confidence": result.avg_confidence,
                "errors": result.errors + extraction_result.errors,
                "extraction": {
                    "category": (
                        extraction_result.classification.category.value
                        if extraction_result.classification
                        else None
                    ),
                    "entities": entities_extracted,
                    "fields": (
                        extraction_result.mapped_record.field_count
                        if extraction_result.mapped_record
                        else 0
                    ),
                    "validation_status": (
                        extraction_result.validation.status
                        if extraction_result.validation
                        else "pending"
                    ),
                },
            }

            doc.status = "processed"

            db.commit()

            logger.info(
                "pipeline.completed",
                job_id=job_id,
                document_id=str(doc.id),
                pages=pages_processed,
                time_ms=elapsed_ms,
                language=result.primary_language,
                confidence=result.avg_confidence,
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "pages_processed": pages_processed,
                "primary_language": result.primary_language,
                "avg_confidence": result.avg_confidence,
                "processing_time_ms": elapsed_ms,
            }

        except Exception as exc:
            db.rollback()
            job.status = "failed"
            job.error_message = str(exc)[:2000]
            job.completed_at = datetime.now(timezone.utc)
            doc.status = "failed"
            db.commit()

            logger.error(
                "pipeline.failed",
                job_id=job_id,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=60)
