FROM python:3.11-slim

# Install system dependencies for OCR and CV (Phase 2+)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-mar \
    tesseract-ocr-ben \
    tesseract-ocr-guj \
    tesseract-ocr-pan \
    tesseract-ocr-tam \
    tesseract-ocr-tel \
    tesseract-ocr-kan \
    tesseract-ocr-mal \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
