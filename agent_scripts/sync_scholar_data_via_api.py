#!/usr/bin/env python3
"""
Sync scholar data using local AMiner API with caching.

This script fetches scholar details from the local AMiner API endpoint
(which wraps the AMiner web API with 15-day caching) and updates both
data/aminer/scholars and data/enriched/scholars directories.

Usage:
    python sync_scholar_data_via_api.py <json_file_path> [options]

Example:
    # Basic usage with credentials
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json \\
        --authorization "Bearer xxx" \\
        --signature "xxx" \\
        --timestamp "xxx"

    # Using environment variables
    export AMINER_AUTH="Bearer xxx"
    export AMINER_SIGNATURE="xxx"
    export AMINER_TIMESTAMP="xxx"
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json

    # Update mode with custom delay
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json \\
        --mode update --delay 1.5

    # Process specific scholars
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json \\
        --ids 53f466dfdabfaedd74e6b9e2 548e3181dabfaef989f09226
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from common_utils import (
    Colors,
    get_project_root,
    load_json_file,
    save_json_file,
    get_validated_scholars,
    archive_file,
    merge_dicts,
    print_progress,
)


# API Configuration
DEFAULT_API_BASE_URL = "http://localhost:37801"
API_ENDPOINT = "/api/aminer/scholar/detail"

# Data source identifier
DATA_SOURCE = "local_api_v1"


def get_api_credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Get API credentials from environment variables.
    Cleans up any whitespace, newlines, or invalid characters.

    Returns:
        Tuple of (authorization, signature, timestamp)
    """
    authorization = os.environ.get("AMINER_AUTH")
    signature = os.environ.get("AMINER_SIGNATURE")
    timestamp = os.environ.get("AMINER_TIMESTAMP")

    # Clean up credentials (remove newlines, leading/trailing whitespace)
    if authorization:
        authorization = authorization.strip().replace('\n', '').replace('\r', '')
    if signature:
        signature = signature.strip().replace('\n', '').replace('\r', '')
    if timestamp:
        timestamp = timestamp.strip().replace('\n', '').replace('\r', '')

    return authorization, signature, timestamp


def fetch_scholar_from_api(
    aminer_id: str,
    api_base_url: str,
    authorization: str,
    signature: str,
    timestamp: str,
    force_refresh: bool = False,
    retry: bool = True,
    retry_delay: int = 10,
) -> dict:
    """
    Fetch scholar data from local API with retry support.

    Args:
        aminer_id: Scholar's AMiner ID
        api_base_url: Base URL of the API
        authorization: Authorization token
        signature: X-Signature header value
        timestamp: X-Timestamp header value
        force_refresh: Force refresh cache
        retry: Whether to retry on failure
        retry_delay: Delay in seconds before retry

    Returns:
        API response containing data and enriched fields

    Raises:
        requests.RequestException: If API call fails after retry
    """
    url = f"{api_base_url}{API_ENDPOINT}"

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
        return response.json()
    except requests.RequestException as e:
        if not retry:
            raise

        # First attempt failed, retry after delay
        print(f"       {Colors.YELLOW}⚠ API request failed, retrying in {retry_delay}s...{Colors.ENDC}")
        print(f"       {Colors.DIM}Error: {str(e)}{Colors.ENDC}")
        time.sleep(retry_delay)

        # Retry once
        print(f"       {Colors.CYAN}↻ Retrying...{Colors.ENDC}")
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        return response.json()


def convert_api_to_aminer_format(api_response: dict, aminer_id: str) -> dict:
    """
    Convert API response to AMiner JSON format for data/aminer/scholars.

    Args:
        api_response: Response from API
        aminer_id: Scholar's AMiner ID

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
        "source": DATA_SOURCE,  # Mark data source
        "detail": detail,
    }

    return aminer_data


def convert_api_to_enriched_format(api_response: dict, aminer_id: str) -> dict:
    """
    Convert API response to enriched format for data/enriched/scholars.

    Args:
        api_response: Response from API
        aminer_id: Scholar's AMiner ID

    Returns:
        Dictionary in enriched format
    """
    enriched = api_response.get("enriched", {})

    # Build enriched data structure
    enriched_data = {
        "aminer_id": aminer_id,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": DATA_SOURCE,  # Mark data source
    }

    # Add all enriched fields
    enriched_data.update(enriched)

    return enriched_data


def process_scholars(
    json_file_path: Path,
    aminer_dir: Path,
    enriched_dir: Path,
    api_base_url: str,
    authorization: str,
    signature: str,
    timestamp: str,
    mode: str = "skip",
    delay: float = 2.0,
    force_refresh: bool = False,
    target_ids: list[str] | None = None,
    retry_delay: int = 10,
) -> dict:
    """
    Process all validated scholars and sync their data.

    Args:
        json_file_path: Path to JSON file with scholar information
        aminer_dir: Directory for AMiner cache files
        enriched_dir: Directory for enriched data files
        api_base_url: Base URL of the API
        authorization: Authorization token
        signature: X-Signature value
        timestamp: X-Timestamp value
        mode: Processing mode - "skip", "update", or "overwrite"
        delay: Delay between API requests in seconds
        force_refresh: Force refresh API cache
        target_ids: Optional list of specific AMiner IDs to process
        retry_delay: Delay in seconds before retrying failed API requests

    Returns:
        Statistics dictionary with processing results
    """
    # Load the JSON file
    print(f"Loading JSON file: {json_file_path}")
    data = load_json_file(json_file_path)

    # Get validated scholars
    scholars = get_validated_scholars(data)
    print(f"Found {len(scholars)} scholars with validated AMiner IDs")

    # Filter by target IDs if specified
    if target_ids:
        scholars = [s for s in scholars if s.get("aminer_id") in target_ids]
        print(f"Filtered to {len(scholars)} scholars matching target IDs")

    # Ensure output directories exist
    aminer_dir.mkdir(parents=True, exist_ok=True)
    enriched_dir.mkdir(parents=True, exist_ok=True)

    # Track statistics
    stats = {
        "total": len(scholars),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "failed": 0,
        "errors": []  # List of (aminer_id, name, error_message)
    }

    for idx, scholar in enumerate(scholars, 1):
        name = scholar.get("name", "Unknown")
        aminer_id = scholar.get("aminer_id")
        aminer_file = aminer_dir / f"{aminer_id}.json"
        enriched_file = enriched_dir / f"{aminer_id}.json"

        # Check if files exist
        aminer_exists = aminer_file.exists()
        enriched_exists = enriched_file.exists()

        if mode == "skip" and aminer_exists and enriched_exists:
            print_progress(
                idx, stats["total"], name, "Skipped",
                f"({aminer_id}) - files exist",
                Colors.DIM
            )
            stats["skipped"] += 1
            continue

        # Archive existing files if in overwrite mode
        if mode == "overwrite":
            if aminer_exists:
                archive_path = archive_file(aminer_file)
                print(f"       Archived AMiner file to: {archive_path.name}")
            if enriched_exists:
                archive_path = archive_file(enriched_file)
                print(f"       Archived enriched file to: {archive_path.name}")

        print_progress(
            idx, stats["total"], name, "Syncing",
            f"({aminer_id})",
            Colors.CYAN
        )

        try:
            # Fetch from API
            api_response = fetch_scholar_from_api(
                aminer_id,
                api_base_url,
                authorization,
                signature,
                timestamp,
                force_refresh,
                retry=True,
                retry_delay=retry_delay,
            )

            # Check API response
            if not api_response.get("success"):
                raise Exception(f"API returned success=false: {api_response.get('msg')}")

            # Convert to AMiner format
            aminer_data = convert_api_to_aminer_format(api_response, aminer_id)

            # Handle update mode for AMiner data
            if mode == "update" and aminer_exists:
                existing_aminer = load_json_file(aminer_file)
                # Merge: keep existing data, update detail section
                aminer_data = merge_dicts(existing_aminer, aminer_data, overwrite=True)

            # Save AMiner data
            save_json_file(aminer_file, aminer_data)
            print(f"       {Colors.GREEN}✓{Colors.ENDC} Saved AMiner data")

            # Convert to enriched format
            enriched_data = convert_api_to_enriched_format(api_response, aminer_id)

            # Handle update mode for enriched data
            if mode == "update" and enriched_exists:
                existing_enriched = load_json_file(enriched_file)
                # Merge: keep existing data, add new fields
                enriched_data = merge_dicts(existing_enriched, enriched_data, overwrite=False)

            # Save enriched data
            save_json_file(enriched_file, enriched_data)
            print(f"       {Colors.GREEN}✓{Colors.ENDC} Saved enriched data")

            stats["success"] += 1
            stats["processed"] += 1

        except requests.RequestException as e:
            # API call failed after retry
            error_msg = f"API request failed after retry: {str(e)}"
            print(f"       {Colors.RED}✗ {error_msg}{Colors.ENDC}")
            print(f"\n{Colors.RED}Fatal error: Stopping script due to API error.{Colors.ENDC}")
            print(f"Error details: {error_msg}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"HTTP Status: {e.response.status_code}")
                print(f"Response: {e.response.text[:500]}")
            stats["failed"] += 1
            stats["errors"].append((aminer_id, name, error_msg))
            # Stop processing and return stats immediately
            return stats

        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            print(f"       {Colors.RED}✗ {error_msg}{Colors.ENDC}")
            print(f"\n{Colors.RED}Fatal error: Stopping script due to processing error.{Colors.ENDC}")
            print(f"Error details: {error_msg}")
            stats["failed"] += 1
            stats["errors"].append((aminer_id, name, error_msg))
            # Stop processing and return stats immediately
            return stats

        # Rate limiting delay
        if idx < stats["total"] and delay > 0:
            time.sleep(delay)

    return stats


def print_summary(stats: dict) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Sync Summary{Colors.ENDC}")
    print("=" * 60)
    print(f"Total scholars:     {stats['total']}")
    print(f"Skipped:            {stats['skipped']}")
    print(f"Processed:          {stats['processed']}")
    print(f"  - Success:        {Colors.GREEN}{stats['success']}{Colors.ENDC}")
    print(f"  - Failed:         {Colors.RED}{stats['failed']}{Colors.ENDC}")

    if stats["errors"]:
        print(f"\n{Colors.RED}Errors (script stopped on first error):{Colors.ENDC}")
        for aminer_id, name, error_msg in stats["errors"]:
            print(f"  - {name} ({aminer_id}): {error_msg}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync scholar data using local AMiner API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # With credentials in arguments
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json \\
        --authorization "Bearer xxx" --signature "xxx" --timestamp "xxx"

    # Using environment variables
    export AMINER_AUTH="Bearer xxx"
    export AMINER_SIGNATURE="xxx"
    export AMINER_TIMESTAMP="xxx"
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json

    # Update mode (preserve existing data)
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json --mode update

    # Specific scholars
    python sync_scholar_data_via_api.py ../data/aaai-26-ai-talents.json \\
        --ids 53f466dfdabfaedd74e6b9e2
        """
    )

    parser.add_argument(
        "json_file",
        type=str,
        help="Path to the JSON file containing scholar information"
    )

    parser.add_argument(
        "--api-url",
        type=str,
        default=DEFAULT_API_BASE_URL,
        help=f"Base URL of the API (default: {DEFAULT_API_BASE_URL})"
    )

    parser.add_argument(
        "--authorization",
        type=str,
        help="Authorization token (or set AMINER_AUTH env var)"
    )

    parser.add_argument(
        "--signature",
        type=str,
        help="X-Signature value (or set AMINER_SIGNATURE env var)"
    )

    parser.add_argument(
        "--timestamp",
        type=str,
        help="X-Timestamp value (or set AMINER_TIMESTAMP env var)"
    )

    parser.add_argument(
        "--aminer-dir",
        type=str,
        default=None,
        help="Directory for AMiner cache files (default: data/aminer/scholars)"
    )

    parser.add_argument(
        "--enriched-dir",
        type=str,
        default=None,
        help="Directory for enriched data files (default: data/enriched/scholars)"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["skip", "update", "overwrite"],
        default="skip",
        help="Processing mode: skip existing (default), update (merge), or overwrite"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between API requests in seconds (default: 2.0)"
    )

    parser.add_argument(
        "--retry-delay",
        type=int,
        default=10,
        help="Delay before retrying failed API requests in seconds (default: 10)"
    )

    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh API cache (bypass 15-day cache)"
    )

    parser.add_argument(
        "--ids",
        nargs="+",
        dest="target_ids",
        help="Only process specific AMiner IDs"
    )

    args = parser.parse_args()

    # Resolve file path
    json_file_path = Path(args.json_file).resolve()
    if not json_file_path.exists():
        print(f"Error: File not found: {json_file_path}")
        sys.exit(1)

    # Get credentials
    authorization = args.authorization
    signature = args.signature
    timestamp = args.timestamp

    # Clean up command line arguments (remove newlines, whitespace)
    if authorization:
        authorization = authorization.strip().replace('\n', '').replace('\r', '')
    if signature:
        signature = signature.strip().replace('\n', '').replace('\r', '')
    if timestamp:
        timestamp = timestamp.strip().replace('\n', '').replace('\r', '')

    # Fall back to environment variables
    if not authorization or not signature or not timestamp:
        env_auth, env_sig, env_ts = get_api_credentials()
        authorization = authorization or env_auth
        signature = signature or env_sig
        timestamp = timestamp or env_ts

    # Validate credentials
    if not authorization:
        print("Error: Missing authorization token")
        print("  Provide via --authorization or set AMINER_AUTH environment variable")
        sys.exit(1)
    if not signature:
        print("Error: Missing signature")
        print("  Provide via --signature or set AMINER_SIGNATURE environment variable")
        sys.exit(1)
    if not timestamp:
        print("Error: Missing timestamp")
        print("  Provide via --timestamp or set AMINER_TIMESTAMP environment variable")
        sys.exit(1)

    # Determine directories
    project_root = get_project_root()
    if args.aminer_dir:
        aminer_dir = Path(args.aminer_dir).resolve()
    else:
        aminer_dir = project_root / "data" / "aminer" / "scholars"

    if args.enriched_dir:
        enriched_dir = Path(args.enriched_dir).resolve()
    else:
        enriched_dir = project_root / "data" / "enriched" / "scholars"

    # Print configuration
    print("=" * 60)
    print(f"{Colors.BOLD}Sync Scholar Data via Local API{Colors.ENDC}")
    print("=" * 60)
    print(f"API URL: {args.api_url}")
    print(f"AMiner directory: {aminer_dir}")
    print(f"Enriched directory: {enriched_dir}")
    print(f"Mode: {args.mode}")
    print(f"Delay: {args.delay}s")
    print(f"Retry delay: {args.retry_delay}s")
    print(f"Force refresh: {args.force_refresh}")
    if args.target_ids:
        print(f"Target IDs: {len(args.target_ids)} specified")
    print()

    # Process scholars
    stats = process_scholars(
        json_file_path=json_file_path,
        aminer_dir=aminer_dir,
        enriched_dir=enriched_dir,
        api_base_url=args.api_url,
        authorization=authorization,
        signature=signature,
        timestamp=timestamp,
        mode=args.mode,
        delay=args.delay,
        force_refresh=args.force_refresh,
        target_ids=args.target_ids,
        retry_delay=args.retry_delay,
    )

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
