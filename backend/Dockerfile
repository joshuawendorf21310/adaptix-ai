# Development Guide for Docker
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend/pyproject.toml backend/setup.py* ./
COPY backend/core_app ./core_app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8014

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8014/health').raise_for_status()"

# Run application
CMD ["uvicorn", "core_app.main:app", "--host", "0.0.0.0", "--port", "8014"]
