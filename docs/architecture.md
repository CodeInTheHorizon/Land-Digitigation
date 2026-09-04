# Architecture – Land Record Digitization System

## Overview

The system digitises Indian land records using OCR, CV, NLP and LLM technologies,
extracting 22+ structured fields from scanned PDFs, images, handwritten documents
and maps in 10 Indian languages.

## High-Level Architecture

```
┌────────────────────────────────────────────────────────┐
│               React Frontend (Vite + TS)               │
│         Tailwind CSS · React Router · Zustand          │
└───────────────────────┬────────────────────────────────┘
                        │ REST API (/api/v1)
┌───────────────────────▼────────────────────────────────┐
│                 FastAPI Backend                          │
│   Auth │ Documents │ Land Records │ Dashboard │ Health  │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │          Processing Pipeline (Celery)            │   │
│   │  Upload → Preprocess → OCR → NLP → Validate     │   │
│   └─────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────┐   │
│   │            AI Service Layer                      │   │
│   │  OCR │ CV │ NLP │ LLM │ Validation │ Confidence │   │
│   └─────────────────────────────────────────────────┘   │
└──┬──────────┬──────────┬──────────┬─────────────────────┘
   │          │          │          │
┌──▼──┐  ┌───▼──┐  ┌────▼──┐  ┌───▼────┐
│ PG  │  │Redis │  │MinIO  │  │Celery  │
│+vec │  │Cache │  │/S3    │  │Workers │
└─────┘  └──────┘  └───────┘  └────────┘
```

## Technology Stack

| Layer         | Technology                              |
|---------------|------------------------------------------|
| Frontend      | React 18, Vite 6, TypeScript 5.7, Tailwind 3 |
| Backend       | Python 3.11, FastAPI 0.115, Pydantic v2  |
| Database      | PostgreSQL 16 + pgvector                 |
| ORM           | SQLAlchemy 2.0 (async, asyncpg)          |
| Migrations    | Alembic 1.14                             |
| Auth          | JWT (python-jose, passlib+bcrypt)         |
| Task Queue    | Celery 5.4 + Redis                       |
| Object Store  | MinIO / S3                               |
| Logging       | structlog (JSON or console)              |
| Container     | Docker Compose                           |

## Database Schema

16 tables across 6 model files:

- **users / roles / user_roles** – RBAC authentication
- **documents / document_pages** – uploaded file tracking
- **processing_jobs / ocr_results** – async processing state
- **extracted_entities / land_records** – extracted field storage
- **landowners / land_parcels / ownership_records** – ownership graph
- **mutation_records / registration_records** – transaction history
- **validation_results / review_tasks** – QA workflow
- **audit_logs** – immutable action log

All tables use UUID primary keys, created_at/updated_at timestamps,
and appropriate foreign key constraints with indexes.

## Phased Implementation

| Phase | Scope                                      |
|-------|--------------------------------------------|
| 1     | Foundation: config, auth, DB, health, frontend shell |
| 2     | Document upload, storage, OCR pipeline     |
| 3     | NLP extraction, LLM integration, validation |
| 4     | Human review, confidence scoring, search   |
| 5     | Reports, analytics, production hardening   |

## Environment Configuration

All settings are loaded from environment variables via Pydantic Settings.
See `.env.example` for the complete variable list.
No credentials are hardcoded anywhere in the codebase.
