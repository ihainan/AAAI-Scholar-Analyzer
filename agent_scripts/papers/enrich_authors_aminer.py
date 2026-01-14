#!/usr/bin/env python3
"""
Extract authors from papers.json and enrich with AMiner data.

This script reads papers.json, extracts authors that have AMiner IDs from the
cached paper details, fetches detailed scholar data via data-proxy API, and
generates an authors.json file.

Only authors that have AMiner IDs in the paper details are processed. Authors
without AMiner IDs are skipped.

The script reuses existing scholar cache in data/aminer/scholars/ and
data/enriched/scholars/ to avoid redundant API calls.

Usage:
    python enrich_authors_aminer.py <papers_json_path> [options]

Example:
    # Basic usage with environment variables for credentials
    export AMINER_AUTH="Bearer xxx"
    export AMINER_SIGNATURE="xxx"
    export AMINER_TIMESTAMP="xxx"
    python enrich_authors_aminer.py ../../data/aaai-26/papers.json

    # With command line credentials
    python enrich_authors_aminer.py ../../data/aaai-26/papers.json \
        --authorization "Bearer xxx" \
        --signature "xxx" \
        --timestamp "xxx"

    # Force refresh all authors (ignore cache)
    python enrich_authors_aminer.py ../../data/aaai-26/papers.json --force

    # Custom output path
    python enrich_authors_aminer.py ../../data/aaai-26/papers.json -o ../../data/aaai-26/authors.json
"""

import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# Add parent directory to path for common_utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from common_utils import (
    Colors,
    get_project_root,
    load_json_file,
    save_json_file,
)


# API Configuration
DEFAULT_API_BASE_URL = "http://localhost:37804"
SCHOLAR_DETAIL_ENDPOINT = "/api/aminer/scholar/detail"

# Data source identifier
DATA_SOURCE = "papers_enrichment_v1"


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
) -> Optional[dict]:
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
        API response or None if failed
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
            return result
        else:
            error_msg = result.get("msg", "Unknown error")
            if verbose:
                print(f" {Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
            return None
    except Exception as e:
        if verbose:
            print(f" {Colors.RED}ERROR{Colors.ENDC} ({str(e)})")
        return None


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
        "source": DATA_SOURCE,
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
        "source": DATA_SOURCE,
    }

    # Add all enriched fields
    enriched_data.update(enriched)

    return enriched_data


def extract_authors_from_papers(
    papers_json_path: Path,
    papers_cache_dir: Path
) -> dict[str, dict]:
    """
    Extract authors with AMiner IDs from papers.

    Args:
        papers_json_path: Path to papers.json
        papers_cache_dir: Directory with cached paper details

    Returns:
        Dictionary mapping aminer_id to author info (name and paper_ids)
    """
    print(f"Loading papers.json: {papers_json_path}")
    papers_data = load_json_file(papers_json_path)
    papers = papers_data.get("papers", [])
    print(f"Found {len(papers)} papers in the file\n")

    authors_map = defaultdict(lambda: {"name": "", "paper_ids": []})
    papers_with_cache = 0
    papers_without_cache = 0
    total_authors_found = 0

    for idx, paper in enumerate(papers, 1):
        paper_id = paper.get("paper_id", "Unknown")
        aminer_paper_id = paper.get("aminer_paper_id")

        if not aminer_paper_id:
            continue

        # Load paper details from cache
        paper_cache_file = papers_cache_dir / f"{aminer_paper_id}.json"
        if not paper_cache_file.exists():
            papers_without_cache += 1
            continue

        papers_with_cache += 1
        paper_data = load_json_file(paper_cache_file)
        authors = paper_data.get("detail", {}).get("authors", [])

        # Extract authors with AMiner IDs
        for author in authors:
            author_id = author.get("id")
            author_name = author.get("name", "")

            if author_id:  # Only process authors with AMiner ID
                if not authors_map[author_id]["name"]:
                    authors_map[author_id]["name"] = author_name
                    total_authors_found += 1
                authors_map[author_id]["paper_ids"].append(paper_id)

        if idx % 100 == 0:
            print(f"Processed {idx}/{len(papers)} papers, found {total_authors_found} unique authors with AMiner IDs")

    print(f"\nExtraction complete:")
    print(f"  Papers with cache: {papers_with_cache}")
    print(f"  Papers without cache: {papers_without_cache}")
    print(f"  Unique authors with AMiner IDs: {len(authors_map)}\n")

    return dict(authors_map)


def process_authors(
    authors_map: dict[str, dict],
    aminer_dir: Path,
    enriched_dir: Path,
    api_base_url: str,
    authorization: str,
    signature: str,
    timestamp: str,
    force: bool = False,
    delay: float = 2.0,
    force_refresh: bool = False,
    verbose: bool = False
) -> tuple[list[dict], dict]:
    """
    Process all authors and enrich with AMiner data.

    Args:
        authors_map: Dictionary mapping aminer_id to author info
        aminer_dir: Directory for AMiner cache files
        enriched_dir: Directory for enriched data files
        api_base_url: Base URL of the API
        authorization: Authorization token
        signature: X-Signature value
        timestamp: X-Timestamp value
        force: Force refresh even if cache exists
        delay: Delay between API requests in seconds
        force_refresh: Force refresh API cache
        verbose: Whether to print detailed progress

    Returns:
        Tuple of (authors_list, statistics)
    """
    # Ensure output directories exist
    aminer_dir.mkdir(parents=True, exist_ok=True)
    enriched_dir.mkdir(parents=True, exist_ok=True)

    # Track statistics
    stats = {
        "total": len(authors_map),
        "processed": 0,
        "cache_hit": 0,
        "api_call": 0,
        "success": 0,
        "failed": 0,
        "failed_ids": []
    }

    authors_list = []

    for idx, (aminer_id, author_info) in enumerate(authors_map.items(), 1):
        name = author_info["name"]
        paper_ids = author_info["paper_ids"]

        print(f"[{idx}/{stats['total']}] {Colors.CYAN}Processing{Colors.ENDC} {name} ({aminer_id})")
        print(f"       Papers: {len(paper_ids)}")

        # Check cache first
        cached_data = None
        if not force:
            cached_data = load_cached_scholar_data(aminer_dir, enriched_dir, aminer_id)
            if cached_data:
                aminer_data, enriched_data = cached_data
                stats["cache_hit"] += 1
                if verbose:
                    print(f"       {Colors.DIM}Using cached data{Colors.ENDC}")

        # Fetch from API if no cache or force refresh
        if cached_data is None or force:
            stats["api_call"] += 1
            api_response = fetch_scholar_from_api(
                aminer_id,
                api_base_url,
                authorization,
                signature,
                timestamp,
                force_refresh,
                verbose
            )

            if api_response:
                # Convert to AMiner format
                aminer_data = convert_api_to_aminer_format(api_response, aminer_id)
                save_json_file(aminer_dir / f"{aminer_id}.json", aminer_data)
                if verbose:
                    print(f"       {Colors.GREEN}✓{Colors.ENDC} Saved AMiner data")

                # Convert to enriched format
                enriched_data = convert_api_to_enriched_format(api_response, aminer_id)
                save_json_file(enriched_dir / f"{aminer_id}.json", enriched_data)
                if verbose:
                    print(f"       {Colors.GREEN}✓{Colors.ENDC} Saved enriched data")
            else:
                print(f"       {Colors.RED}[FAILED]{Colors.ENDC} Could not fetch scholar data")
                stats["failed"] += 1
                stats["failed_ids"].append(aminer_id)
                stats["processed"] += 1
                continue

        # Build author entry for authors.json
        detail = aminer_data.get("detail", {})
        enriched = enriched_data if isinstance(enriched_data, dict) else {}

        # Extract indices from enriched data (nested under "indices" key)
        indices = enriched.get("indices", {})

        author_entry = {
            "name": name,
            "normalized_name": name.lower(),
            "aminer_id": aminer_id,
            "aminer_name": detail.get("name", name),
            "aminer_name_zh": detail.get("name_zh", ""),
            "papers": sorted(paper_ids),
            "paper_count": len(paper_ids),
            "h_index": indices.get("hindex"),
            "n_citation": indices.get("citations"),
            "n_pubs": indices.get("pubs"),
            "organization": detail.get("orgs", [""])[0] if detail.get("orgs") else "",
            "position": detail.get("position", "")
        }

        authors_list.append(author_entry)
        stats["success"] += 1
        stats["processed"] += 1

        print(f"       {Colors.GREEN}[SUCCESS]{Colors.ENDC}")

        # Rate limiting
        if idx < stats["total"] and delay > 0 and stats["api_call"] > 0:
            time.sleep(delay)

    return authors_list, stats


def print_summary(stats: dict) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Enrichment Summary{Colors.ENDC}")
    print("=" * 60)
    print(f"Total authors:      {stats['total']}")
    print(f"Processed:          {stats['processed']}")
    print(f"  - Cache hit:      {Colors.GREEN}{stats['cache_hit']}{Colors.ENDC}")
    print(f"  - API calls:      {Colors.CYAN}{stats['api_call']}{Colors.ENDC}")
    print(f"  - Success:        {Colors.GREEN}{stats['success']}{Colors.ENDC}")
    print(f"  - Failed:         {Colors.RED}{stats['failed']}{Colors.ENDC}")

    if stats["failed_ids"]:
        print(f"\n{Colors.RED}Failed AMiner IDs:{Colors.ENDC}")
        for aminer_id in stats["failed_ids"]:
            print(f"  - {aminer_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract authors from papers.json and enrich with AMiner data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "papers_json",
        type=str,
        help="Path to the papers.json file"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output path for authors.json (default: same directory as papers.json)"
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
        help="Force refresh even if cache exists"
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
    papers_json_path = Path(args.papers_json).resolve()
    if not papers_json_path.exists():
        print(f"{Colors.RED}Error: File not found: {papers_json_path}{Colors.ENDC}")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = papers_json_path.parent / "authors.json"

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

    papers_cache_dir = project_root / "data" / "aminer" / "papers"

    # Print configuration
    print("=" * 60)
    print(f"{Colors.BOLD}Enrich Authors with AMiner Data{Colors.ENDC}")
    print("=" * 60)
    print(f"Papers JSON: {papers_json_path}")
    print(f"Output: {output_path}")
    print(f"API URL: {args.api_url}")
    print(f"AMiner directory: {aminer_dir}")
    print(f"Enriched directory: {enriched_dir}")
    print(f"Force refresh: {args.force}")
    print(f"Delay: {args.delay}s")
    print()

    # Extract authors from papers
    authors_map = extract_authors_from_papers(papers_json_path, papers_cache_dir)

    if not authors_map:
        print(f"{Colors.YELLOW}No authors with AMiner IDs found{Colors.ENDC}")
        sys.exit(0)

    # Process authors
    authors_list, stats = process_authors(
        authors_map=authors_map,
        aminer_dir=aminer_dir,
        enriched_dir=enriched_dir,
        api_base_url=args.api_url,
        authorization=authorization,
        signature=signature,
        timestamp=timestamp,
        force=args.force,
        delay=args.delay,
        force_refresh=args.force_refresh,
        verbose=args.verbose
    )

    # Sort authors by name
    authors_list.sort(key=lambda x: x["normalized_name"])

    # Generate authors.json
    output_data = {
        "metadata": {
            "total_authors": len(authors_list),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": str(papers_json_path)
        },
        "authors": authors_list
    }

    print(f"\n{Colors.CYAN}Saving authors.json...{Colors.ENDC}")
    save_json_file(output_path, output_data)
    print(f"{Colors.GREEN}Saved to: {output_path}{Colors.ENDC}")

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
