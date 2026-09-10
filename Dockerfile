FROM python:3.11-slim

# Install system dependencies including Tesseract OCR and OpenCV requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set python path
ENV PYTHONPATH=/app/backend

# Copy requirements and install
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend source code
COPY backend ./backend
COPY frontend ./frontend

# Create upload directory
RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
