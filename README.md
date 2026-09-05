# 🏛️ Intelligent Land Record Digitization & Validation System

An AI-powered platform for automatically extracting, classifying, validating, and managing structured information from Indian land records — scanned PDFs, handwritten documents, maps, and legacy files.

## 🎯 Overview

This system leverages **OCR**, **Computer Vision**, **NLP**, and **LLM** technologies to digitize land records across multiple Indian languages, extracting structured fields like landowner details, survey numbers, khasra/khata numbers, plot areas, ownership records, mutations, and registrations.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                        │
│         (Vite + TypeScript + Tailwind + shadcn/ui)       │
└─────────────────────┬───────────────────────────────────┘
                      │ REST API
┌─────────────────────▼───────────────────────────────────┐
│                  FastAPI Backend                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ Auth API │ │ Doc API  │ │ Record   │ │ Search API │ │
│  │          │ │          │ │ API      │ │            │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Processing Pipeline                     │   │
│  │  Upload → Preprocess → OCR → NLP → Validate      │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │         AI Service Layer                          │   │
│  │  OCR │ CV │ NLP │ LLM │ Validation │ Confidence  │   │
│  └──────────────────────────────────────────────────┘   │
└──┬──────────┬──────────┬──────────┬─────────────────────┘
   │          │          │          │
┌──▼──┐  ┌───▼──┐  ┌────▼──┐  ┌───▼────┐
│ PG  │  │Redis │  │MinIO  │  │Celery  │
│+vec │  │Cache │  │/S3    │  │Workers │
└─────┘  └──────┘  └───────┘  └────────┘
```

## 📋 Key Features

- **Multi-format ingestion**: Scanned PDFs, images, handwritten docs, photographs, maps
- **Multilingual OCR**: Hindi, English, Marathi, Bengali, Gujarati, Tamil, Telugu, Kannada, Malayalam, Punjabi
- **Intelligent extraction**: 22+ structured fields from land records
- **Confidence scoring**: Per-field confidence with source tracking
- **Validation engine**: Deterministic rules + LLM-based reasoning
- **Human review**: Queue-based review for low-confidence extractions
- **Vector search**: Semantic search across all records via pgvector
- **Audit trail**: Complete processing history and change tracking

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)

### Run with Docker Compose
```bash
# Clone and start
cp .env.example .env
docker compose up -d

# Initialize/update the PostgreSQL schema
docker compose run --rm backend alembic upgrade head

# Access
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# MinIO Console: http://localhost:9001
```

### Development Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 📁 Project Structure

```
Land-Digitigation/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # REST API endpoints
│   │   ├── core/               # Config, security, dependencies
│   │   ├── db/                 # Database session, base
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # Business logic & AI services
│   │   │   ├── ocr/            # OCR abstraction layer
│   │   │   ├── cv/             # Computer Vision processing
│   │   │   ├── nlp/            # NLP entity extraction
│   │   │   ├── llm/            # LLM abstraction layer
│   │   │   └── validation/     # Validation engine
│   │   ├── tasks/              # Celery async tasks
│   │   └── utils/              # Shared utilities
│   ├── alembic/                # Database migrations
│   ├── tests/                  # Pytest test suites
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Route pages
│   │   ├── hooks/              # Custom React hooks
│   │   ├── lib/                # Utilities
│   │   ├── services/           # API client layer
│   │   └── types/              # TypeScript types
│   └── package.json
├── infrastructure/
│   ├── docker/                 # Dockerfiles
│   └── nginx/                  # Reverse proxy config
├── docs/                       # Architecture documentation
├── docker-compose.yml
└── .env.example
```

## 🧪 Testing

```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm test

# E2E tests
npx playwright test
```

## 📄 License

This project is developed as an academic/innovation project for land record modernization in India.
