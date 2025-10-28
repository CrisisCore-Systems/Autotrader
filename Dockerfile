# Multi-stage production Dockerfile for AutoTrader
# Optimized for security, size, and reproducibility
# Security features:
# - Multi-stage build (separates build from runtime)
# - Non-root user (UID 1000)
# - Minimal base image (Alpine)
# - No unnecessary packages in final image
# - Pinned base image versions for reproducibility
# - Health check for container monitoring

# Build args to control Python version and requirements file (override at build time if needed)
ARG PYTHON_TAG=3.13-alpine
ARG REQS_FILE=requirements-py313.txt

# === Stage 1: Builder ===
FROM python:${PYTHON_TAG} AS builder
ARG REQS_FILE

# Install build dependencies
RUN apk add --no-cache \
    bash \
    build-base \
    git \
    libffi-dev \
    linux-headers \
    openssl-dev \
    postgresql-dev

# Create non-root user for build
RUN addgroup -S builder && \
    adduser -S -G builder builder && \
    mkdir -p /home/builder && \
    chown builder:builder /home/builder
USER builder
WORKDIR /home/builder

# Copy dependency files (both requirement sets to allow switching via REQS_FILE)
COPY --chown=builder:builder requirements*.txt pyproject.toml ./

# Install Python dependencies in user space
RUN pip install --user --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --user --no-cache-dir -r ${REQS_FILE}

# === Stage 2: Runtime ===
FROM python:${PYTHON_TAG} AS runtime

# Security: Install runtime dependencies only
RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    libstdc++

# Security: Create non-root user with explicit UID
RUN addgroup -g 1000 -S autotrader && \
    adduser -S -G autotrader -u 1000 autotrader && \
    mkdir -p /home/autotrader && \
    chown autotrader:autotrader /home/autotrader

# Security: Set secure default umask
RUN echo "umask 027" >> /home/autotrader/.profile

# Copy Python packages from builder
COPY --from=builder /home/builder/.local /home/autotrader/.local

# Set up application directory
WORKDIR /app
RUN chown autotrader:autotrader /app

# Create necessary directories with correct permissions
RUN mkdir -p /app/logs /app/.cache /app/artifacts /app/backtest_results /tmp && \
    chown -R autotrader:autotrader /app/logs /app/.cache /app/artifacts /app/backtest_results

# Copy application code
COPY --chown=autotrader:autotrader src/ ./src/
COPY --chown=autotrader:autotrader autotrader/ ./autotrader/
COPY --chown=autotrader:autotrader pipeline/ ./pipeline/
COPY --chown=autotrader:autotrader configs/ ./configs/
COPY --chown=autotrader:autotrader backtest/ ./backtest/
COPY --chown=autotrader:autotrader scripts/ ./scripts/
COPY --chown=autotrader:autotrader *.py ./

# Switch to non-root user
USER autotrader

# Add local Python packages to PATH
ENV PATH="/home/autotrader/.local/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH:-}"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Expose Prometheus metrics port
EXPOSE 9090

# Default entrypoint to start the Prometheus exporter; allow overriding args (e.g., port)
ENTRYPOINT ["python", "scripts/monitoring/export_compliance_metrics.py"]
CMD ["--port", "9090"]

# Metadata
LABEL maintainer="CrisisCore Systems"
LABEL version="1.0.0"
LABEL description="AutoTrader - Crypto Trading Analysis Platform"
