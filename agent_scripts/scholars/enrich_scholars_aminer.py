#!/usr/bin/env python3
"""
Enrich scholars with AMiner data from scholars.json or authors.json.

This script reads a JSON file containing scholar information (scholars.json or
authors.json), fetches detailed scholar data via data-proxy API, and optionally
generates an enriched output file.

The script supports two input formats:
- scholars.json: expects top-level key 'talents' with items containing 'aminer_id'
- authors.json: expects top-level key 'authors' with items containing 'aminer_id'

The script reuses existing scholar cache in data/aminer/scholars/ and
data/enriched/scholars/ to avoid redundant API calls.

Usage:
    python enrich_scholars_aminer.py [options]

Example:
    # Basic usage with default file (authors.json) and environment variables for credentials
    export AMINER_AUTH="Bearer xxx"
    export AMINER_SIGNATURE="xxx"
    export AMINER_TIMESTAMP="xxx"
    python enrich_scholars_aminer.py

    # Specify a different JSON file
    python enrich_scholars_aminer.py --json-file ../../data/aaai-26/scholars.json

    # With command line credentials
    python enrich_scholars_aminer.py --json-file ../../data/aaai-26/authors.json \
        --authorization "Bearer xxx" \
        --signature "xxx" \
        --timestamp "xxx"

    # Force refresh all scholars (ignore cache)
    python enrich_scholars_aminer.py --json-file ../../data/aaai-26/scholars.json --force

    # Update existing scholars (merge with cache, preserve fields like email)
    python enrich_scholars_aminer.py --json-file ../../data/aaai-26/scholars.json --update-existing

    # Process only specific AMiner IDs
    python enrich_scholars_aminer.py --ids 53f49b5ddabfaebbd777bc95 5608b82645cedb3396d4ba82

    # Custom output path
    python enrich_scholars_aminer.py --json-file ../../data/aaai-26/scholars.json \
        -o ../../data/aaai-26/scholars_enriched.json
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

# Add current directory to path for aminer_scholar_utils
sys.path.insert(0, str(Path(__file__).parent))
from aminer_scholar_utils import (
    DEFAULT_API_BASE_URL,
    get_api_credentials,
    process_single_scholar,
    print_processing_summary,
)

# Add parent directory to path for common_utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from common_utils import Colors, get_project_root, load_json_file, save_json_file


# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
AUTHORS_FILE = PROJECT_ROOT / "data" / "aaai-26" / "authors.json"

# Data source identifier
DATA_SOURCE = "scholars_enrichment_v1"


def load_scholars_from_json(json_path: Path) -> tuple[list[dict], str]:
    """
    Load scholars from JSON file.

    Supports two formats:
    - scholars.json: top-level key 'talents'
    - authors.json: top-level key 'authors'

    Args:
        json_path: Path to the JSON file

    Returns:
        Tuple of (scholars_list, key_name)
        key_name is either "talents" or "authors"
    """
    print(f"Loading scholars from: {json_path}")
    data = load_json_file(json_path)

    # Determine which format we're dealing with
    if "talents" in data:
        scholars = data["talents"]
        key_name = "talents"
        print(f"Found {len(scholars)} scholars in 'talents' field (scholars.json format)\n")
    elif "authors" in data:
        scholars = data["authors"]
        key_name = "authors"
        print(f"Found {len(scholars)} scholars in 'authors' field (authors.json format)\n")
    else:
        print(f"{Colors.RED}Error: JSON file must contain 'talents' or 'authors' key{Colors.ENDC}")
        sys.exit(1)

    return scholars, key_name


def process_scholars(
    scholars: list[dict],
    aminer_dir: Path,
    enriched_dir: Path,
    api_base_url: str,
    authorization: str,
    signature: str,
    timestamp: str,
    force: bool = False,
    delay: float = 5.0,
    force_refresh: bool = False,
    update_existing: bool = False,
    verbose: bool = False
) -> tuple[list[dict], dict]:
    """
    Process all scholars and enrich with AMiner data.

    Args:
        scholars: List of scholar dictionaries
        aminer_dir: Directory for AMiner cache files
        enriched_dir: Directory for enriched data files
        api_base_url: Base URL of the API
        authorization: Authorization token
        signature: X-Signature value
        timestamp: X-Timestamp value
        force: Force refresh even if cache exists
        delay: Delay between API requests in seconds
        force_refresh: Force refresh API cache
        update_existing: Update existing cache with merge (preserves extra fields like email)
        verbose: Whether to print detailed progress

    Returns:
        Tuple of (enriched_scholars_list, statistics)
    """
    # Track statistics
    stats = {
        "total": len(scholars),
        "processed": 0,
        "skipped": 0,
        "cache_hit": 0,
        "api_call": 0,
        "api_updated": 0,
        "success": 0,
        "failed": 0,
        "failed_ids": []
    }

    enriched_scholars = []

    for idx, scholar in enumerate(scholars, 1):
        aminer_id = scholar.get("aminer_id")
        name = scholar.get("name", "Unknown")

        # Check for invalid or missing AMiner IDs
        if not aminer_id or aminer_id == "failed" or aminer_id.strip() == "":
            reason = "no AMiner ID" if not aminer_id or aminer_id.strip() == "" else "invalid AMiner ID"
            print(f"[{idx}/{stats['total']}] {Colors.YELLOW}Skipped{Colors.ENDC} {name} ({reason})")
            stats["skipped"] += 1
            # Keep original scholar data without enrichment
            enriched_scholars.append(scholar.copy())
            continue

        print(f"[{idx}/{stats['total']}] {Colors.CYAN}Processing{Colors.ENDC} {name} ({aminer_id})")

        # Process the scholar
        aminer_data, enriched_data, status, error_msg = process_single_scholar(
            aminer_id=aminer_id,
            aminer_dir=aminer_dir,
            enriched_dir=enriched_dir,
            api_base_url=api_base_url,
            authorization=authorization,
            signature=signature,
            timestamp=timestamp,
            data_source=DATA_SOURCE,
            force=force,
            force_refresh=force_refresh,
            update_existing=update_existing,
            verbose=verbose
        )

        # Update statistics
        if status == "cache_hit":
            stats["cache_hit"] += 1
            print(f"       {Colors.DIM}Cache hit{Colors.ENDC}")
        elif status == "api_success":
            stats["api_call"] += 1
            print(f"       {Colors.GREEN}[SUCCESS]{Colors.ENDC}")
        elif status == "api_updated":
            stats["api_call"] += 1
            stats["api_updated"] += 1
            print(f"       {Colors.CYAN}[UPDATED]{Colors.ENDC}")
        elif status == "api_no_change":
            stats["api_call"] += 1
            print(f"       {Colors.DIM}No changes{Colors.ENDC}")
        elif status == "api_failed":
            stats["api_call"] += 1
            stats["failed"] += 1
            stats["failed_ids"].append(aminer_id)
            stats["processed"] += 1
            error_display = f": {error_msg}" if error_msg else ""
            print(f"       {Colors.RED}[FAILED]{Colors.ENDC} API call failed{error_display}")
            # Keep original scholar data on failure
            enriched_scholars.append(scholar.copy())
            continue

        # Build enriched scholar entry
        detail = aminer_data.get("detail", {}) if aminer_data else {}
        enriched = enriched_data if isinstance(enriched_data, dict) else {}

        # Start with original scholar data
        enriched_scholar = scholar.copy()

        # Add AMiner detail fields
        if detail:
            enriched_scholar["aminer_name"] = detail.get("name", name)
            enriched_scholar["aminer_name_zh"] = detail.get("name_zh", "")
            enriched_scholar["bio"] = detail.get("bio", "")
            enriched_scholar["bio_zh"] = detail.get("bio_zh", "")
            enriched_scholar["edu"] = detail.get("edu", "")
            enriched_scholar["edu_zh"] = detail.get("edu_zh", "")
            enriched_scholar["position"] = detail.get("position", "")
            enriched_scholar["position_zh"] = detail.get("position_zh", "")
            enriched_scholar["orgs"] = detail.get("orgs", [])
            enriched_scholar["org_zhs"] = detail.get("org_zhs", [])
            enriched_scholar["honor"] = detail.get("honor", [])

        # Add enriched fields (indices, etc.)
        if enriched:
            indices = enriched.get("indices", {})
            enriched_scholar["h_index"] = indices.get("hindex")
            enriched_scholar["n_citation"] = indices.get("citations")
            enriched_scholar["n_pubs"] = indices.get("pubs")
            enriched_scholar["email"] = enriched.get("email", "")

        enriched_scholars.append(enriched_scholar)
        stats["success"] += 1
        stats["processed"] += 1

        # Rate limiting
        if idx < stats["total"] and delay > 0 and stats["api_call"] > 0:
            time.sleep(delay)

    return enriched_scholars, stats


def main():
    parser = argparse.ArgumentParser(
        description="Enrich scholars with AMiner data from scholars.json or authors.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--ids",
        nargs="+",
        help="Specific AMiner IDs to process (for testing or selective updates)"
    )

    parser.add_argument(
        "--json-file",
        type=str,
        default=str(AUTHORS_FILE),
        help=f"JSON file containing scholars (default: {AUTHORS_FILE})"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output path for enriched JSON (optional, default: no output file)"
    )

    parser.add_argument(
        "--api-url",
        type=str,
        default=DEFAULT_API_BASE_URL,
        help=f"Base URL of the data-proxy API (default: {DEFAULT_API_BASE_URL})"
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
        "--force",
        action="store_true",
        help="Force refresh even if cache exists (completely overwrite)"
    )

    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update existing cache with merge (preserves extra fields like email)"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between API requests in seconds (default: 2.0)"
    )

    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh API cache (bypass 15-day cache)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress for each API call"
    )

    args = parser.parse_args()

    # Resolve file path
    json_path = Path(args.json_file).resolve()
    if not json_path.exists():
        print(f"{Colors.RED}Error: File not found: {json_path}{Colors.ENDC}")
        sys.exit(1)

    # Determine output path
    output_path = None
    if args.output:
        output_path = Path(args.output).resolve()

    # Get credentials
    authorization = args.authorization
    signature = args.signature
    timestamp = args.timestamp

    # Clean up command line arguments
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
        print(f"{Colors.RED}Error: Missing authorization token{Colors.ENDC}")
        print("  Provide via --authorization or set AMINER_AUTH environment variable")
        sys.exit(1)
    if not signature:
        print(f"{Colors.RED}Error: Missing signature{Colors.ENDC}")
        print("  Provide via --signature or set AMINER_SIGNATURE environment variable")
        sys.exit(1)
    if not timestamp:
        print(f"{Colors.RED}Error: Missing timestamp{Colors.ENDC}")
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
    print(f"{Colors.BOLD}Enrich Scholars with AMiner Data{Colors.ENDC}")
    print("=" * 60)
    print(f"Input JSON: {json_path}")
    if output_path:
        print(f"Output: {output_path}")
    else:
        print(f"Output: {Colors.DIM}(no output file){Colors.ENDC}")
    print(f"API URL: {args.api_url}")
    print(f"AMiner directory: {aminer_dir}")
    print(f"Enriched directory: {enriched_dir}")
    print(f"Force refresh: {args.force}")
    print(f"Update existing: {args.update_existing}")
    print(f"Delay: {args.delay}s")
    print()

    # Load scholars from JSON
    scholars, key_name = load_scholars_from_json(json_path)

    if not scholars:
        print(f"{Colors.YELLOW}No scholars found{Colors.ENDC}")
        sys.exit(0)

    # Filter by specific IDs if provided
    if args.ids:
        ids_set = set(args.ids)
        original_count = len(scholars)
        scholars = [s for s in scholars if s.get("aminer_id") in ids_set]
        print(f"Filtered to {len(scholars)} scholars (from {original_count} total) matching specified IDs")
        print(f"Specified IDs: {', '.join(args.ids)}")
        print()

        if not scholars:
            print(f"{Colors.YELLOW}No matching scholars found for the specified IDs{Colors.ENDC}")
            sys.exit(0)

    # Process scholars
    enriched_scholars, stats = process_scholars(
        scholars=scholars,
        aminer_dir=aminer_dir,
        enriched_dir=enriched_dir,
        api_base_url=args.api_url,
        authorization=authorization,
        signature=signature,
        timestamp=timestamp,
        force=args.force,
        delay=args.delay,
        force_refresh=args.force_refresh,
        update_existing=args.update_existing,
        verbose=args.verbose
    )

    # Generate output file if requested
    if output_path:
        # Load original metadata
        original_data = load_json_file(json_path)
        metadata = original_data.get("metadata", {})

        # Build output data with same structure as input
        output_data = {
            "metadata": metadata,
            key_name: enriched_scholars
        }

        print(f"\n{Colors.CYAN}Saving enriched data...{Colors.ENDC}")
        save_json_file(output_path, output_data)
        print(f"{Colors.GREEN}Saved to: {output_path}{Colors.ENDC}")

    # Print summary
    print_processing_summary(stats)


if __name__ == "__main__":
    main()
