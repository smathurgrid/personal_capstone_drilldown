# Docker Deployment Guide

This guide explains how to run the DrillDown Unified application using Docker and Docker Compose.

## Prerequisites

1. **Docker** (version 20.10 or higher)
2. **Docker Compose** (version 2.0 or higher)
3. **NVIDIA Docker** (optional, for GPU support with Ollama)

## Quick Start

### 1. Prepare Environment

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` and set the required variables:
- `GOOGLE_API_KEY` - for ecommerce mode (optional)
- `AUTH_SECRET_KEY` - replace with a secure random string
- Other settings as needed

### 2. Start Services

Start all services (Redis, PostgreSQL, Qdrant, Ollama, and the main app):

```bash
docker-compose up -d
```

This will:
- Pull all required Docker images
- Build the application container
- Start all services in the background

### 3. Pull Ollama Models

After Ollama is running, pull the required models:

```bash
# Enter the Ollama container
docker exec -it drilldown-ollama bash

# Inside the container, pull models
ollama pull qwen3.5:9b
ollama pull qwen2.5vl:7b
ollama pull x/flux2-klein:4b

# Exit the container
exit
```

### 4. Access the Application

- **API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/api/health

### 5. Optional: Ingest Ecommerce Dataset

If using ecommerce mode, ingest the fashion dataset:

```bash
# Copy dataset to data directory first
# Then run:
docker exec -it drilldown-app python3 scripts/ingest_fashion_dataset.py --limit 1000
```

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| App | 8001 | Main FastAPI application |
| Redis | 6379 | Cache and session storage |
| PostgreSQL | 5432 | Database (auth, history) |
| Qdrant | 6333 | Vector database for ecommerce |
| Ollama | 11434 | LLM and vision models |

## Docker Compose Commands

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f ollama
```

### Stop services
```bash
docker-compose stop
```

### Start services
```bash
docker-compose start
```

### Restart services
```bash
docker-compose restart
```

### Stop and remove containers
```bash
docker-compose down
```

### Stop and remove containers + volumes (WARNING: deletes data)
```bash
docker-compose down -v
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

## Configuration Options

### Using SQLite Instead of PostgreSQL

If you prefer SQLite (simpler setup), modify the `app` service in `docker-compose.yml`:

1. Remove `postgres` from `depends_on`
2. Change `DATABASE_URL` environment variable:
   ```yaml
   - DATABASE_URL=sqlite+aiosqlite:///./data/drilldown.db
   ```
3. (Optional) Comment out or remove the `postgres` service

### Without GPU Support

If you don't have NVIDIA GPU or don't need GPU acceleration:

1. Remove the `deploy` section from the `ollama` service in `docker-compose.yml`:
   ```yaml
   # Remove these lines:
   # deploy:
   #   resources:
   #     reservations:
   #       devices:
   #         - driver: nvidia
   #           count: all
   #           capabilities: [gpu]
   ```

### Minimal Setup (No Ecommerce)

To run only the explainer mode without ecommerce features:

1. Comment out or remove the `qdrant` service
2. Remove `qdrant` from app's `depends_on`
3. No need to ingest fashion dataset

## Data Persistence

Docker volumes are used for persistent data:

- `redis_data` - Redis cache
- `postgres_data` - PostgreSQL database
- `qdrant_data` - Qdrant vector store
- `ollama_data` - Ollama models
- `./data` - Application data (uploads, KB, etc.)

These volumes persist even when containers are stopped. To delete all data, use:
```bash
docker-compose down -v
```

## Troubleshooting

### Check service health
```bash
docker-compose ps
```

### View detailed logs
```bash
docker-compose logs -f app
```

### Restart a single service
```bash
docker-compose restart app
```

### Check disk space
```bash
docker system df
```

### Clean up unused Docker resources
```bash
docker system prune -a
```

### Ollama not responding
```bash
# Check if Ollama is running
docker exec -it drilldown-ollama ollama list

# Restart Ollama
docker-compose restart ollama
```

### Database connection issues
```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Connect to PostgreSQL
docker exec -it drilldown-postgres psql -U drilldown -d drilldown
```

## Development

### Run with live code reload
For development, you can mount your source code:

Add to `app` service volumes in `docker-compose.yml`:
```yaml
volumes:
  - ./backend:/app/backend
  - ./frontend:/app/frontend
```

Then restart:
```bash
docker-compose restart app
```

### Run tests inside container
```bash
docker exec -it drilldown-app python3 -m pytest
```

## Production Deployment

For production:

1. Use proper secrets management (not `.env` files)
2. Set `AUTH_COOKIE_SECURE=true`
3. Use PostgreSQL instead of SQLite
4. Configure proper CORS origins
5. Use a reverse proxy (nginx, traefik) for SSL/TLS
6. Set resource limits in docker-compose.yml
7. Enable Docker health checks monitoring
8. Set up log aggregation
9. Regular backups of volumes

Example production additions to docker-compose.yml:
```yaml
services:
  app:
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Support

For issues or questions, check:
- Main README.md
- API documentation at /docs endpoint
- Service logs: `docker-compose logs -f`
