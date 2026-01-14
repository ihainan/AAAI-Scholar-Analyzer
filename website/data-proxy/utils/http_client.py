"""
HTTP client utilities for external API requests.
"""

import httpx
from config import settings


# HTTP client for external API requests
http_client = httpx.AsyncClient(
    timeout=settings.http_timeout,
    follow_redirects=True
)


async def close_clients():
    """Close all HTTP clients. Call this on app shutdown."""
    await http_client.aclose()
