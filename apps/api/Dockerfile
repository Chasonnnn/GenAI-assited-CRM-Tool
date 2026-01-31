# Production Dockerfile for Surrogacy Force API
# Multi-stage build for smaller final image

# ============================================================================
# Stage 1: Build dependencies
# ============================================================================
FROM ghcr.io/astral-sh/uv:0.9.24 AS uv

FROM python:3.11.14-slim-bookworm AS builder

WORKDIR /app
ARG CACHE_BUST=0
RUN echo "cache_bust=${CACHE_BUST}" > /dev/null

# Install uv
COPY --from=uv /uv /usr/local/bin/uv

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment via uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project


# ============================================================================
# Stage 2: Production image
# ============================================================================
FROM python:3.11.14-slim-bookworm

WORKDIR /app
ARG CACHE_BUST=0
RUN echo "cache_bust=${CACHE_BUST}" > /dev/null

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Install Playwright browser binaries (required for PDF export)
RUN python -m playwright install --with-deps chromium && \
    chmod -R 755 /opt/playwright

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENV=production

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
