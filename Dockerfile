# ============================================================
# Stage 1: Builder
# Install deps in an isolated layer so the final image
# doesn't carry pip cache or build tools.
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /install

# Install build deps for any C-extension packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install/packages --no-cache-dir -r requirements.txt


# ============================================================
# Stage 2: Runtime
# Minimal image — only what's needed to run the server.
# ============================================================
FROM python:3.11-slim AS runtime

# Run as non-root for security
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install/packages /usr/local

# Copy application source
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose the port uvicorn listens on
EXPOSE 8000

# ── Health check so Docker / orchestrators know when the app is ready ──────
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# ── Start command ──────────────────────────────────────────────────────────
# workers=1 for in-memory session store (single process keeps SESSION_STORE shared).
# Increase workers only if you swap state.py for Redis.
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
