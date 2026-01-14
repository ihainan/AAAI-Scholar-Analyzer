"""
Avatar service for fetching and caching AMiner scholar avatars.
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from config import settings
from services.cache_service import get_cache_path, is_cache_valid

logger = logging.getLogger(__name__)

# Default avatar size - if downloaded avatar is this size, it's likely a default avatar
DEFAULT_AVATAR_SIZE = 1676


async def fetch_avatar_url_from_firecrawl(aminer_id: str) -> Optional[str]:
    """
    Fetch avatar URL from AMiner scholar page using Firecrawl API.

    Args:
        aminer_id: AMiner scholar ID

    Returns:
        Avatar URL if found, None otherwise

    Raises:
        HTTPException: If Firecrawl API fails
    """
    scholar_url = f"https://www.aminer.cn/profile/{aminer_id}"
    logger.info(f"[Avatar] Fetching avatar URL for scholar {aminer_id} from Firecrawl")

    # Call Firecrawl API with streaming to avoid memory issues
    api_endpoint = f"{settings.firecrawl_api_url}/scrape"
    payload = {
        "url": scholar_url,
        "formats": ["html"],
        "onlyMainContent": False,
        "waitFor": 3000  # Wait for JavaScript rendering
    }

    try:
        async with httpx.AsyncClient(timeout=settings.firecrawl_timeout) as client:
            async with client.stream("POST", api_endpoint, json=payload) as response:
                if response.status_code != 200:
                    logger.error(f"[Avatar] Firecrawl API returned status {response.status_code}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Firecrawl API error: {response.status_code}"
                    )

                # Stream and search for avatar URL
                buffer = ""
                buffer_size = 1024 * 1024  # 1MB buffer

                # Avatar URL pattern: https://avatarcdn.aminer.cn/upload/avatar/数字/数字/数字/学者ID_数字.扩展名
                avatar_pattern = rf'https://avatarcdn\.aminer\.cn/upload/avatar/\d+/\d+/\d+/{aminer_id}_\d+\.(png|jpg|jpeg)(?:!\d+)?'

                async for chunk in response.aiter_bytes():
                    if chunk:
                        buffer += chunk.decode('utf-8', errors='ignore')

                        # Check if we found the avatar URL
                        if len(buffer) > buffer_size:
                            match = re.search(avatar_pattern, buffer)
                            if match:
                                avatar_url = match.group(0)
                                # Remove size parameter (!160, !80, etc.) to get original image
                                avatar_url = re.sub(r'!\d+$', '', avatar_url)
                                logger.info(f"[Avatar] Found avatar URL: {avatar_url}")
                                return avatar_url
                            # Keep last part of buffer in case URL is split
                            buffer = buffer[-10000:]

                # Final check
                if buffer:
                    match = re.search(avatar_pattern, buffer)
                    if match:
                        avatar_url = match.group(0)
                        avatar_url = re.sub(r'!\d+$', '', avatar_url)
                        logger.info(f"[Avatar] Found avatar URL: {avatar_url}")
                        return avatar_url

                logger.warning(f"[Avatar] No avatar URL found for scholar {aminer_id}")
                return None

    except httpx.TimeoutException:
        logger.error(f"[Avatar] Firecrawl request timeout for scholar {aminer_id}")
        raise HTTPException(status_code=504, detail="Firecrawl API timeout")
    except Exception as e:
        logger.error(f"[Avatar] Firecrawl request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Firecrawl API error: {str(e)}")


async def download_avatar(avatar_url: str) -> Tuple[bytes, str]:
    """
    Download avatar from URL.

    Args:
        avatar_url: Avatar URL to download

    Returns:
        Tuple of (image_bytes, content_type)

    Raises:
        HTTPException: If download fails (should NOT be cached)
    """
    logger.info(f"[Avatar] Downloading avatar from: {avatar_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.aminer.cn/'
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(avatar_url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', 'image/jpeg')
            image_bytes = response.content

            logger.info(f"[Avatar] Downloaded {len(image_bytes)} bytes, content-type: {content_type}")
            return image_bytes, content_type

    except httpx.TimeoutException as e:
        logger.error(f"[Avatar] Download timeout: {e}")
        raise HTTPException(status_code=504, detail="Avatar download timeout - will retry next time")
    except httpx.HTTPStatusError as e:
        logger.error(f"[Avatar] HTTP error {e.response.status_code}: {e}")
        raise HTTPException(status_code=502, detail=f"Avatar download HTTP error - will retry next time")
    except Exception as e:
        logger.error(f"[Avatar] Download failed: {e}")
        raise HTTPException(status_code=502, detail=f"Avatar download error - will retry next time")


def get_file_extension(content_type: str, url: str) -> str:
    """
    Determine file extension from content type and URL.

    Args:
        content_type: HTTP Content-Type header
        url: Avatar URL

    Returns:
        File extension (with dot)
    """
    if 'jpeg' in content_type or 'jpg' in content_type:
        return '.jpg'
    elif 'png' in content_type:
        return '.png'
    else:
        # Fallback to URL extension
        parsed_url = urlparse(url)
        ext = Path(parsed_url.path).suffix
        return ext if ext else '.jpg'


async def get_scholar_avatar(aminer_id: str, force_refresh: bool = False) -> Tuple[bytes, str]:
    """
    Get scholar avatar with caching.

    Flow:
    1. Check if .default marker exists -> raise 404 (no avatar/default, cached)
    2. Check if cached avatar exists and is valid -> return cached
    3. Fetch avatar URL from Firecrawl
       - Not found -> create .default marker, raise 404 (truly no avatar)
    4. Download avatar
       - Network error -> raise 502/504, NO CACHE (allow retry)
       - Success but 1676 bytes -> create .default marker, raise 404 (default avatar)
       - Success -> cache and return

    Caching strategy:
    - .default marker: Only for confirmed no-avatar or default-avatar cases
    - Download failures: NOT cached, will retry on next request

    Args:
        aminer_id: AMiner scholar ID
        force_refresh: Force refresh cache

    Returns:
        Tuple of (image_bytes, content_type)

    Raises:
        HTTPException:
            - 404: Avatar not found or is default (cached, won't retry)
            - 502: Download/Firecrawl error (NOT cached, will retry)
            - 504: Timeout (NOT cached, will retry)
    """
    logger.info(f"[Avatar] Getting avatar for scholar {aminer_id}, force_refresh={force_refresh}")

    # Check for .default marker - if exists, this scholar has default avatar
    default_marker_path = settings.avatar_cache_dir / f"{aminer_id}.default"
    if default_marker_path.exists() and not force_refresh:
        logger.info(f"[Avatar] Scholar {aminer_id} has default avatar (cached)")
        raise HTTPException(status_code=404, detail="Scholar has default avatar")

    # Check for cached avatar (any extension)
    for ext in ['.jpg', '.jpeg', '.png']:
        cache_path = settings.avatar_cache_dir / f"{aminer_id}{ext}"
        if cache_path.exists():
            if not force_refresh and is_cache_valid(cache_path, settings.avatar_cache_ttl):
                logger.info(f"[Avatar] Returning cached avatar: {cache_path}")
                with open(cache_path, 'rb') as f:
                    image_bytes = f.read()
                # Determine content type from extension
                content_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
                return image_bytes, content_type

    # No valid cache, fetch from Firecrawl
    avatar_url = await fetch_avatar_url_from_firecrawl(aminer_id)

    if not avatar_url:
        logger.warning(f"[Avatar] No avatar found for scholar {aminer_id}")
        # Create .default marker - scholar truly has no avatar
        default_marker_path.touch()
        raise HTTPException(status_code=404, detail="Avatar not found")

    # Download avatar (may raise HTTPException on network errors - should NOT be cached)
    image_bytes, content_type = await download_avatar(avatar_url)

    # Check if it's default avatar
    if len(image_bytes) == DEFAULT_AVATAR_SIZE:
        logger.info(f"[Avatar] Scholar {aminer_id} has default avatar ({DEFAULT_AVATAR_SIZE} bytes)")
        # Create .default marker - confirmed default avatar
        default_marker_path.touch()
        raise HTTPException(status_code=404, detail="Scholar has default avatar")

    # Save to cache
    ext = get_file_extension(content_type, avatar_url)
    cache_path = settings.avatar_cache_dir / f"{aminer_id}{ext}"

    try:
        with open(cache_path, 'wb') as f:
            f.write(image_bytes)
        logger.info(f"[Avatar] Cached avatar to: {cache_path}")

        # Remove .default marker if exists (in case of previous failure)
        if default_marker_path.exists():
            default_marker_path.unlink()
            logger.info(f"[Avatar] Removed stale .default marker for {aminer_id}")
    except Exception as e:
        logger.error(f"[Avatar] Failed to cache avatar: {e}")
        # Don't fail the request if caching fails

    return image_bytes, content_type
