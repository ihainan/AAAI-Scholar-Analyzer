#!/usr/bin/env python3
"""
Enrich papers.json with AMiner data.

This script reads papers.json, searches for each paper on AMiner,
fetches detailed data, and updates the papers.json file with AMiner IDs.
It also persists detailed paper data to individual JSON files.

Usage:
    python enrich_papers_aminer.py <papers_json_path> [options]

Example:
    # Basic usage (skip papers that already have AMiner ID)
    python enrich_papers_aminer.py ../../data/aaai-26/papers.json

    # Force refresh all papers including those marked as not_found
    python enrich_papers_aminer.py ../../data/aaai-26/papers.json --force

    # Process specific papers only
    python enrich_papers_aminer.py ../../data/aaai-26/papers.json --paper-ids AIA67 MAIN123

    # Custom output directory and delay
    python enrich_papers_aminer.py ../../data/aaai-26/papers.json --output-dir ./output --delay 2.0
"""

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """Get the project root directory (grandparent of papers directory)."""
    return Path(__file__).parent.parent.parent.resolve()


# AMiner API Configuration
AMINER_BASE_URL = "https://datacenter.aminer.cn/gateway/open_platform/api"


def get_aminer_api_key() -> Optional[str]:
    """Get AMiner API key from environment variable."""
    return os.environ.get("AMINER_API_KEY")


def search_paper_api(title: str, size: int = 1, retry_count: int = 3, retry_delay: int = 10) -> dict:
    """
    Search for papers by title on AMiner API with retry logic.

    Args:
        title: Paper title to search
        size: Number of results to return
        retry_count: Number of retries on failure
        retry_delay: Delay between retries in seconds

    Returns:
        API response dict with success/data fields
    """
    api_key = get_aminer_api_key()
    if not api_key:
        return {"success": False, "msg": "AMINER_API_KEY not set", "data": None}

    params = {
        "title": title,
        "page": 0,
        "size": min(size, 20)  # Max 20
    }

    query_string = urllib.parse.urlencode(params)
    url = f"{AMINER_BASE_URL}/paper/search?{query_string}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json;charset=utf-8"
    }

    for attempt in range(retry_count):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if attempt < retry_count - 1:
                print(f"       {Colors.YELLOW}HTTP Error {e.code}, retrying in {retry_delay}s... (attempt {attempt + 1}/{retry_count}){Colors.ENDC}")
                time.sleep(retry_delay)
            else:
                return {"success": False, "msg": f"HTTP {e.code}: {error_body}", "data": None}
        except urllib.error.URLError as e:
            if attempt < retry_count - 1:
                print(f"       {Colors.YELLOW}Network error, retrying in {retry_delay}s... (attempt {attempt + 1}/{retry_count}){Colors.ENDC}")
                time.sleep(retry_delay)
            else:
                return {"success": False, "msg": f"Network error: {str(e)}", "data": None}
        except Exception as e:
            return {"success": False, "msg": f"Unexpected error: {str(e)}", "data": None}

    return {"success": False, "msg": "Max retries exceeded", "data": None}


def get_paper_detail_api(paper_id: str, retry_count: int = 3, retry_delay: int = 10) -> dict:
    """
    Get paper details by ID from AMiner API with retry logic.

    Args:
        paper_id: Paper ID
        retry_count: Number of retries on failure
        retry_delay: Delay between retries in seconds

    Returns:
        API response dict with success/data fields
    """
    api_key = get_aminer_api_key()
    if not api_key:
        return {"success": False, "msg": "AMINER_API_KEY not set", "data": None}

    params = {"id": paper_id}
    query_string = urllib.parse.urlencode(params)
    url = f"{AMINER_BASE_URL}/paper/detail?{query_string}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json;charset=utf-8"
    }

    for attempt in range(retry_count):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if attempt < retry_count - 1:
                print(f"       {Colors.YELLOW}HTTP Error {e.code}, retrying in {retry_delay}s... (attempt {attempt + 1}/{retry_count}){Colors.ENDC}")
                time.sleep(retry_delay)
            else:
                return {"success": False, "msg": f"HTTP {e.code}: {error_body}", "data": None}
        except urllib.error.URLError as e:
            if attempt < retry_count - 1:
                print(f"       {Colors.YELLOW}Network error, retrying in {retry_delay}s... (attempt {attempt + 1}/{retry_count}){Colors.ENDC}")
                time.sleep(retry_delay)
            else:
                return {"success": False, "msg": f"Network error: {str(e)}", "data": None}
        except Exception as e:
            return {"success": False, "msg": f"Unexpected error: {str(e)}", "data": None}

    return {"success": False, "msg": "Max retries exceeded", "data": None}


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def load_json_file(file_path: Path) -> dict:
    """Load and parse a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: dict) -> None:
    """Save data to a JSON file with proper formatting."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def backup_file(file_path: Path, project_root: Path) -> Path:
    """
    Create a backup of the file with timestamp in data/backup directory.

    Args:
        file_path: Path to the file to backup
        project_root: Project root directory

    Returns:
        Path to the backup file, or None if source file doesn't exist
    """
    if not file_path.exists():
        return None

    # Calculate relative path from project root
    try:
        relative_path = file_path.relative_to(project_root)
    except ValueError:
        relative_path = file_path

    # Create backup path in data/backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_root / "data" / "backup" / relative_path.parent
    backup_filename = f"{file_path.stem}.backup_{timestamp}{file_path.suffix}"
    backup_path = backup_dir / backup_filename

    # Ensure backup directory exists
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Copy file to backup location
    shutil.copy2(file_path, backup_path)
    return backup_path


def search_paper_by_title(title: str, verbose: bool = False) -> tuple[Optional[str], str]:
    """
    Search for a paper by title on AMiner with automatic retry.

    Args:
        title: Paper title to search
        verbose: Whether to print detailed progress

    Returns:
        Tuple of (aminer_id, status) where status is "success", "not_found", or "failed"
    """
    if verbose:
        print(f"       Searching title: {title[:60]}...", end="", flush=True)

    search_result = search_paper_api(title=title, size=1, retry_count=3, retry_delay=10)

    if search_result.get("success"):
        data = search_result.get("data", [])
        if data and len(data) > 0:
            aminer_id = data[0].get("id")
            if verbose:
                print(f" {Colors.GREEN}FOUND{Colors.ENDC} (ID: {aminer_id})")
            return aminer_id, "success"
        else:
            if verbose:
                print(f" {Colors.YELLOW}NOT FOUND{Colors.ENDC}")
            return None, "not_found"
    else:
        error_msg = search_result.get("msg", "Unknown error")
        if verbose:
            print(f" {Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
        return None, "failed"


def fetch_paper_detail_data(aminer_id: str, verbose: bool = False) -> Optional[dict]:
    """
    Fetch detailed information about a paper from AMiner with automatic retry.

    Args:
        aminer_id: The paper's AMiner ID
        verbose: Whether to print detailed progress

    Returns:
        Paper detail data or None if failed
    """
    if verbose:
        print(f"       Fetching details...", end="", flush=True)

    detail_result = get_paper_detail_api(aminer_id, retry_count=3, retry_delay=10)

    if detail_result.get("success"):
        data = detail_result.get("data", [])
        if data and len(data) > 0:
            if verbose:
                print(f" {Colors.GREEN}OK{Colors.ENDC}")
            return data[0]
        else:
            if verbose:
                print(f" {Colors.RED}NO DATA{Colors.ENDC}")
            return None
    else:
        error_msg = detail_result.get("msg", "Unknown error")
        if verbose:
            print(f" {Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
        return None


def save_paper_detail(
    output_dir: Path,
    aminer_id: str,
    detail: dict
) -> None:
    """
    Save paper detail data to file using AMiner ID as filename.

    Note: Caller should check if file exists before calling this function.

    Args:
        output_dir: Output directory for paper JSON files
        aminer_id: AMiner paper ID (used as filename)
        detail: Paper detail data from API
    """
    file_path = output_dir / f"{aminer_id}.json"

    paper_data = {
        "aminer_id": aminer_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "detail": detail
    }

    save_json_file(file_path, paper_data)


def update_paper_with_aminer(
    paper: dict,
    aminer_id: Optional[str],
    status: str
) -> bool:
    """
    Update a single paper entry with AMiner information.

    Args:
        paper: Paper dictionary to update
        aminer_id: AMiner paper ID (None if not found)
        status: Validation status

    Returns:
        True if paper was modified
    """
    modified = False

    # Update aminer_paper_id
    if aminer_id:
        if paper.get("aminer_paper_id") != aminer_id:
            paper["aminer_paper_id"] = aminer_id
            modified = True
    elif "aminer_paper_id" in paper and status in ["not_found", "failed"]:
        # Remove aminer_paper_id if search failed
        del paper["aminer_paper_id"]
        modified = True

    # Update validation status (only if status changed)
    existing_validation = paper.get("aminer_validation", {})
    existing_status = existing_validation.get("status")

    if existing_status != status:
        # Status changed, update with new timestamp
        validation = {
            "status": status,
            "matched_at": datetime.now(timezone.utc).isoformat()
        }
        paper["aminer_validation"] = validation
        modified = True

    return modified


def process_papers(
    json_file_path: Path,
    output_dir: Path,
    force: bool = False,
    target_paper_ids: Optional[list[str]] = None,
    delay: float = 1.0,
    verbose: bool = False
) -> dict:
    """
    Process all papers in the papers.json file and enrich with AMiner data.

    Args:
        json_file_path: Path to the papers.json file
        output_dir: Directory to save individual paper JSON files
        force: Force re-fetch even if already has AMiner ID or marked as not_found
        target_paper_ids: Optional list of specific paper IDs to process
        delay: Delay between API requests in seconds
        verbose: Whether to print detailed progress

    Returns:
        Statistics dictionary with processing results
    """
    project_root = get_project_root()

    # Load the JSON file
    print(f"Loading papers.json: {json_file_path}")
    data = load_json_file(json_file_path)

    # Get papers
    papers = data.get("papers", [])
    print(f"Found {len(papers)} papers in the file\n")

    # Filter by target paper IDs if specified
    if target_paper_ids:
        papers = [p for p in papers if p.get("paper_id") in target_paper_ids]
        print(f"Filtered to {len(papers)} papers matching target IDs\n")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Track statistics
    stats = {
        "total": len(papers),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "not_found": 0,
        "failed": 0,
        "failed_ids": []
    }

    json_modified = False

    for idx, paper in enumerate(papers, 1):
        title = paper.get("title", "Unknown")
        paper_id = paper.get("paper_id", "Unknown")
        existing_aminer_id = paper.get("aminer_paper_id")
        validation_status = paper.get("aminer_validation", {}).get("status")

        # Check if should skip
        if not force:
            if existing_aminer_id:
                print(f"[{idx}/{stats['total']}] {Colors.DIM}Skipping{Colors.ENDC} {paper_id}: {title[:50]}... (already has AMiner ID)")
                stats["skipped"] += 1
                continue
            if validation_status == "not_found":
                print(f"[{idx}/{stats['total']}] {Colors.DIM}Skipping{Colors.ENDC} {paper_id}: {title[:50]}... (marked as not_found)")
                stats["skipped"] += 1
                continue

        print(f"[{idx}/{stats['total']}] {Colors.CYAN}Processing{Colors.ENDC} {paper_id}: {title[:50]}...")

        # Search for paper on AMiner
        aminer_id, status = search_paper_by_title(title, verbose=verbose)

        if status == "success" and aminer_id:
            # Check if detail cache already exists
            cache_file = output_dir / f"{aminer_id}.json"

            if cache_file.exists():
                # Cache exists, skip API call
                if verbose:
                    print(f"       {Colors.DIM}Cache exists, skipping API call{Colors.ENDC}")

                # Update papers.json
                if update_paper_with_aminer(paper, aminer_id, "success"):
                    json_modified = True

                print(f"       {Colors.GREEN}[SUCCESS]{Colors.ENDC} Using cached detail: {aminer_id}.json")
                stats["success"] += 1
            else:
                # Cache doesn't exist, fetch from API
                detail = fetch_paper_detail_data(aminer_id, verbose=verbose)

                if detail:
                    # Save paper detail data
                    save_paper_detail(
                        output_dir=output_dir,
                        aminer_id=aminer_id,
                        detail=detail
                    )

                    # Update papers.json
                    if update_paper_with_aminer(paper, aminer_id, "success"):
                        json_modified = True

                    print(f"       {Colors.GREEN}[SUCCESS]{Colors.ENDC} Saved detail to: {aminer_id}.json")
                    stats["success"] += 1
                else:
                    # Detail fetch failed (after retries)
                    if update_paper_with_aminer(paper, None, "failed"):
                        json_modified = True
                    print(f"       {Colors.RED}[FAILED]{Colors.ENDC} Could not fetch paper details (after retries)")
                    print(f"       {Colors.YELLOW}Waiting 10s before continuing...{Colors.ENDC}")
                    time.sleep(10)
                    stats["failed"] += 1
                    stats["failed_ids"].append(paper_id)
        elif status == "not_found":
            # Paper not found on AMiner
            if update_paper_with_aminer(paper, None, "not_found"):
                json_modified = True
            print(f"       {Colors.YELLOW}[NOT FOUND]{Colors.ENDC} No matching paper on AMiner")
            stats["not_found"] += 1
        else:
            # Search failed (after retries)
            if update_paper_with_aminer(paper, None, "failed"):
                json_modified = True
            print(f"       {Colors.RED}[FAILED]{Colors.ENDC} Search API call failed (after retries)")
            print(f"       {Colors.YELLOW}Waiting 10s before continuing...{Colors.ENDC}")
            time.sleep(10)
            stats["failed"] += 1
            stats["failed_ids"].append(paper_id)

        stats["processed"] += 1

        # Save after every paper (if modified) to prevent data loss
        if json_modified:
            save_json_file(json_file_path, data)

        # Backup every 100 processed papers
        if json_modified and stats["processed"] % 100 == 0:
            print(f"\n{Colors.CYAN}[Checkpoint] Creating backup... ({stats['processed']}/{stats['total']}){Colors.ENDC}")
            backup_path = backup_file(json_file_path, project_root)
            if backup_path:
                print(f"Backup saved to: {backup_path}")
            print(f"{Colors.GREEN}Checkpoint backup created{Colors.ENDC}\n")

        # Rate limiting
        if idx < stats["total"] and delay > 0:
            time.sleep(delay)

    # Final backup if modified (only if we didn't just backup at a checkpoint)
    if json_modified and stats["processed"] % 100 != 0:
        print(f"\n{Colors.CYAN}Creating final backup...{Colors.ENDC}")
        backup_path = backup_file(json_file_path, project_root)
        if backup_path:
            print(f"Backup saved to: {backup_path}")
        print(f"{Colors.GREEN}Final backup created{Colors.ENDC}")

    return stats


def print_summary(stats: dict) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Enrichment Summary{Colors.ENDC}")
    print("=" * 60)
    print(f"Total papers:       {stats['total']}")
    print(f"Skipped:            {stats['skipped']}")
    print(f"Processed:          {stats['processed']}")
    print(f"  - Success:        {Colors.GREEN}{stats['success']}{Colors.ENDC}")
    print(f"  - Not Found:      {Colors.YELLOW}{stats['not_found']}{Colors.ENDC}")
    print(f"  - Failed:         {Colors.RED}{stats['failed']}{Colors.ENDC}")

    if stats["failed_ids"]:
        print(f"\n{Colors.RED}Failed Paper IDs:{Colors.ENDC}")
        for paper_id in stats["failed_ids"]:
            print(f"  - {paper_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Enrich papers.json with AMiner data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "json_file",
        type=str,
        help="Path to the papers.json file"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for paper detail JSON files (default: data/aminer/papers)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch even if already has AMiner ID or marked as not_found"
    )

    parser.add_argument(
        "--paper-ids",
        nargs="+",
        dest="target_paper_ids",
        help="Only process specific paper IDs"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between API requests in seconds (default: 0.5)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress for each API call"
    )

    args = parser.parse_args()

    # Resolve file path
    json_file_path = Path(args.json_file).resolve()
    if not json_file_path.exists():
        print(f"{Colors.RED}Error: File not found: {json_file_path}{Colors.ENDC}")
        sys.exit(1)

    # Determine output directory
    project_root = get_project_root()
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        # Default: data/aminer/papers (global cache)
        output_dir = project_root / "data" / "aminer" / "papers"

    print(f"{Colors.BOLD}Enrich Papers with AMiner Data{Colors.ENDC}")
    print(f"Input file: {json_file_path}")
    print(f"Output directory: {output_dir}")
    print(f"Force refresh: {args.force}")
    print(f"Delay: {args.delay}s")
    if args.target_paper_ids:
        print(f"Target paper IDs: {len(args.target_paper_ids)} specified")
    print()

    # Process papers
    stats = process_papers(
        json_file_path=json_file_path,
        output_dir=output_dir,
        force=args.force,
        target_paper_ids=args.target_paper_ids,
        delay=args.delay,
        verbose=args.verbose
    )

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
