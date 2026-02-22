# =============================================================================
# JudgeLoom — Production Dockerfile
# =============================================================================
# Multi-stage build:
#   builder  — installs Python dependencies into a clean venv
#   runtime  — minimal image with only what's needed to run
# =============================================================================

# ─── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Build-time system deps (compilers, headers for C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtualenv so we can copy it cleanly to the runtime stage
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Upgrade pip/wheel before installing project deps
RUN pip install --no-cache-dir --upgrade pip wheel

# Copy requirements first — layer-cache friendly
COPY requirements/base.txt requirements/base.txt
COPY requirements/production.txt requirements/production.txt

# Install production requirements only
RUN pip install --no-cache-dir -r requirements/production.txt


# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="JudgeLoom Core" \
      org.opencontainers.image.description="JudgeLoom Django application (production)" \
      org.opencontainers.image.source="https://github.com/judgeloom/judgeloom-core"

# Runtime system deps (shared libs only — no headers/compilers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    zlib1g \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pull the pre-built venv from the builder stage
ENV VIRTUAL_ENV=/opt/venv
COPY --from=builder "$VIRTUAL_ENV" "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Non-root user for security
RUN groupadd --gid 1000 judgeloom \
    && useradd --uid 1000 --gid judgeloom --no-create-home judgeloom

WORKDIR /app

# Copy application source
COPY --chown=judgeloom:judgeloom . /app/

# Create writable directories for runtime artifacts
RUN mkdir -p /var/judgeloom/static /var/judgeloom/media \
    && chown -R judgeloom:judgeloom /var/judgeloom

# Switch to non-root before running the app
USER judgeloom

# Collect static assets at build time
ENV DJANGO_SETTINGS_MODULE=config.settings.production
RUN python manage.py collectstatic --noinput --clear

EXPOSE 8000

# Readiness probe — hits the API root to verify Django is serving
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/')"]

# Gunicorn serves via WSGI for low-latency HTTP; switch to daphne/uvicorn
# for full async/WebSocket support if needed.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--timeout", "60", \
     "--keep-alive", "5", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
