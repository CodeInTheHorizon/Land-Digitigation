"""Celery application and task registration."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "land_records",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.PROCESSING_TIMEOUT_SECONDS,
    worker_concurrency=settings.CELERY_CONCURRENCY,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
