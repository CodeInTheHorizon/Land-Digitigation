"""Root conftest.py – shared fixtures for all backend tests."""

from __future__ import annotations

import os

import pytest

# Ensure tests never accidentally connect to a real database.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test_landrecords")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DEBUG", "false")


@pytest.fixture
def app_settings():
    """Return a fresh Settings instance for tests."""
    from app.core.config import Settings
    return Settings()
