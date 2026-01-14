"""
Email image service for fetching scholar email images from AMiner.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import httpx
from fastapi import HTTPException

from config import settings
from services.cache_service import (
    get_cache_path,
    get_cache_stats,
    is_cache_valid,
    read_json_cache,
)
from utils.http_client import http_client

logger = logging.getLogger(__name__)


async def fetch_email_image_from_aminer(
    email_path: str,
    authorization: str,
    x_signature: str,
    x_timestamp: str
) -> Tuple[bytes, str]:
    """
    Fetch email image from AMiner API.

    Args:
        email_path: Email image path (e.g., /magic?W3siYWN...)
        authorization: Authorization token
        x_signature: Request signature
        x_timestamp: Request timestamp

    Returns:
        Tuple of (image_bytes, content_type)

    Raises:
        HTTPException: If fetch fails
    """
    if not email_path.startswith("/magic"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid email path format: {email_path}"
        )

    url = f"https://apiv2.aminer.cn{email_path}"
    logger.info(f"[Email Image] Fetching from: {url}")

    headers = {
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Authorization": authorization,
        "X-Signature": x_signature,
        "X-Timestamp": x_timestamp,
        "Referer": "https://www.aminer.cn/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }

    try:
        response = await http_client.get(url, headers=headers)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "image/png")
        image_bytes = response.content

        logger.info(f"[Email Image] Successfully fetched - Size: {len(image_bytes)} bytes, Type: {content_type}")

        if not content_type.startswith("image/"):
            logger.warning(f"[Email Image] Unexpected content type: {content_type}")

        return image_bytes, content_type

    except httpx.HTTPError as e:
        logger.error(f"[Email Image] Failed to fetch: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch email image from AMiner: {str(e)}"
        )


def get_image_extension(content_type: str) -> str:
    """Determine file extension from content type."""
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    elif "png" in content_type:
        return ".png"
    elif "gif" in content_type:
        return ".gif"
    elif "webp" in content_type:
        return ".webp"
    else:
        return ".png"  # Default to PNG


async def get_scholar_email_image(
    scholar_id: str,
    authorization: str,
    x_signature: str,
    x_timestamp: str,
    force_refresh: bool = False
) -> Tuple[bytes, str]:
    """
    Get scholar email image with caching.

    This function:
    1. Checks if "no email" marker exists (cached 404)
    2. Reads cached getPerson response to extract email path
    3. Checks if email image is cached
    4. If not cached or force_refresh, fetches from AMiner
    5. Caches the image or "no email" marker

    Args:
        scholar_id: AMiner scholar ID
        authorization: Authorization token
        x_signature: Request signature
        x_timestamp: Request timestamp
        force_refresh: Force refresh cache

    Returns:
        Tuple of (image_bytes, content_type)

    Raises:
        HTTPException: If email not found or fetch fails
    """
    logger.info(f"[Email Image] Request for scholar ID: {scholar_id}, Force Refresh: {force_refresh}")

    # Check for "no email" marker (cached 404)
    no_email_marker = get_cache_path(settings.email_cache_dir, scholar_id, extension=".no_email")
    if not force_refresh and is_cache_valid(no_email_marker, settings.email_cache_ttl):
        cache_stats = get_cache_stats(no_email_marker)
        logger.info(
            f"[Email Cache] No-email marker HIT for scholar {scholar_id} - "
            f"Age: {cache_stats['age_days']:.1f} days ({cache_stats['age_hours']:.1f} hours)"
        )
        raise HTTPException(
            status_code=404,
            detail="No email available for this scholar"
        )

    # Step 1: Read cached getPerson response to get email path
    person_cache_path = get_cache_path(settings.aminer_cache_dir, scholar_id)
    if not person_cache_path.exists():
        logger.warning(f"[Email Image] No cached person data found for {scholar_id}")
        raise HTTPException(
            status_code=404,
            detail="Scholar data not cached. Please fetch scholar detail first."
        )

    cached_person_data = read_json_cache(person_cache_path)
    if not cached_person_data:
        logger.error(f"[Email Image] Failed to read cached person data for {scholar_id}")
        raise HTTPException(
            status_code=500,
            detail="Failed to read cached scholar data"
        )

    # Extract email path from raw_response or old format
    email_path = None
    if "raw_response" in cached_person_data:
        # New format with raw_response
        try:
            raw_response = cached_person_data["raw_response"]
            email_path = raw_response["data"][0]["data"][0]["profile"].get("email", "")
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"[Email Image] Failed to extract email from raw_response: {e}")
    else:
        # Old format - try to extract from official_format if it has the enriched data
        # But this is unlikely to work for old format, so we'll just log a warning
        logger.warning(f"[Email Image] Old cache format detected - cannot extract email path reliably")

    if not email_path:
        logger.info(f"[Email Image] No email found for scholar {scholar_id}")

        # Delete any existing cached images for this scholar
        email_cache_base = get_cache_path(settings.email_cache_dir, scholar_id, extension="")
        for ext in [".png", ".jpg", ".gif", ".webp"]:
            old_file = Path(str(email_cache_base) + ext)
            if old_file.exists():
                try:
                    old_file.unlink()
                    logger.info(f"[Email Cache] Removed old cached image: {old_file}")
                except Exception as e:
                    logger.error(f"[Email Cache] Failed to remove old image: {e}")

        # Cache the "no email" state with a marker file
        try:
            no_email_marker.touch()
            logger.info(f"[Email Cache] Created no-email marker for scholar {scholar_id}: {no_email_marker}")
        except Exception as e:
            logger.error(f"[Email Cache] Failed to create no-email marker: {e}")

        raise HTTPException(
            status_code=404,
            detail="No email available for this scholar"
        )

    logger.info(f"[Email Image] Found email path: {email_path}")

    # Step 2: Check email image cache
    # Use scholar_id as cache key (one email image per scholar)
    email_cache_base = get_cache_path(settings.email_cache_dir, scholar_id, extension="")

    # Check for any existing cached email image with different extensions
    cached_file: Optional[Path] = None
    for ext in [".png", ".jpg", ".gif", ".webp"]:
        potential_file = Path(str(email_cache_base) + ext)
        if potential_file.exists():
            cached_file = potential_file
            break

    # Check if cache is valid
    if not force_refresh and cached_file and is_cache_valid(cached_file, settings.email_cache_ttl):
        cache_stats = get_cache_stats(cached_file)
        logger.info(
            f"[Email Cache] HIT for scholar {scholar_id} - "
            f"Age: {cache_stats['age_days']:.1f} days ({cache_stats['age_hours']:.1f} hours)"
        )

        # Read cached image
        try:
            with open(cached_file, "rb") as f:
                image_bytes = f.read()

            # Determine content type from extension
            ext = cached_file.suffix
            content_type_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            content_type = content_type_map.get(ext, "image/png")

            logger.info(f"[Email Cache] Returning cached image: {cached_file}")
            return image_bytes, content_type

        except Exception as e:
            logger.error(f"[Email Cache] Failed to read cached file: {e}")
            # Continue to fetch fresh data

    if force_refresh:
        logger.info(f"[Email Cache] Force refresh requested for scholar {scholar_id}")
    elif not cached_file:
        logger.info(f"[Email Cache] MISS for scholar {scholar_id} - No cache file found")
    else:
        cache_stats = get_cache_stats(cached_file)
        logger.info(
            f"[Email Cache] EXPIRED for scholar {scholar_id} - "
            f"Age: {cache_stats['age_days']:.1f} days (TTL: 30 days)"
        )

    # Step 3: Fetch from AMiner
    logger.info(f"[Email Image] Fetching fresh data from AMiner for scholar {scholar_id}")
    image_bytes, content_type = await fetch_email_image_from_aminer(
        email_path, authorization, x_signature, x_timestamp
    )

    # Step 4: Cache the image
    ext = get_image_extension(content_type)
    cache_file = Path(str(email_cache_base) + ext)

    try:
        with open(cache_file, "wb") as f:
            f.write(image_bytes)
        logger.info(f"[Email Cache] Cached image for scholar {scholar_id} to: {cache_file}")

        # Remove no-email marker if it exists (email is now available)
        no_email_marker = get_cache_path(settings.email_cache_dir, scholar_id, extension=".no_email")
        if no_email_marker.exists():
            no_email_marker.unlink()
            logger.info(f"[Email Cache] Removed no-email marker for scholar {scholar_id}")

    except Exception as e:
        logger.error(f"[Email Cache] Failed to cache image: {e}")

    return image_bytes, content_type
