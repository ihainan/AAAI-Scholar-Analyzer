"""
Data Proxy Service

A data gateway service providing:
- AMiner API proxy and format conversion
- Future: Internal data exposure for external consumption
"""

import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from routes import aminer
from utils.http_client import close_clients

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Data Proxy Service",
    version="0.1.0",
    description="Data gateway for external APIs and internal data exposure"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str


# Routes
@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        service="data-proxy"
    )


# Register routers
app.include_router(aminer.router, prefix="/api")


# Lifecycle events
@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    logger.info("Starting Data Proxy Service...")
    logger.info(f"Configuration:")
    logger.info(f"  - Host: {settings.host}:{settings.port}")
    logger.info(f"  - Cache Dir: {settings.cache_dir}")
    logger.info(f"  - AMiner Cache TTL: {settings.aminer_cache_ttl}s ({settings.aminer_cache_ttl / 86400:.0f} days)")
    logger.info(f"  - CORS Origins: {settings.cors_origins}")
    logger.info(f"  - Log Level: {settings.log_level}")
    logger.info("Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks."""
    logger.info("Shutting down Data Proxy Service...")
    await close_clients()
    logger.info("Service stopped")


if __name__ == "__main__":
    import uvicorn
    import os

    # Enable reload only in development (check ENV environment variable)
    # Set ENV=production in .env.prod to disable reload
    is_production = os.getenv("ENV", "development") == "production"

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=not is_production,
        reload_excludes=["cache/*"] if not is_production else None
    )
