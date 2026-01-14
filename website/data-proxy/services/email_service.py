"""
Email image service for fetching scholar email images from AMiner.
"""

import io
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import httpx
from fastapi import HTTPException
from PIL import Image

from config import settings
from services.cache_service import (
    get_cache_path,
    get_cache_stats,
    is_cache_valid,
    read_json_cache,
)
from utils.http_client import http_client

logger = logging.getLogger(__name__)


def convert_transparent_to_white_bg(image_bytes: bytes, output_format: str = "PNG") -> Tuple[bytes, str]:
    """
    Convert image with transparent background to white background.

    This is useful for OCR, as many OCR models work better with
    black text on white background rather than transparent background.

    Args:
        image_bytes: Original image bytes (may have transparency)
        output_format: Output format, "PNG" or "JPEG"

    Returns:
        Tuple of (converted_image_bytes, content_type)
    """
    try:
        # Open image
        img = Image.open(io.BytesIO(image_bytes))

        logger.debug(f"[Image Convert] Original: mode={img.mode}, size={img.size}, format={img.format}")

        # Handle transparency
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            logger.debug(f"[Image Convert] Image has transparency, converting to white background")

            # Create white background
            white_bg = Image.new('RGB', img.size, (255, 255, 255))

            # Paste image on white background
            if img.mode == 'RGBA':
                white_bg.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            elif img.mode == 'LA':
                white_bg.paste(img, mask=img.split()[1])  # Use alpha channel as mask
            else:
                white_bg.paste(img)

            img = white_bg
        else:
            # Convert to RGB if needed
            if img.mode != 'RGB':
                logger.debug(f"[Image Convert] Converting {img.mode} to RGB")
                img = img.convert('RGB')

        # Save to bytes
        output = io.BytesIO()
        if output_format.upper() == "JPEG":
            img.save(output, format='JPEG', quality=95, optimize=True)
            content_type = "image/jpeg"
        else:  # PNG
            img.save(output, format='PNG', optimize=True)
            content_type = "image/png"

        converted_bytes = output.getvalue()

        logger.info(
            f"[Image Convert] {len(image_bytes)} bytes → {len(converted_bytes)} bytes "
            f"({len(converted_bytes) / len(image_bytes) * 100:.1f}%), format={output_format}"
        )

        return converted_bytes, content_type

    except Exception as e:
        logger.error(f"[Image Convert] Failed to convert image: {e}")
        # Return original image if conversion fails
        return image_bytes, "image/png"


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
    force_refresh: bool = False,
    output_format: str = "PNG",
    convert_to_white_bg: bool = True
) -> Tuple[bytes, str]:
    """
    Get scholar email image with caching and optional white background conversion.

    This function:
    1. Checks if "no email" marker exists (cached 404)
    2. Reads cached getPerson response to extract email path
    3. Checks if email image is cached
    4. If not cached or force_refresh, fetches from AMiner
    5. Optionally converts transparent background to white (for better OCR)
    6. Caches the converted image or "no email" marker

    Args:
        scholar_id: AMiner scholar ID
        authorization: Authorization token
        x_signature: Request signature
        x_timestamp: Request timestamp
        force_refresh: Force refresh cache
        output_format: Output format, "PNG" or "JPEG" (default: "PNG")
        convert_to_white_bg: Convert transparent background to white (default: True)

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
        # Old format detected - need to refresh cache to get raw_response
        logger.warning(
            f"[Email Image] Old cache format detected for scholar {scholar_id}, "
            "refreshing to get raw_response with email field"
        )

        # Import here to avoid circular dependency
        from services.aminer_service import get_scholar_detail

        # Force refresh the scholar data to get new format with raw_response
        try:
            logger.info(f"[Email Image] Refreshing scholar data for {scholar_id} to get email field")
            # This will update the cache with new format (raw_response + official_format)
            await get_scholar_detail(
                scholar_id,
                authorization,
                x_signature,
                x_timestamp,
                force_refresh=True  # Force refresh to update cache
            )

            # Re-read the cache which should now have raw_response
            cached_person_data = read_json_cache(person_cache_path)
            if cached_person_data and "raw_response" in cached_person_data:
                try:
                    raw_response = cached_person_data["raw_response"]
                    email_path = raw_response["data"][0]["data"][0]["profile"].get("email", "")
                    logger.info(f"[Email Image] Successfully extracted email path after refresh")
                except (KeyError, IndexError, TypeError) as e:
                    logger.warning(f"[Email Image] Failed to extract email from refreshed data: {e}")
            else:
                logger.warning(f"[Email Image] Refreshed cache still doesn't have raw_response")
        except Exception as e:
            logger.error(f"[Email Image] Failed to refresh scholar data: {e}")
            # Continue with empty email_path, will be handled below

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
    # We always cache white-background PNG for best OCR compatibility and file size
    # If user requests JPEG, we convert from cached PNG dynamically
    email_cache_file = get_cache_path(settings.email_cache_dir, scholar_id, extension=".png")

    # Check if cache is valid
    if not force_refresh and email_cache_file.exists() and is_cache_valid(email_cache_file, settings.email_cache_ttl):
        cache_stats = get_cache_stats(email_cache_file)
        logger.info(
            f"[Email Cache] HIT for scholar {scholar_id} - "
            f"Age: {cache_stats['age_days']:.1f} days ({cache_stats['age_hours']:.1f} hours)"
        )

        # Read cached image (white-background PNG)
        try:
            with open(email_cache_file, "rb") as f:
                cached_image_bytes = f.read()

            logger.info(f"[Email Cache] Returning cached image: {email_cache_file}")

            # If user requests JPEG, convert from PNG
            if output_format.upper() == "JPEG":
                logger.info(f"[Email Cache] Converting cached PNG to JPEG for output")
                return convert_transparent_to_white_bg(cached_image_bytes, "JPEG")
            else:
                # Return cached PNG directly
                return cached_image_bytes, "image/png"

        except Exception as e:
            logger.error(f"[Email Cache] Failed to read cached file: {e}")
            # Continue to fetch fresh data

    if force_refresh:
        logger.info(f"[Email Cache] Force refresh requested for scholar {scholar_id}")
    elif not email_cache_file.exists():
        logger.info(f"[Email Cache] MISS for scholar {scholar_id} - No cache file found")
    else:
        cache_stats = get_cache_stats(email_cache_file)
        logger.info(
            f"[Email Cache] EXPIRED for scholar {scholar_id} - "
            f"Age: {cache_stats['age_days']:.1f} days (TTL: 30 days)"
        )

    # Step 3: Fetch from AMiner
    logger.info(f"[Email Image] Fetching fresh data from AMiner for scholar {scholar_id}")
    raw_image_bytes, raw_content_type = await fetch_email_image_from_aminer(
        email_path, authorization, x_signature, x_timestamp
    )

    # Step 4: Convert to white background PNG for caching (best for OCR and file size)
    if convert_to_white_bg:
        logger.info(f"[Email Image] Converting to white background PNG for caching")
        cached_image_bytes, _ = convert_transparent_to_white_bg(raw_image_bytes, "PNG")
    else:
        logger.info(f"[Email Image] Using original image without conversion")
        cached_image_bytes = raw_image_bytes

    # Step 5: Cache the converted white-background PNG
    try:
        with open(email_cache_file, "wb") as f:
            f.write(cached_image_bytes)
        logger.info(f"[Email Cache] Cached white-background PNG for scholar {scholar_id} to: {email_cache_file}")

        # Remove no-email marker if it exists (email is now available)
        no_email_marker = get_cache_path(settings.email_cache_dir, scholar_id, extension=".no_email")
        if no_email_marker.exists():
            no_email_marker.unlink()
            logger.info(f"[Email Cache] Removed no-email marker for scholar {scholar_id}")

        # Delete old cached images with different extensions
        email_cache_base = get_cache_path(settings.email_cache_dir, scholar_id, extension="")
        for ext in [".jpg", ".jpeg", ".gif", ".webp"]:
            old_file = Path(str(email_cache_base) + ext)
            if old_file.exists() and old_file != email_cache_file:
                try:
                    old_file.unlink()
                    logger.info(f"[Email Cache] Removed old cached image: {old_file}")
                except Exception as e:
                    logger.error(f"[Email Cache] Failed to remove old image: {e}")

    except Exception as e:
        logger.error(f"[Email Cache] Failed to cache image: {e}")

    # Step 6: Return in requested format
    if output_format.upper() == "JPEG":
        logger.info(f"[Email Image] Converting to JPEG for output")
        return convert_transparent_to_white_bg(cached_image_bytes, "JPEG")
    else:
        return cached_image_bytes, "image/png"
