# Multi-stage production Dockerfile for AutoTrader
# Optimized for security, size, and reproducibility

# === Stage 1: Builder ===
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for build
RUN useradd --create-home --shell /bin/bash builder
USER builder
WORKDIR /home/builder

# Copy dependency files
COPY --chown=builder:builder requirements.txt pyproject.toml ./

# Install Python dependencies in user space
RUN pip install --user --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --user --no-cache-dir -r requirements.txt

# === Stage 2: Runtime ===
FROM python:3.11-slim-bookworm AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 autotrader

# Copy Python packages from builder
COPY --from=builder /home/builder/.local /home/autotrader/.local

# Set up application directory
WORKDIR /app
RUN chown autotrader:autotrader /app

# Create necessary directories with correct permissions
RUN mkdir -p /app/logs /app/.cache /tmp && \
    chown -R autotrader:autotrader /app/logs /app/.cache

# Copy application code
COPY --chown=autotrader:autotrader src/ ./src/
COPY --chown=autotrader:autotrader pipeline/ ./pipeline/
COPY --chown=autotrader:autotrader configs/ ./configs/
COPY --chown=autotrader:autotrader *.py ./

# Switch to non-root user
USER autotrader

# Add local Python packages to PATH
ENV PATH="/home/autotrader/.local/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command (can be overridden)
CMD ["python", "-m", "src.services.exporter"]

# Metadata
LABEL maintainer="CrisisCore Systems"
LABEL version="1.0.0"
LABEL description="AutoTrader - Crypto Trading Analysis Platform"
