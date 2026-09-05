FROM python:3.11-slim-bookworm

# Install system dependencies for OCR and CV (Phase 2+)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-mar \
    tesseract-ocr-ben \
    tesseract-ocr-guj \
    tesseract-ocr-pan \
    tesseract-ocr-tam \
    tesseract-ocr-tel \
    tesseract-ocr-kan \
    tesseract-ocr-mal \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENV EASYOCR_MODULE_PATH=/opt/easyocr

COPY backend/requirements.txt .
# CPU wheels avoid pulling CUDA libraries into the Render image.
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
# Fail the build if English/Hindi fallback weights cannot be provisioned.
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False); easyocr.Reader(['en', 'hi'], gpu=False, verbose=False)"

COPY backend/ .

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
