#!/usr/bin/env python3
"""
Common utilities for AMiner scholar enrichment.

This module provides shared functionality for scripts that enrich scholar data
using the AMiner API through the data-proxy service.
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# Add parent directory to path for common_utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from common_utils import Colors, load_json_file, save_json_file


# API Configuration
DEFAULT_API_BASE_URL = "http://localhost:37804"
SCHOLAR_DETAIL_ENDPOINT = "/api/aminer/scholar/detail"


def get_api_credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Get API credentials from environment variables.

    Returns:
        Tuple of (authorization, signature, timestamp)
    """
    authorization = os.environ.get("AMINER_AUTH")
    signature = os.environ.get("AMINER_SIGNATURE")
    timestamp = os.environ.get("AMINER_TIMESTAMP")

    # Clean up credentials
    if authorization:
        authorization = authorization.strip().replace('\n', '').replace('\r', '')
    if signature:
        signature = signature.strip().replace('\n', '').replace('\r', '')
    if timestamp:
        timestamp = timestamp.strip().replace('\n', '').replace('\r', '')

    return authorization, signature, timestamp


def load_cached_scholar_data(
    aminer_dir: Path,
    enriched_dir: Path,
    aminer_id: str
) -> Optional[tuple[dict, dict]]:
    """
    Load cached scholar data if exists.

    Args:
        aminer_dir: Directory for AMiner cache files
        enriched_dir: Directory for enriched data files
        aminer_id: Scholar's AMiner ID

    Returns:
        Tuple of (aminer_data, enriched_data) or None if cache doesn't exist
    """
    aminer_file = aminer_dir / f"{aminer_id}.json"
    enriched_file = enriched_dir / f"{aminer_id}.json"

    # Both files must exist to use cache
    if aminer_file.exists() and enriched_file.exists():
        aminer_data = load_json_file(aminer_file)
        enriched_data = load_json_file(enriched_file)
        return (aminer_data, enriched_data)

    return None


def fetch_scholar_from_api(
    aminer_id: str,
    api_base_url: str,
    authorization: str,
    signature: str,
    timestamp: str,
    force_refresh: bool = False,
    verbose: bool = False
) -> tuple[Optional[dict], Optional[str]]:
    """
    Fetch scholar data from data-proxy API.

    Args:
        aminer_id: Scholar's AMiner ID
        api_base_url: Base URL of the API
        authorization: Authorization token
        signature: X-Signature value
        timestamp: X-Timestamp value
        force_refresh: Force refresh cache
        verbose: Whether to print detailed progress

    Returns:
        Tuple of (API response or None if failed, error message or None if successful)
    """
    if verbose:
        print(f"       Fetching from API...", end="", flush=True)

    url = f"{api_base_url}{SCHOLAR_DETAIL_ENDPOINT}"
    headers = {
        "Authorization": authorization,
        "X-Signature": signature,
        "X-Timestamp": timestamp,
    }
    params = {
        "id": aminer_id,
        "force_refresh": "true" if force_refresh else "false",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            if verbose:
                print(f" {Colors.GREEN}OK{Colors.ENDC}")
            return (result, None)
        else:
            error_msg = result.get("msg", "Unknown error")
            if verbose:
                print(f" {Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
            return (None, error_msg)
    except Exception as e:
        error_msg = str(e)
        if verbose:
            print(f" {Colors.RED}ERROR{Colors.ENDC} ({error_msg})")
        return (None, error_msg)


def convert_api_to_aminer_format(api_response: dict, aminer_id: str, data_source: str) -> dict:
    """
    Convert API response to AMiner JSON format for data/aminer/scholars.

    Args:
        api_response: Response from API
        aminer_id: Scholar's AMiner ID
        data_source: Data source identifier

    Returns:
        Dictionary in AMiner format
    """
    data = api_response.get("data", {})

    # Build detail section (matching official AMiner format)
    detail = {
        "id": data.get("id", aminer_id),
        "name": data.get("name", ""),
        "name_zh": data.get("name_zh", ""),
        "bio": data.get("bio", ""),
        "bio_zh": data.get("bio_zh", ""),
        "edu": data.get("edu", ""),
        "edu_zh": data.get("edu_zh", ""),
        "position": data.get("position", ""),
        "position_zh": data.get("position_zh", ""),
        "orgs": data.get("orgs", []),
        "org_zhs": data.get("org_zhs", []),
        "honor": data.get("honor", []),
    }

    # Build AMiner format structure
    aminer_data = {
        "aminer_id": aminer_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": data_source,
        "detail": detail,
    }

    return aminer_data


def convert_api_to_enriched_format(api_response: dict, aminer_id: str, data_source: str) -> dict:
    """
    Convert API response to enriched format for data/enriched/scholars.

    Args:
        api_response: Response from API
        aminer_id: Scholar's AMiner ID
        data_source: Data source identifier

    Returns:
        Dictionary in enriched format
    """
    enriched = api_response.get("enriched", {})

    # Build enriched data structure
    enriched_data = {
        "aminer_id": aminer_id,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": data_source,
    }

    # Add all enriched fields
    enriched_data.update(enriched)

    return enriched_data


def merge_enriched_data(existing_data: dict, new_data: dict) -> tuple[dict, bool]:
    """
    Merge existing enriched data with new data from API.

    Strategy:
    - Keep all existing fields that are not in new_data
    - Update AMiner-related fields with new values
    - Preserve manually added fields (like email)

    Args:
        existing_data: Existing enriched data
        new_data: New enriched data from API

    Returns:
        Tuple of (merged_data, has_changes)
        - merged_data: Merged enriched data
        - has_changes: True if any meaningful field was actually updated
    """
    # Start with existing data
    merged = existing_data.copy()

    # Track if we have any actual changes
    has_changes = False

    # Fields to ignore when checking for changes
    ignore_fields = {"last_updated", "source"}

    # Fields to preserve from existing data
    preserve_fields = {"email"}

    # Update with new data (this will overwrite overlapping keys)
    for key, new_value in new_data.items():
        if key in ignore_fields:
            # Always update these fields
            merged[key] = new_value
        elif key in preserve_fields:
            # Preserve from existing if it exists and is not empty
            if key in existing_data and existing_data[key]:
                merged[key] = existing_data[key]
            else:
                merged[key] = new_value
                if new_value:  # Only count as change if new value is not empty
                    has_changes = True
        else:
            # Check if value actually changed
            existing_value = existing_data.get(key)
            if existing_value != new_value:
                has_changes = True
            merged[key] = new_value

    # Check for new fields that didn't exist before
    for key in new_data:
        if key not in existing_data and key not in ignore_fields:
            has_changes = True
            break

    return merged, has_changes


def process_single_scholar(
    aminer_id: str,
    aminer_dir: Path,
    enriched_dir: Path,
    api_base_url: str,
    authorization: str,
    signature: str,
    timestamp: str,
    data_source: str,
    force: bool = False,
    force_refresh: bool = False,
    update_existing: bool = False,
    verbose: bool = False
) -> tuple[Optional[dict], Optional[dict], str]:
    """
    Process a single scholar and enrich with AMiner data.

    Args:
        aminer_id: Scholar's AMiner ID
        aminer_dir: Directory for AMiner cache files
        enriched_dir: Directory for enriched data files
        api_base_url: Base URL of the API
        authorization: Authorization token
        signature: X-Signature value
        timestamp: X-Timestamp value
        data_source: Data source identifier
        force: Force refresh even if cache exists (completely overwrite)
        force_refresh: Force refresh API cache
        update_existing: Update existing cache with merge (preserves extra fields like email)
        verbose: Whether to print detailed progress

    Returns:
        Tuple of (aminer_data, enriched_data, status, error_msg)
        - status can be: "cache_hit", "api_success", "api_updated", "api_no_change", "api_failed"
        - error_msg is None unless status is "api_failed"
    """
    # Ensure output directories exist
    aminer_dir.mkdir(parents=True, exist_ok=True)
    enriched_dir.mkdir(parents=True, exist_ok=True)

    # Load existing enriched data if available (for merge mode)
    enriched_file = enriched_dir / f"{aminer_id}.json"
    existing_enriched_data = None
    if enriched_file.exists():
        existing_enriched_data = load_json_file(enriched_file)

    # Check cache first
    cached_data = None
    if not force and not update_existing:
        cached_data = load_cached_scholar_data(aminer_dir, enriched_dir, aminer_id)
        if cached_data:
            aminer_data, enriched_data = cached_data
            if verbose:
                print(f"       {Colors.DIM}Using cached scholar data{Colors.ENDC}")
            return (aminer_data, enriched_data, "cache_hit", None)

    # Fetch from API if no cache, force refresh, or update_existing mode
    if verbose:
        if update_existing and existing_enriched_data:
            print(f"       {Colors.CYAN}Updating existing data from API{Colors.ENDC}")
        else:
            print(f"       {Colors.CYAN}Fetching from API{Colors.ENDC}")

    api_response, error_msg = fetch_scholar_from_api(
        aminer_id,
        api_base_url,
        authorization,
        signature,
        timestamp,
        force_refresh,
        verbose
    )

    # Retry with force_refresh if failed (may be due to stale cache)
    if not api_response and error_msg:
        # Always show retry message with sleep duration
        print(f"       {Colors.YELLOW}Initial fetch failed, retrying with force_refresh in 10s...{Colors.ENDC}", flush=True)
        if verbose:
            print(f"       {Colors.DIM}Error: {error_msg}{Colors.ENDC}")

        time.sleep(10)  # Wait before retry

        # Show that we're now retrying
        print(f"       {Colors.CYAN}Retrying now with force_refresh=true...{Colors.ENDC}", flush=True)

        api_response, retry_error_msg = fetch_scholar_from_api(
            aminer_id,
            api_base_url,
            authorization,
            signature,
            timestamp,
            force_refresh=True,  # Force refresh on retry
            verbose=verbose
        )

        if not api_response:
            # Update error message with retry info
            error_msg = f"{error_msg} (retry also failed: {retry_error_msg})"

    if api_response:
        # Convert to AMiner format
        aminer_data = convert_api_to_aminer_format(api_response, aminer_id, data_source)
        save_json_file(aminer_dir / f"{aminer_id}.json", aminer_data)
        if verbose:
            print(f"       {Colors.GREEN}✓{Colors.ENDC} Saved AMiner data")

        # Convert to enriched format
        new_enriched_data = convert_api_to_enriched_format(api_response, aminer_id, data_source)

        # Merge with existing data if in update mode and existing data exists
        if update_existing and existing_enriched_data:
            enriched_data, has_changes = merge_enriched_data(existing_enriched_data, new_enriched_data)
            if verbose:
                if has_changes:
                    print(f"       {Colors.CYAN}↻{Colors.ENDC} Merged with existing data (changes detected)")
                else:
                    print(f"       {Colors.DIM}↻{Colors.ENDC} Merged with existing data (no changes)")
            # Only mark as updated if there were actual changes
            status = "api_updated" if has_changes else "api_no_change"
        else:
            enriched_data = new_enriched_data
            status = "api_success"

        save_json_file(enriched_dir / f"{aminer_id}.json", enriched_data)
        if verbose:
            print(f"       {Colors.GREEN}✓{Colors.ENDC} Saved enriched data")

        return (aminer_data, enriched_data, status, None)
    else:
        if verbose:
            print(f"       {Colors.RED}[FAILED]{Colors.ENDC} Could not fetch scholar data")
        return (None, None, "api_failed", error_msg)


def print_processing_summary(stats: dict, title: str = "Enrichment Summary") -> None:
    """
    Print processing summary with statistics.

    Args:
        stats: Dictionary containing processing statistics
        title: Title for the summary section
    """
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}{title}{Colors.ENDC}")
    print("=" * 60)
    print(f"Total scholars:     {stats.get('total', 0)}")

    # Show skipped if it exists
    if stats.get('skipped', 0) > 0:
        print(f"Skipped:            {Colors.YELLOW}{stats.get('skipped', 0)}{Colors.ENDC}")

    print(f"Processed:          {stats.get('processed', 0)}")
    print(f"  - Cache hit:      {Colors.GREEN}{stats.get('cache_hit', 0)}{Colors.ENDC}")
    print(f"  - API calls:      {Colors.CYAN}{stats.get('api_call', 0)}{Colors.ENDC}")

    # Show api_updated if it exists
    if stats.get('api_updated', 0) > 0:
        print(f"    - Updated:      {Colors.CYAN}{stats.get('api_updated', 0)}{Colors.ENDC}")

    print(f"  - Success:        {Colors.GREEN}{stats.get('success', 0)}{Colors.ENDC}")
    print(f"  - Failed:         {Colors.RED}{stats.get('failed', 0)}{Colors.ENDC}")

    if stats.get("failed_ids"):
        print(f"\n{Colors.RED}Failed AMiner IDs:{Colors.ENDC}")
        for aminer_id in stats["failed_ids"]:
            print(f"  - {aminer_id}")
