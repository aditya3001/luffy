# Local Development Dockerfile
# This includes all source files for development with hot-reload
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
# RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL project files for local development
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    ENV=development

# Expose API port
EXPOSE 8000

# Default command (can be overridden)
# CMD ["python", "scripts/start_api.py"]
CMD ["uvicorn", "src.services.api:app", "--host", "0.0.0.0", "--port", "8000"]
