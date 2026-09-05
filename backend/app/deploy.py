"""Run API and Celery together so they can share Render's SQLite/upload disk."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.base import Base
from app import models  # noqa: F401


def prepare_storage():
    if settings.STORAGE_BACKEND == "local":
        Path(settings.LOCAL_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    url = make_url(settings.SYNC_DATABASE_URL)
    if url.drivername == "sqlite":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    # There are no Alembic revisions yet. Bootstrap missing tables only; this
    # never drops tables or migrates existing data/columns.
    engine = create_engine(settings.SYNC_DATABASE_URL)
    try:
        if url.drivername == "sqlite":
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def main():
    prepare_storage()
    processes = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    commands = []
    if not settings.use_sync_processing:
        # Celery worker only when a Redis broker is configured; in sync mode the
        # API runs the pipeline itself and no broker is contacted.
        commands.append(
            [sys.executable, "-m", "celery", "-A", "app.tasks", "worker",
             "--loglevel=info", "--concurrency=1", "--prefetch-multiplier=1"]
        )
    commands.append(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
         "--port", os.environ.get("PORT", "8000"), "--workers", "1",
         "--timeout-keep-alive", "75"]
    )
    try:
        for command in commands:
            processes.append(subprocess.Popen(command))
        while not stopping:
            if any(process.poll() is not None for process in processes):
                return 1  # Restart the entire service if either child exits.
            time.sleep(0.5)
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 25
        for process in processes:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
