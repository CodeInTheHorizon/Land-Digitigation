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
