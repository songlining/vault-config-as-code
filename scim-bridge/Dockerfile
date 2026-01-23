# SCIM Bridge Dockerfile for containerizing the FastAPI application
# Base on Python 3.11 slim image for smaller footprint and security

FROM python:3.11-slim

# Install system dependencies including git (required for Git operations)
RUN apt-get update && \
    apt-get install -y \
        git \
        curl \
        --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create data directory for persistent storage (user mappings, repo clone)
RUN mkdir -p /data

# Copy requirements file first for better Docker layer caching
# If requirements.txt changes, only this layer and below will rebuild
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code to /app
COPY app/ ./app/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app /data
USER appuser

# Expose port 8000 (FastAPI default port)
EXPOSE 8000

# Set environment variables with defaults
ENV REPO_CLONE_DIR=/data/repo \
    USER_MAPPING_FILE=/data/user_mapping.json \
    LOG_LEVEL=INFO

# Health check to verify service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with uvicorn
# 0.0.0.0 binds to all interfaces inside container
# --reload disabled in production for performance and security
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]