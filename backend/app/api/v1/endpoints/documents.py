"""Document upload, listing, retrieval, and processing endpoints."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.document import Document, DocumentPage
from app.models.processing import ProcessingJob
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.document import (
    DocumentListResponse,
    DocumentPageResponse,
    DocumentResponse,
    ProcessingJobResponse,
)
from app.services.storage import get_storage_service

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = get_logger(__name__)


def _validate_file(file: UploadFile) -> None:
    """Validate file extension and size."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{ext}' not allowed. Accepted: {settings.ALLOWED_EXTENSIONS}",
        )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document for processing."""
    _validate_file(file)

    # Read file content
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    # Generate safe filename
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    safe_name = f"{uuid.uuid4().hex}.{file_ext}"
    storage_path = f"documents/{current_user.id}/{safe_name}"

    # Store file
    storage = get_storage_service()
    await storage.upload(storage_path, content, file.content_type or "application/octet-stream")

    # Create DB record
    doc = Document(
        original_filename=file.filename,
        safe_filename=safe_name,
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(content),
        storage_path=storage_path,
        status="uploaded",
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    db.add(AuditLog(user_id=current_user.id, action="document.upload", resource_type="document", resource_id=str(doc.id), description=file.filename))

    logger.info("document.uploaded", document_id=str(doc.id), filename=file.filename)
    return doc


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    document_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents uploaded by the current user."""
    query = select(Document).where(Document.uploaded_by == current_user.id)

    if status_filter:
        query = query.where(Document.status == status_filter)
    if document_type:
        query = query.where(Document.document_type == document_type)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    query = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    docs = result.scalars().all()

    return DocumentListResponse(items=docs, total=total, page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.uploaded_by == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/{document_id}/process", response_model=ProcessingJobResponse)
async def process_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger AI processing pipeline for a document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.uploaded_by == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="Document is already being processed")

    # Create processing job
    job = ProcessingJob(
        document_id=doc.id,
        job_type="full_pipeline",
        status="queued",
    )
    db.add(job)
    doc.status = "processing"
    await db.flush()
    await db.refresh(job)
    # Commit before dispatch so a fast worker can read the job immediately.
    await db.commit()

    # Dispatch Celery task
    from app.tasks.pipeline import process_document_task
    try:
        task = process_document_task.delay(str(job.id))
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:2000]
        doc.status = "uploaded"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Processing service is unavailable. Please try again.",
        ) from exc

    job.celery_task_id = task.id
    db.add(AuditLog(user_id=current_user.id, action="document.process", resource_type="document", resource_id=str(doc.id)))
    await db.commit()
    await db.refresh(job)

    logger.info("document.processing_started", document_id=str(doc.id), job_id=str(job.id))
    return job


@router.get("/{document_id}/pages", response_model=list[DocumentPageResponse])
async def get_document_pages(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all pages of a document with OCR text."""
    # Verify ownership
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.uploaded_by == current_user.id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    return result.scalars().all()


@router.get("/{document_id}/jobs", response_model=list[ProcessingJobResponse])
async def get_processing_jobs(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List processing jobs for a document."""
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.uploaded_by == current_user.id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its associated data."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.uploaded_by == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from storage
    storage = get_storage_service()
    try:
        await storage.delete(doc.storage_path)
    except Exception:
        logger.warning("storage.delete_failed", path=doc.storage_path)

    await db.delete(doc)
    db.add(AuditLog(user_id=current_user.id, action="document.delete", resource_type="document", resource_id=str(document_id)))
    logger.info("document.deleted", document_id=str(doc.id))
