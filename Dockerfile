FROM python:3.11-slim

WORKDIR /app

# Runtime dependencies for QR decoding and OCR.
RUN apt-get update && apt-get install -y \
    libzbar0 \
    libzbar-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application.
COPY . .

# Runtime directories (ignored by Git).
RUN mkdir -p logs backups data

CMD ["python", "main.py"]
