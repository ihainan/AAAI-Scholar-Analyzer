"""
Cache management service for API responses and assets.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings


def get_cache_path(cache_dir: Path, item_id: str, extension: str = ".json") -> Path:
    """
    Generate cache file path for an item.

    Args:
        cache_dir: Cache directory path
        item_id: Unique identifier for the cached item
        extension: File extension (default: .json)

    Returns:
        Path to cache file
    """
    return cache_dir / f"{item_id}{extension}"


def is_cache_valid(cache_path: Path, ttl_seconds: int) -> bool:
    """
    Check if cache file is still valid (within TTL).

    Args:
        cache_path: Path to cache file
        ttl_seconds: Time-to-live in seconds

    Returns:
        True if cache is valid, False otherwise
    """
    if not cache_path.exists():
        return False

    cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
    return cache_age < ttl_seconds


def read_json_cache(cache_path: Path) -> Optional[dict]:
    """
    Read JSON data from cache file.

    Args:
        cache_path: Path to cache file

    Returns:
        Cached data or None if read fails
    """
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json_cache(cache_path: Path, data: dict) -> bool:
    """
    Write JSON data to cache file.

    Args:
        cache_path: Path to cache file
        data: Data to cache

    Returns:
        True if write succeeds, False otherwise
    """
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def clear_cache_directory(cache_dir: Path) -> int:
    """
    Clear all files in a cache directory.

    Args:
        cache_dir: Cache directory to clear

    Returns:
        Number of files deleted
    """
    count = 0
    if cache_dir.exists():
        for file in cache_dir.iterdir():
            if file.is_file():
                file.unlink()
                count += 1
    return count


def get_cache_stats(cache_path: Path) -> dict:
    """
    Get cache statistics (age, size, etc.).

    Args:
        cache_path: Path to cache file

    Returns:
        Dictionary with cache statistics
    """
    if not cache_path.exists():
        return {"exists": False}

    stat = cache_path.stat()
    age_seconds = datetime.now().timestamp() - stat.st_mtime
    age_days = age_seconds / (24 * 60 * 60)
    age_hours = age_seconds / 3600

    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "age_seconds": age_seconds,
        "age_hours": age_hours,
        "age_days": age_days,
        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }
