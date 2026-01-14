"""
AMiner API routes for scholar data.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import Response

from config import settings
from services.aminer_service import get_scholar_detail
from services.avatar_service import get_scholar_avatar
from services.email_service import get_scholar_email_image
from services.cache_service import clear_cache_directory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aminer", tags=["AMiner"])


@router.get("/scholar/detail")
async def get_aminer_scholar_detail_endpoint(
    id: str = Query(..., description="AMiner scholar ID"),
    authorization: Optional[str] = Header(None, description="AMiner authorization token"),
    x_signature: Optional[str] = Header(None, alias="X-Signature", description="AMiner API signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp", description="AMiner API timestamp"),
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get scholar detail from AMiner web API with caching.

    This endpoint mimics the official AMiner API format while using the web API internally.
    Responses are cached for 15 days by default.

    Headers required:
    - Authorization: AMiner bearer token
    - X-Signature: Request signature
    - X-Timestamp: Request timestamp

    Query parameters:
    - id: Scholar AMiner ID (required)
    - force_refresh: Force refresh cache (optional, default: false)
    """
    logger.info(f"[API Request] GET /aminer/scholar/detail - Scholar ID: {id}, Force Refresh: {force_refresh}")

    # Validate required headers
    if not authorization:
        logger.warning(f"[API Request] Missing Authorization header for scholar {id}")
        raise HTTPException(status_code=400, detail="Authorization header is required")
    if not x_signature:
        logger.warning(f"[API Request] Missing X-Signature header for scholar {id}")
        raise HTTPException(status_code=400, detail="X-Signature header is required")
    if not x_timestamp:
        logger.warning(f"[API Request] Missing X-Timestamp header for scholar {id}")
        raise HTTPException(status_code=400, detail="X-Timestamp header is required")

    return await get_scholar_detail(id, authorization, x_signature, x_timestamp, force_refresh)


@router.post("/cache/clear")
def clear_aminer_cache_endpoint():
    """Clear all cached AMiner web API responses."""
    logger.info("[Cache Management] Clearing all AMiner API cache")
    count = clear_cache_directory(settings.aminer_cache_dir)
    logger.info(f"[Cache Management] Cleared {count} cached files")
    return {"status": "aminer cache cleared", "files_deleted": count}


@router.get("/scholar/avatar")
async def get_scholar_avatar_endpoint(
    id: str = Query(..., description="AMiner scholar ID"),
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get scholar avatar image with caching.

    This endpoint fetches scholar avatars from AMiner using Firecrawl to handle JavaScript rendering.
    Avatars are cached permanently to avoid repeated fetching.

    Default avatars (1676 bytes) are detected and marked - subsequent requests will return 404
    without fetching again.

    Query parameters:
    - id: Scholar AMiner ID (required)
    - force_refresh: Force refresh cache (optional, default: false)

    Returns:
        Image binary data (JPEG or PNG)

    Raises:
        404: Avatar is default or not found
        502: Firecrawl or download error
        504: Timeout
    """
    logger.info(f"[API Request] GET /aminer/scholar/avatar - Scholar ID: {id}, Force Refresh: {force_refresh}")

    try:
        image_bytes, content_type = await get_scholar_avatar(id, force_refresh)
        return Response(content=image_bytes, media_type=content_type)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"[API Request] Unexpected error for scholar {id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scholar/email")
async def get_scholar_email_endpoint(
    id: str = Query(..., description="AMiner scholar ID"),
    authorization: Optional[str] = Header(None, description="AMiner authorization token"),
    x_signature: Optional[str] = Header(None, alias="X-Signature", description="AMiner API signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp", description="AMiner API timestamp"),
    force_refresh: bool = Query(False, description="Force refresh cache"),
    format: str = Query("png", description="Output format: png or jpg (default: png)"),
):
    """
    Get scholar email image with caching and white background conversion.

    This endpoint fetches email images from AMiner's getPerson API. The email field
    contains a path to an image endpoint that renders the email address as an image
    to prevent scraping.

    Images are automatically converted from transparent background (RGBA) to white
    background (RGB) for better OCR compatibility. The converted white-background
    PNG is cached for 30 days.

    The workflow is:
    1. Read cached scholar detail data (from /api/aminer/scholar/detail)
    2. Extract email image path from cached data
    3. Fetch email image from AMiner (if not cached)
    4. Convert transparent background to white background
    5. Cache the converted image as PNG for 30 days
    6. Return in requested format (PNG or JPEG)

    Headers required:
    - Authorization: AMiner bearer token
    - X-Signature: Request signature
    - X-Timestamp: Request timestamp

    Query parameters:
    - id: Scholar AMiner ID (required)
    - force_refresh: Force refresh cache (optional, default: false)
    - format: Output format, "png" or "jpg" (optional, default: "png")
      - PNG: Smaller file size, recommended for most use cases
      - JPEG: Larger file size, may work better with some OCR systems

    Returns:
        Image binary data with white background (PNG or JPEG)

    Raises:
        400: Invalid email path format or missing headers
        404: Scholar data not cached or no email available
        500: Failed to read cached data
        502: Failed to fetch from AMiner

    Note:
        The cached image is always stored as white-background PNG for optimal
        storage efficiency. JPEG conversion is done dynamically on request.
    """
    logger.info(
        f"[API Request] GET /aminer/scholar/email - Scholar ID: {id}, "
        f"Force Refresh: {force_refresh}, Format: {format}"
    )

    # Validate required headers
    if not authorization:
        logger.warning(f"[API Request] Missing Authorization header for scholar {id}")
        raise HTTPException(status_code=400, detail="Authorization header is required")
    if not x_signature:
        logger.warning(f"[API Request] Missing X-Signature header for scholar {id}")
        raise HTTPException(status_code=400, detail="X-Signature header is required")
    if not x_timestamp:
        logger.warning(f"[API Request] Missing X-Timestamp header for scholar {id}")
        raise HTTPException(status_code=400, detail="X-Timestamp header is required")

    # Validate format parameter
    output_format = format.upper()
    if output_format not in ["PNG", "JPG", "JPEG"]:
        logger.warning(f"[API Request] Invalid format parameter: {format}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format: {format}. Supported formats: png, jpg"
        )

    # Normalize JPEG to JPG
    if output_format == "JPG":
        output_format = "JPEG"

    try:
        image_bytes, content_type = await get_scholar_email_image(
            id, authorization, x_signature, x_timestamp,
            force_refresh=force_refresh,
            output_format=output_format,
            convert_to_white_bg=True
        )
        return Response(content=image_bytes, media_type=content_type)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"[API Request] Unexpected error for scholar {id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
