"""Celery application and task registration."""

from __future__ import annotations

import os

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "land_records",
    broker=(
        os.getenv("CELERY_BROKER_URL")
        or os.getenv("CELERY_BROKER_URL_OVERRIDE")
        or settings.CELERY_BROKER_URL
    ),
    backend=(
        os.getenv("CELERY_RESULT_BACKEND")
        or os.getenv("CELERY_RESULT_BACKEND_OVERRIDE")
        or settings.CELERY_RESULT_BACKEND
    ),
    include=["app.tasks.pipeline"],
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
    broker_connection_retry_on_startup=True,
    # Bound broker connection attempts so an unreachable Redis fails fast
    # instead of retrying until the HTTP request times out.
    broker_connection_max_retries=3,
    broker_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_policy": {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1},
    },
    result_backend_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_policy": {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1},
    },
    task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1},
)
