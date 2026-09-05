"""Deployment regressions without external services or OCR models."""

from unittest.mock import Mock
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, settings


@pytest.mark.parametrize("raw,async_url,sync_url", [
    ("postgres://user:placeholder@db.example/db", "postgresql+asyncpg://user:placeholder@db.example/db", "postgresql://user:placeholder@db.example/db"),
    ("sqlite+aiosqlite:///test.db", "sqlite+aiosqlite:///test.db", "sqlite:///test.db"),
])
def test_api_and_worker_use_same_database(raw, async_url, sync_url):
    config = Settings(_env_file=None, DATABASE_URL_OVERRIDE=raw)
    assert config.DATABASE_URL == async_url
    assert config.SYNC_DATABASE_URL == sync_url


def production_config(tmp_path, **overrides):
    values = dict(
        APP_ENV="production", DEBUG=False, SECRET_KEY="s" * 40,
        JWT_SECRET_KEY="j" * 40, CORS_ORIGINS="https://frontend.example",
        DATABASE_URL_OVERRIDE=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        LOCAL_STORAGE_DIR=str(tmp_path / "uploads"),
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("overrides", [
    {"SECRET_KEY": "change-me"}, {"JWT_SECRET_KEY": "short"},
    {"CORS_ORIGINS": "*"}, {"CORS_ORIGINS": "https://frontend.example/path"},
    {"DEBUG": True}, {"DATABASE_URL_OVERRIDE": "sqlite:///relative.db"},
    {"LOCAL_STORAGE_DIR": "uploads"},
])
def test_reject_unsafe_production_config(tmp_path, overrides):
    with pytest.raises(ValueError):
        production_config(tmp_path, **overrides)


def test_accept_persistent_config(tmp_path):
    assert production_config(tmp_path).APP_ENV == "production"


@pytest.mark.asyncio
async def test_health_does_not_access_database(monkeypatch):
    from app.main import app
    from app.db.session import engine
    connect = Mock(side_effect=AssertionError("liveness touched database"))
    monkeypatch.setattr(type(engine), "connect", connect)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    connect.assert_not_called()


@pytest.mark.asyncio
async def test_cors_preflight():
    from app.main import app
    headers = {"Origin": settings.cors_origins_list[0], "Access-Control-Request-Method": "POST"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options("/api/v1/documents/upload", headers=headers)
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
        headers["Origin"] = "https://untrusted.example"
        assert (await client.options("/api/v1/documents/upload", headers=headers)).status_code == 400


def test_storage_blocks_sibling_path(tmp_path):
    from app.services.storage import LocalStorageService
    storage = LocalStorageService(str(tmp_path / "uploads"))
    with pytest.raises(ValueError):
        storage._resolve("../uploads-other/secret.pdf")


def test_worker_uses_sqlite_override(tmp_path, monkeypatch):
    from app.tasks import pipeline
    monkeypatch.setattr(settings, "DATABASE_URL_OVERRIDE", f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    monkeypatch.setattr(pipeline, "_sync_engine", None)
    engine = pipeline._get_sync_engine()
    try:
        assert Path(engine.url.database) == tmp_path / "worker.db"
    finally:
        engine.dispose()


def test_historic_processing_errors_are_redacted(monkeypatch):
    from app.schemas.document import ProcessingJobResponse
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert "/private" not in ProcessingJobResponse.safe_error_message("failed at /private/document.pdf")


@pytest.mark.asyncio
async def test_application_startup(tmp_path, monkeypatch):
    from app import main
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'startup.db'}")
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(settings, "DATABASE_URL_OVERRIDE", str(engine.url))
    try:
        async with main.lifespan(main.app):
            assert (tmp_path / "startup.db").is_file()
    finally:
        await engine.dispose()


def test_bootstrap_and_restart_preserve_data(tmp_path, monkeypatch):
    import sqlite3
    from app.deploy import prepare_storage
    monkeypatch.setattr(settings, "DATABASE_URL_OVERRIDE", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    prepare_storage()
    with sqlite3.connect(tmp_path / "test.db") as connection:
        connection.execute("CREATE TABLE deployment_marker (value TEXT)")
        connection.execute("INSERT INTO deployment_marker VALUES ('preserved')")
    prepare_storage()
    with sqlite3.connect(tmp_path / "test.db") as connection:
        assert connection.execute("SELECT value FROM deployment_marker").fetchone() == ("preserved",)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


# -- Free-tier synchronous processing ----------------------------------------

@pytest.mark.parametrize("mode,env,broker,expect_sync", [
    ("sync", "production", "", True),
    ("sync", "development", "redis://localhost:6379/1", True),
    ("celery", "production", "", False),
    ("auto", "production", "", True),
    ("auto", "production", "redis://key-value:6379/1", False),
    ("auto", "development", "", False),
])
def test_processing_mode_resolution(monkeypatch, tmp_path, mode, env, broker, expect_sync):
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL_OVERRIDE", raising=False)
    values = dict(PROCESSING_MODE=mode, CELERY_BROKER_URL_OVERRIDE=broker, APP_ENV=env)
    config = (production_config(tmp_path, **values) if env == "production"
              else Settings(_env_file=None, **values))
    assert config.use_sync_processing is expect_sync


def test_invalid_processing_mode_rejected():
    with pytest.raises(ValueError):
        Settings(_env_file=None, PROCESSING_MODE="queue")


def test_sync_deployment_starts_no_celery_worker(monkeypatch):
    from app import deploy
    monkeypatch.setattr(deploy, "prepare_storage", lambda: None)
    monkeypatch.setattr(settings, "PROCESSING_MODE", "sync")
    started = []

    class DummyProcess:
        def __init__(self, command):
            started.append(command)

        def poll(self):
            return 0

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(deploy.subprocess, "Popen", DummyProcess)
    deploy.main()
    assert len(started) == 1
    assert "celery" not in " ".join(started[0])
    assert "uvicorn" in " ".join(started[0])


def test_disabled_ocr_fallback_never_loads_easyocr(monkeypatch):
    from app.services.ocr.ocr_service import OCRService
    monkeypatch.setattr(settings, "OCR_FALLBACK_ENGINE", "")
    assert settings.ocr_fallback_engine == ""
    assert OCRService._fallback_name("tesseract") == ""
    monkeypatch.setattr(settings, "OCR_FALLBACK_ENGINE", "easyocr")
    assert OCRService._fallback_name("tesseract") == "easyocr"


def test_celery_publish_retries_are_bounded():
    from app.tasks import celery_app
    assert celery_app.conf.task_publish_retry_policy["max_retries"] <= 3
    assert celery_app.conf.broker_transport_options["socket_connect_timeout"] <= 5


def test_pipeline_task_delegates_to_shared_runner():
    from app.tasks import pipeline
    assert callable(pipeline.run_processing_job)
    assert pipeline.process_document_task.name == "process_document"


@pytest.mark.asyncio
async def test_sync_mode_runs_pipeline_inline_without_broker(tmp_path, monkeypatch):
    """The process endpoint completes the job itself and never touches Celery."""
    import uuid

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import Session as SyncSession
    from sqlalchemy import create_engine

    from app.main import app
    from app.db.base import Base
    from app.db.session import get_db
    from app.core.dependencies import get_current_user
    from app.models.document import Document
    from app.models.processing import ProcessingJob
    from app.models.user import User
    from app.tasks import pipeline as pipeline_module
    from app.api.v1.endpoints import documents as documents_module

    db_path = tmp_path / "sync.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    user = User(id=uuid.uuid4(), email="operator@example.gov", hashed_password="x", full_name="Operator")
    doc = Document(original_filename="record.pdf", safe_filename="a.pdf", mime_type="application/pdf",
                   file_size_bytes=10, storage_path="documents/a.pdf", status="uploaded", uploaded_by=user.id)
    async with factory() as session:
        session.add_all([user, doc])
        await session.commit()
        document_id = doc.id

    async def override_db():
        async with factory() as session:
            yield session
            await session.commit()

    def completed(job_id: str) -> dict:
        # Stand-in for the real pipeline: writes results the way the worker does.
        sync_engine = create_engine(f"sqlite:///{db_path}")
        try:
            with SyncSession(sync_engine) as db:
                job = db.get(ProcessingJob, uuid.UUID(job_id))
                job.status = "completed"
                db.get(Document, job.document_id).status = "processed"
                db.commit()
        finally:
            sync_engine.dispose()
        return {"status": "completed"}

    monkeypatch.setattr(pipeline_module, "run_processing_job", completed)
    monkeypatch.setattr(settings, "PROCESSING_MODE", "sync")
    monkeypatch.setattr(
        pipeline_module.process_document_task, "delay",
        Mock(side_effect=AssertionError("sync mode contacted the Celery broker")),
    )
    monkeypatch.setattr(documents_module, "get_storage_service", Mock())
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/documents/{document_id}/process")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
