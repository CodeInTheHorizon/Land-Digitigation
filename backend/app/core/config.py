"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import AliasChoices, Field, field_validator, model_validator
from sqlalchemy.engine import make_url
from urllib.parse import urlsplit
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings – values come from .env or the process environment."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    # -- App ------------------------------------------------------------------
    APP_NAME: str = "Land Record Digitization System"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-to-a-random-string-at-least-32-chars"
    API_V1_PREFIX: str = "/api/v1"

    # -- Database -------------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "landrecords"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "landrecords"
    DATABASE_URL_OVERRIDE: str = Field(
        default="", validation_alias=AliasChoices("DATABASE_URL_OVERRIDE", "DATABASE_URL")
    )

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            url = make_url(self.DATABASE_URL_OVERRIDE)
            if url.drivername in ("postgres", "postgresql"):
                url = url.set(drivername="postgresql+asyncpg")
            elif url.drivername == "sqlite":
                url = url.set(drivername="sqlite+aiosqlite")
            return url.render_as_string(hide_password=False)
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        url = make_url(self.DATABASE_URL)
        driver = url.drivername.replace("+asyncpg", "").replace("+aiosqlite", "")
        return url.set(drivername=driver).render_as_string(hide_password=False)

    # -- Redis ----------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    CELERY_BROKER_URL_OVERRIDE: str = ""
    CELERY_RESULT_BACKEND_OVERRIDE: str = ""

    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        if self.CELERY_BROKER_URL_OVERRIDE:
            return self.CELERY_BROKER_URL_OVERRIDE
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        if self.CELERY_RESULT_BACKEND_OVERRIDE:
            return self.CELERY_RESULT_BACKEND_OVERRIDE
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/2"

    # -- Processing mode ------------------------------------------------------
    # auto   : Celery when a broker is explicitly configured, otherwise sync
    #          in production (Render free tier has no Redis).
    # celery : always dispatch to Celery/Redis.
    # sync   : always process inside the web request (no Redis contact).
    PROCESSING_MODE: str = "auto"

    @field_validator("PROCESSING_MODE")
    @classmethod
    def _validate_processing_mode(cls, v: str) -> str:
        mode = v.strip().lower()
        if mode not in ("auto", "celery", "sync"):
            raise ValueError("PROCESSING_MODE must be one of: auto, celery, sync")
        return mode

    @property
    def celery_broker_configured(self) -> bool:
        """True only when a broker URL was supplied explicitly (not the localhost default)."""
        return bool(
            self.CELERY_BROKER_URL_OVERRIDE
            or os.getenv("CELERY_BROKER_URL")
            or os.getenv("CELERY_BROKER_URL_OVERRIDE")
        )

    @property
    def use_sync_processing(self) -> bool:
        """Whether document processing runs inside the web request."""
        if self.PROCESSING_MODE == "sync":
            return True
        if self.PROCESSING_MODE == "celery":
            return False
        # auto: keep Celery for development/compose; fall back to sync in
        # production deployments that have no broker configured.
        return self.APP_ENV == "production" and not self.celery_broker_configured

    # -- Object Storage -------------------------------------------------------
    STORAGE_BACKEND: str = "local"  # local | minio | s3
    LOCAL_STORAGE_DIR: str = "uploads"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "land-records"
    MINIO_USE_SSL: bool = False

    # -- JWT ------------------------------------------------------------------
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -- OCR ------------------------------------------------------------------
    OCR_PRIMARY_ENGINE: str = "tesseract"
    # Set to "" or "none" to disable the fallback engine entirely — required on
    # low-memory hosts, where loading EasyOCR/Torch would exhaust the instance.
    OCR_FALLBACK_ENGINE: str = "easyocr"

    @property
    def ocr_fallback_engine(self) -> str:
        name = self.OCR_FALLBACK_ENGINE.strip().lower()
        return "" if name in ("", "none", "disabled") else name

    OCR_LANGUAGES: str = "eng,hin"  # Tesseract language packs to load
    OCR_MIN_CONFIDENCE: float = 0.3  # Discard blocks below this confidence

    GOOGLE_VISION_CREDENTIALS_PATH: str = ""
    AZURE_COGNITIVE_ENDPOINT: str = ""
    AZURE_COGNITIVE_KEY: str = ""

    # -- Preprocessing --------------------------------------------------------
    PREPROCESS_TARGET_DPI: int = 300
    PREPROCESS_NOISE_THRESHOLD: float = 0.15  # skip denoising if noise < threshold
    PREPROCESS_DESKEW_MAX_ANGLE: float = 15.0  # max degrees to auto-correct

    # -- LLM ------------------------------------------------------------------
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    LOCAL_LLM_URL: str = "http://localhost:11434"
    LOCAL_LLM_MODEL: str = "llama3"

    # -- Upload ---------------------------------------------------------------
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "pdf,png,jpg,jpeg,tiff,tif,bmp,webp"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # -- Processing -----------------------------------------------------------
    CELERY_CONCURRENCY: int = 2
    PROCESSING_TIMEOUT_SECONDS: int = 300

    # -- CORS -----------------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def validate_production(self):
        if self.APP_ENV != "production":
            return self
        for name in ("SECRET_KEY", "JWT_SECRET_KEY"):
            value = getattr(self, name)
            if len(value) < 32 or value.startswith("change-me"):
                raise ValueError(f"Production requires a random {name} of at least 32 characters")
        if self.DEBUG:
            raise ValueError("DEBUG must be false in production")
        if not self.cors_origins_list:
            raise ValueError("Production requires explicit CORS_ORIGINS")
        for origin in self.cors_origins_list:
            parsed = urlsplit(origin)
            if ("*" in origin or not parsed.hostname or parsed.path or parsed.query
                    or parsed.fragment or parsed.username or parsed.password
                    or parsed.scheme not in ("https", "http")
                    or (parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"))):
                raise ValueError("CORS_ORIGINS must contain exact HTTPS origins (HTTP localhost allowed)")
        if not self.DATABASE_URL_OVERRIDE:
            raise ValueError("Production requires DATABASE_URL or DATABASE_URL_OVERRIDE")
        url = make_url(self.DATABASE_URL)
        if url.drivername.startswith("sqlite"):
            if not url.database or not Path(url.database).is_absolute():
                raise ValueError("Production SQLite requires an absolute persistent disk path")
        elif url.host in (None, "localhost", "127.0.0.1"):
            raise ValueError("Production database must use a deployed database host")
        if self.STORAGE_BACKEND not in ("local", "minio", "s3"):
            raise ValueError("Unsupported STORAGE_BACKEND")
        if self.STORAGE_BACKEND == "local" and not Path(self.LOCAL_STORAGE_DIR).is_absolute():
            raise ValueError("Production local storage requires an absolute persistent disk path")
        return self

    # -- Logging --------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if v == "change-me-to-a-random-string-at-least-32-chars":
            import warnings
            warnings.warn(
                "SECRET_KEY is set to the insecure default — set a random value "
                "before deploying to production.",
                stacklevel=2,
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if v == "change-me-jwt-secret":
            import warnings
            warnings.warn(
                "JWT_SECRET_KEY is set to the insecure default — set a random value "
                "before deploying to production.",
                stacklevel=2,
            )
        return v


settings = Settings()
