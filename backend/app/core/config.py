"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings – values come from .env or the process environment."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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
    DATABASE_URL_OVERRIDE: str = ""

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # -- Redis ----------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/2"

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
    OCR_FALLBACK_ENGINE: str = "easyocr"
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
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

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
