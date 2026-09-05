"""Tests for the configuration system."""

import os


class TestSettings:
    def test_database_url_constructed(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        assert "postgresql+asyncpg://" in s.DATABASE_URL
        assert s.POSTGRES_DB in s.DATABASE_URL

    def test_sync_database_url(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        assert s.SYNC_DATABASE_URL.startswith("postgresql://")
        assert "asyncpg" not in s.SYNC_DATABASE_URL

    def test_redis_url(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        assert s.REDIS_URL.startswith("redis://")

    def test_celery_urls_use_different_dbs(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        assert s.CELERY_BROKER_URL.endswith("/1")
        assert s.CELERY_RESULT_BACKEND.endswith("/2")

    def test_cors_origins_list(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        origins = s.cors_origins_list
        assert isinstance(origins, list)
        assert len(origins) >= 1

    def test_allowed_extensions_list(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        exts = s.allowed_extensions_list
        assert "pdf" in exts
        assert "png" in exts

    def test_max_upload_bytes(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        assert s.max_upload_bytes == s.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("APP_NAME", "Test App Override")
        from app.core.config import Settings
        s = Settings(_env_file=None, DATABASE_URL_OVERRIDE="")
        assert s.APP_NAME == "Test App Override"
