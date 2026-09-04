"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine
from app.models.user import Role, User, UserRole


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, Role.__table__, UserRole.__table__],
                )
            )
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount v1 API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {"service": settings.APP_NAME, "version": "0.1.0", "docs": "/docs"}
