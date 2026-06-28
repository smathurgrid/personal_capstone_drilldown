# Multi-stage build for DrillDown Unified Application
FROM node:20-slim AS frontend-builder

# Install frontend dependencies
WORKDIR /app
COPY package.json package-lock.json* ./
COPY packages ./packages
RUN npm install

# Copy frontend source
COPY frontend ./frontend
COPY vite.config.ts tsconfig.json tailwind.config.ts ./

# Build frontend
RUN npm run build

# Backend stage
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend ./backend
COPY scripts ./scripts
COPY data ./data

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/dist ./frontend/dist

# Copy environment example (user will mount actual .env)
COPY .env.example ./

# Create necessary directories
RUN mkdir -p \
    ./data/qdrant_storage \
    ./data/ecommerce/uploads \
    ./data/ecommerce/debug \
    ./data/explainer/static \
    ./data/kb \
    ./data/kb/qdrant \
    ./data/fashion-dataset/images

# Expose ports
EXPOSE 8001

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

# Run the application
CMD ["python3", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
