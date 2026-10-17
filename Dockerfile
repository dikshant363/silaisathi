# SilaiSathi — Production Container for DigitalOcean App Platform
# Offline-First AI Assistant Workstation (Fictional Demo & Gemma 4 Cloud Mode)

FROM python:3.12-slim AS runtime

# Optimization and security environment settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    SILAISATHI_CLOUD_DEPLOYMENT=1 \
    SILAISATHI_DEMO_MODE=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# Install curl for container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user for security compliance
RUN useradd -m -u 1000 appuser && \
    mkdir -p /home/appuser/.silaisathi/backups && \
    chown -R appuser:appuser /home/appuser

# Copy package definition and project code required for building
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md /app/
COPY silaisathi /app/silaisathi
COPY samples /app/samples
COPY .streamlit /app/.streamlit
COPY scripts /app/scripts
COPY app.py /app/

# Install application dependencies via pip
RUN pip install --no-cache-dir .

# Set permissions for non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# DigitalOcean App Platform HTTP port (default 8080)
EXPOSE 8080

# Health check using Streamlit's official endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8080}/_stcore/health || exit 1

# Launch Streamlit bound to 0.0.0.0 on the port assigned by App Platform ($PORT)
CMD ["sh", "-c", "exec streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true"]
