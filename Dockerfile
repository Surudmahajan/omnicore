# OmniCore Backend — Dockerfile
# Optimised for HuggingFace Docker Spaces with persistent storage.

FROM python:3.11-slim

# Metadata
LABEL maintainer="OmniCore"
LABEL description="OmniCore Developer Data Infrastructure Platform — Backend API"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .

# Create data directories
# On HuggingFace Spaces with persistent storage, /data is mounted automatically.
RUN mkdir -p /data/datasets

# Environment variable defaults (override via HuggingFace Secrets)
ENV ENVIRONMENT=production
ENV DATABASE_PATH=/data/omnicore.db
ENV DATASET_STORAGE_PATH=/data/datasets
ENV PORT=7860

# HuggingFace Spaces run as user 1000
RUN useradd -m -u 1000 omnicore && chown -R omnicore:omnicore /app /data
USER omnicore

# Expose the port HuggingFace Spaces expects
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7860/health').raise_for_status()"

# Start the server
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "7860", \
     "--workers", "1", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
