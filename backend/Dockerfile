# Multi-stage build for Python backend
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH
# Ensure project root is on Python path for app and worker imports
ENV PYTHONPATH=/app

# Copy application code
COPY . .

# Create temp directory for file uploads
RUN mkdir -p /tmp/uploads

# Expose port
EXPOSE 8000

# Default command (can be overridden for workers)
# Note: Railway handles health checks via railway.backend.toml
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

