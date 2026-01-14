#!/usr/bin/env python3
"""
Download scholar avatars using the data-proxy API.

This script fetches avatars for all scholars in data/aminer/scholars/
by calling the data-proxy avatar API endpoint. Avatars are cached
by the API service and default avatars are automatically detected and skipped.

Usage:
    # Download all scholars' avatars
    python download_avatars.py

    # Download specific scholars
    python download_avatars.py --ids 53f47489dabfaedf4367d232 53f3a231dabfae4b34ac11ab

    # Custom API URL and delay
    python download_avatars.py --api-url http://localhost:37803 --delay 2
"""

import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Set
import sys

import httpx


# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHOLARS_DIR = PROJECT_ROOT / "data" / "aminer" / "scholars"
AVATAR_DIR = PROJECT_ROOT / "data" / "aminer" / "avatars"

# API Configuration
DEFAULT_API_URL = "http://localhost:37803"
DEFAULT_DELAY = 1.0  # seconds between requests


def load_scholar_ids() -> List[str]:
    """Load all scholar IDs from JSON files in the scholars directory."""
    if not SCHOLARS_DIR.exists():
        print(f"Error: Scholars directory not found: {SCHOLARS_DIR}")
        sys.exit(1)

    scholar_ids = []
    for json_file in SCHOLARS_DIR.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                aminer_id = data.get('aminer_id')
                if aminer_id:
                    scholar_ids.append(aminer_id)
        except Exception as e:
            print(f"Warning: Failed to load {json_file.name}: {e}")
            continue

    return scholar_ids


def get_local_avatar_path(aminer_id: str) -> tuple[Path | None, Path]:
    """
    Check if avatar already exists locally.
    Returns (avatar_path, default_marker_path).
    """
    default_marker = AVATAR_DIR / f"{aminer_id}.default"

    # Check for existing avatar files
    for ext in ['.jpg', '.jpeg', '.png']:
        avatar_path = AVATAR_DIR / f"{aminer_id}{ext}"
        if avatar_path.exists():
            return avatar_path, default_marker

    return None, default_marker


def download_avatar(
    client: httpx.Client,
    api_url: str,
    aminer_id: str,
    force_refresh: bool = False
) -> Dict[str, any]:
    """
    Download avatar for a single scholar using the API and save to local directory.

    Returns:
        Dictionary with status information:
        - success: bool
        - status_code: int
        - message: str
        - size_bytes: int (if success)
    """
    # Check if already exists locally (unless force refresh)
    existing_path, default_marker = get_local_avatar_path(aminer_id)
    if not force_refresh:
        if default_marker.exists():
            return {
                "success": False,
                "status_code": 404,
                "message": "Default avatar (cached)"
            }
        if existing_path:
            size_bytes = existing_path.stat().st_size
            return {
                "success": True,
                "status_code": 200,
                "message": "Already cached",
                "size_bytes": size_bytes
            }

    endpoint = f"{api_url}/api/aminer/scholar/avatar"
    params = {
        "id": aminer_id,
        "force_refresh": str(force_refresh).lower()
    }

    try:
        response = client.get(endpoint, params=params, timeout=200.0)

        if response.status_code == 200:
            # Determine file extension from content-type
            content_type = response.headers.get('content-type', 'image/jpeg')
            if 'png' in content_type:
                ext = '.png'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            else:
                ext = '.jpg'  # default

            # Save to local directory
            AVATAR_DIR.mkdir(parents=True, exist_ok=True)
            avatar_path = AVATAR_DIR / f"{aminer_id}{ext}"

            with open(avatar_path, 'wb') as f:
                f.write(response.content)

            size_bytes = len(response.content)
            return {
                "success": True,
                "status_code": 200,
                "message": "Downloaded",
                "size_bytes": size_bytes
            }
        elif response.status_code == 404:
            # Default avatar or not found - create marker
            AVATAR_DIR.mkdir(parents=True, exist_ok=True)
            default_marker.touch()
            return {
                "success": False,
                "status_code": 404,
                "message": "Default avatar or not found"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "message": f"HTTP {response.status_code}"
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "status_code": 504,
            "message": "Timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "message": f"Error: {str(e)}"
        }


def format_size(bytes_size: int) -> str:
    """Format bytes size to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}TB"


def format_time(seconds: float) -> str:
    """Format seconds to human readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Download scholar avatars using data-proxy API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        help="Specific AMiner IDs to download (if not specified, downloads all)"
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Data-proxy API URL (default: {DEFAULT_API_URL})"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY})"
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh cached avatars"
    )

    args = parser.parse_args()

    # Load scholar IDs
    if args.ids:
        scholar_ids = args.ids
        print(f"Downloading avatars for {len(scholar_ids)} specified scholars")
    else:
        print("Loading scholar IDs from JSON files...")
        scholar_ids = load_scholar_ids()
        print(f"Found {len(scholar_ids)} scholars")

    if not scholar_ids:
        print("No scholars to process")
        return

    # Statistics
    stats = {
        "total": len(scholar_ids),
        "success": 0,
        "default": 0,
        "error": 0,
        "total_bytes": 0
    }

    start_time = time.time()

    # Create HTTP client
    with httpx.Client() as client:
        for i, aminer_id in enumerate(scholar_ids, 1):
            # Progress
            progress = (i / stats["total"]) * 100
            print(f"[{i}/{stats['total']} ({progress:.1f}%)] {aminer_id}", end=" ... ")

            # Download
            result = download_avatar(client, args.api_url, aminer_id, args.force_refresh)

            # Update statistics
            if result["success"]:
                stats["success"] += 1
                stats["total_bytes"] += result["size_bytes"]
                print(f"✓ {result['message']} ({format_size(result['size_bytes'])})")
            elif result["status_code"] == 404:
                stats["default"] += 1
                print(f"⊘ {result['message']}")
            else:
                stats["error"] += 1
                print(f"✗ {result['message']}")

            # Delay between requests (except last one)
            if i < stats["total"]:
                time.sleep(args.delay)

    # Summary
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total:         {stats['total']}")
    print(f"  Success:       {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"  Default/404:   {stats['default']} ({stats['default']/stats['total']*100:.1f}%)")
    print(f"  Errors:        {stats['error']} ({stats['error']/stats['total']*100:.1f}%)")
    print(f"  Downloaded:    {format_size(stats['total_bytes'])}")
    print(f"  Time elapsed:  {format_time(elapsed_time)}")
    print(f"  Avg time/req:  {elapsed_time/stats['total']:.2f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
