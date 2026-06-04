# =========================
# Backend (FastAPI) image
# Build context = repo root
# =========================

# -------- 1. Builder stage --------
FROM python:3.12-slim AS builder

WORKDIR /app

# Build deps for packages that need to compile (psycopg, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Isolated virtualenv we can copy into the runtime image
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements/base.txt .
RUN pip install --no-cache-dir -r base.txt


# -------- 2. Runtime stage --------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Only runtime deps (OCR/PDF processing)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Backend lives in backend/ : main.py imports `src.*`, so src must be top-level.
COPY backend/main.py /app/main.py
COPY backend/src /app/src
COPY deployment/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

# Cloud Run injects $PORT (defaults to 8080)
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
