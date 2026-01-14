# Data Proxy Service

A modular data gateway service that provides:
- **AMiner API Proxy**: Converts AMiner Web API to official API format with caching
- **Future**: Expose internal data (conferences, scholars) for external consumption

## Architecture

```
data-proxy/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration management (.env support)
├── routes/              # API route modules
│   └── aminer.py       # AMiner API endpoints
├── services/            # Business logic layer
│   ├── aminer_service.py   # AMiner API integration
│   └── cache_service.py    # Caching utilities
└── utils/               # Utility modules
    └── http_client.py  # HTTP client for external APIs
```

## Configuration

### Development

Copy `.env.example` to `.env` and adjust settings:

```bash
cp .env.example .env
```

### Production (Docker)

Copy `.env.prod.example` to `.env.prod` and adjust settings:

```bash
cp .env.prod.example .env.prod
```

Docker Compose will automatically read `.env.prod` when starting the service.

Key configuration options:

**Docker Configuration (Production only)**:
- `HOST_PORT`: Port exposed on host machine (default: 37803)
- `CACHE_HOST_DIR`: Cache directory on host machine (default: ./cache_data)

**Application Configuration**:
- `HOST`: Service binding address inside container (default: 0.0.0.0)
- `PORT`: Port application listens on inside container (default: 37803)
  - Docker maps `HOST_PORT` (host) → `PORT` (container)
- `CACHE_DIR`: Cache storage location inside container (default: /app/cache)
- `AMINER_CACHE_TTL`: AMiner API cache TTL in seconds (default: 15 days / 1296000s)
- `HTTP_TIMEOUT`: HTTP client timeout for AMiner API requests in seconds (default: 30)
  - **Important**: Use integer value (e.g., `30`) not float (e.g., `30.0`) to avoid uv parsing issues
- `CORS_ORIGINS`: CORS allowed origins (default: *)
- `LOG_LEVEL`: Logging level (default: INFO)

## Development

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
# Install dependencies
uv sync

# Run development server (with hot reload)
uv run uvicorn main:app --host 0.0.0.0 --port 37803 --reload
```

### API Documentation

Once running, visit:
- Swagger UI: http://localhost:37803/docs
- ReDoc: http://localhost:37803/redoc

## Production Deployment

### Using Docker Compose (Recommended)

From the `website/data-proxy` directory:

```bash
# Step 1: Create production environment configuration
cp .env.prod.example .env.prod
# Edit .env.prod to adjust settings as needed

# Step 2: Build and start data-proxy service
docker compose up -d

# View logs
docker compose logs -f data-proxy

# Stop service
docker compose down
```

The service will be directly available at `http://localhost:${HOST_PORT}` (default: 37803)

**Configuration Examples**:

1. **Use a different host port** (e.g., 8080):
   ```bash
   # In .env.prod
   HOST_PORT=8080    # External access via port 8080
   PORT=37803        # Application listens on 37803 inside container
   ```
   Access at `http://localhost:8080` (maps to container port 37803)

2. **Use a custom cache directory**:
   ```bash
   # In .env.prod
   CACHE_HOST_DIR=/var/data/aminer-cache
   ```
   Ensure the directory exists: `mkdir -p /var/data/aminer-cache`

3. **Change application port** (advanced):
   ```bash
   # In .env.prod
   HOST_PORT=8080    # External port
   PORT=8080         # Application also listens on 8080
   ```
   Both host and container use port 8080

### Standalone Docker

```bash
# Build image
docker build -t data-proxy .

# Run container
docker run -d \
  -p 37803:37803 \
  -v data_proxy_cache:/app/cache \
  --name scholar-data-proxy \
  data-proxy
```

## API Endpoints

### Health Check
```
GET /health
```

### AMiner API

#### Get Scholar Detail
```
GET /api/aminer/scholar/detail?id={scholar_id}&force_refresh={bool}
```

Required headers:
- `Authorization`: AMiner bearer token
- `X-Signature`: Request signature
- `X-Timestamp`: Request timestamp

Response: Scholar detail in official AMiner API format with enriched fields.

**Automatic Retry**: The endpoint automatically retries failed requests once after a 5-second delay, making it more resilient to temporary network issues or API rate limits.

#### Clear Cache
```
POST /api/aminer/cache/clear
```

Clears all cached AMiner API responses.

## Adding New Data Sources

To add a new data source:

1. Create a service module in `services/` (e.g., `myapi_service.py`)
2. Create a route module in `routes/` (e.g., `myapi.py`)
3. Register the router in `main.py`:
   ```python
   from routes import myapi
   app.include_router(myapi.router, prefix="/api")
   ```

## Cache Management

The service uses file-based caching:
- **AMiner API**: 15-day TTL, stored in `{CACHE_DIR}/aminer/`
- Cache can be cleared via API endpoints or by deleting files

## Logging

Structured logging with configurable levels:
- `DEBUG`: Detailed request/response logging
- `INFO`: Request summary and cache hits/misses (default)
- `WARNING`: Potential issues
- `ERROR`: Failures and exceptions

Set via `LOG_LEVEL` environment variable.
