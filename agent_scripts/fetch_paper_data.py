#!/usr/bin/env python3
"""
Fetch paper data from AMiner APIs and save to individual JSON files.

This script reads a JSON file containing paper information, searches for papers
on AMiner by title (strict match), fetches detailed data, and saves the data to
individual JSON files. It also updates the original JSON with AMiner paper IDs.

Usage:
    python fetch_paper_data.py <json_file_path> [options]

Example:
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json --mode update
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json --paper-ids AIA67
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """Get the project root directory (parent of agent_scripts)."""
    return Path(__file__).parent.parent.resolve()


# Add the aminer-paper skill directory to the path for importing
sys.path.insert(0, str(get_project_root() / ".claude/skills/aminer-paper"))

from aminer_paper_api import (
    search_paper,
    get_paper_detail,
)


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
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
        # If file is outside project root, use absolute path structure
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


def get_papers_from_json(data: dict) -> list[dict]:
    """
    Extract papers from the JSON data.

    Expects data structure with a "papers" key containing a list of papers.
    """
    return data.get("papers", [])


def search_paper_by_title(title: str, verbose: bool = False) -> tuple[Optional[str], str]:
    """
    Search for a paper by title on AMiner.

    Args:
        title: Paper title to search
        verbose: Whether to print detailed progress

    Returns:
        Tuple of (aminer_id, status) where status is "success", "not_found", or "failed"
    """
    if verbose:
        print(f"       Searching title: {title[:60]}...", end="", flush=True)

    try:
        search_result = search_paper(title=title, size=1)

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
    except Exception as e:
        if verbose:
            print(f" {Colors.RED}ERROR{Colors.ENDC} ({str(e)})")
        return None, "failed"


def fetch_paper_detail_data(aminer_id: str, verbose: bool = False) -> Optional[dict]:
    """
    Fetch detailed information about a paper from AMiner.

    Args:
        aminer_id: The paper's AMiner ID
        verbose: Whether to print detailed progress

    Returns:
        Paper detail data or None if failed
    """
    if verbose:
        print(f"       Fetching details...", end="", flush=True)

    try:
        detail_result = get_paper_detail(aminer_id)

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
    except Exception as e:
        if verbose:
            print(f" {Colors.RED}ERROR{Colors.ENDC} ({str(e)})")
        return None


def load_or_create_paper_file(file_path: Path, aminer_id: str) -> dict:
    """
    Load existing paper file or create a new structure.

    Args:
        file_path: Path to the paper JSON file
        aminer_id: AMiner paper ID

    Returns:
        Paper data dictionary
    """
    if file_path.exists():
        return load_json_file(file_path)
    else:
        return {
            "aminer_id": aminer_id,
            "fetched_at": None,
            "sources": [],
            "detail": None
        }


def add_source_to_paper_data(
    paper_data: dict,
    source_file: Path,
    paper_id: str,
    project_root: Path
) -> bool:
    """
    Add source information to paper data if not already present.

    Args:
        paper_data: The paper data dictionary
        source_file: Path to the source JSON file
        paper_id: The paper ID in the source file
        project_root: Project root directory for relative path calculation

    Returns:
        True if source was added, False if it already exists
    """
    # Calculate relative path from project root
    try:
        relative_path = source_file.relative_to(project_root)
    except ValueError:
        relative_path = source_file

    source_path_str = str(relative_path)

    # Check if source already exists
    for source in paper_data.get("sources", []):
        if source.get("file") == source_path_str and source.get("paper_id") == paper_id:
            return False

    # Add new source
    new_source = {
        "file": source_path_str,
        "paper_id": paper_id,
        "added_at": datetime.now(timezone.utc).isoformat()
    }
    paper_data["sources"].append(new_source)
    return True


def save_paper_data(
    output_dir: Path,
    aminer_id: str,
    detail: dict,
    source_file: Path,
    paper_id: str,
    project_root: Path,
    mode: str = "skip"
) -> None:
    """
    Save paper data to file with source tracking.

    Args:
        output_dir: Output directory for paper JSON files
        aminer_id: AMiner paper ID
        detail: Paper detail data from API
        source_file: Source JSON file path
        paper_id: Paper ID in source file
        project_root: Project root directory
        mode: Processing mode (skip/update/merge)
    """
    file_path = output_dir / f"{aminer_id}.json"

    # Load or create paper data structure
    paper_data = load_or_create_paper_file(file_path, aminer_id)

    # Update detail data based on mode
    if mode == "update" or paper_data["detail"] is None:
        paper_data["detail"] = detail
        paper_data["fetched_at"] = datetime.now(timezone.utc).isoformat()

    # Add source information
    add_source_to_paper_data(paper_data, source_file, paper_id, project_root)

    # Save to file
    save_json_file(file_path, paper_data)


def update_original_json_paper(
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

    # Update validation status
    validation = {
        "status": status,
        "matched_at": datetime.now(timezone.utc).isoformat()
    }

    if paper.get("aminer_validation") != validation:
        paper["aminer_validation"] = validation
        modified = True

    return modified


def process_papers(
    json_file_path: Path,
    output_dir: Path,
    mode: str = "skip",
    target_paper_ids: Optional[list[str]] = None,
    delay: float = 1.0,
    verbose: bool = False
) -> dict:
    """
    Process all papers in the JSON file and fetch their AMiner data.

    Args:
        json_file_path: Path to the JSON file containing paper information
        output_dir: Directory to save individual paper JSON files
        mode: Processing mode - "skip", "update", or "merge"
        target_paper_ids: Optional list of specific paper IDs to process
        delay: Delay between API requests in seconds
        verbose: Whether to print detailed progress

    Returns:
        Statistics dictionary with processing results
    """
    project_root = get_project_root()

    # Load the JSON file
    print(f"Loading JSON file: {json_file_path}")
    data = load_json_file(json_file_path)

    # Get papers
    papers = get_papers_from_json(data)
    print(f"Found {len(papers)} papers in the file")

    # Filter by target paper IDs if specified
    if target_paper_ids:
        papers = [p for p in papers if p.get("paper_id") in target_paper_ids]
        print(f"Filtered to {len(papers)} papers matching target IDs")

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

        # Check if already processed and handle based on mode
        if existing_aminer_id and mode == "skip":
            print(f"[{idx}/{stats['total']}] {Colors.DIM}Skipping{Colors.ENDC} {paper_id}: {title[:50]}... (already has AMiner ID)")
            stats["skipped"] += 1
            continue

        print(f"[{idx}/{stats['total']}] {Colors.CYAN}Processing{Colors.ENDC} {paper_id}: {title[:50]}...")

        # Search for paper on AMiner
        aminer_id, status = search_paper_by_title(title, verbose=verbose)

        if status == "success" and aminer_id:
            # Fetch paper details
            detail = fetch_paper_detail_data(aminer_id, verbose=verbose)

            if detail:
                # Save paper data
                save_paper_data(
                    output_dir=output_dir,
                    aminer_id=aminer_id,
                    detail=detail,
                    source_file=json_file_path,
                    paper_id=paper_id,
                    project_root=project_root,
                    mode=mode
                )

                # Update original JSON
                if update_original_json_paper(paper, aminer_id, "success"):
                    json_modified = True

                print(f"       {Colors.GREEN}[SUCCESS]{Colors.ENDC} Saved to: {aminer_id}.json")
                stats["success"] += 1
            else:
                # Detail fetch failed
                if update_original_json_paper(paper, None, "failed"):
                    json_modified = True
                print(f"       {Colors.RED}[FAILED]{Colors.ENDC} Could not fetch paper details")
                stats["failed"] += 1
                stats["failed_ids"].append(paper_id)
        elif status == "not_found":
            # Paper not found on AMiner
            if update_original_json_paper(paper, None, "not_found"):
                json_modified = True
            print(f"       {Colors.YELLOW}[NOT FOUND]{Colors.ENDC} No matching paper on AMiner")
            stats["not_found"] += 1
        else:
            # Search failed
            if update_original_json_paper(paper, None, "failed"):
                json_modified = True
            print(f"       {Colors.RED}[FAILED]{Colors.ENDC} Search API call failed")
            stats["failed"] += 1
            stats["failed_ids"].append(paper_id)

        stats["processed"] += 1

        # Rate limiting
        if idx < stats["total"] and delay > 0:
            time.sleep(delay)

    # Save updated original JSON if modified
    if json_modified:
        print(f"\n{Colors.CYAN}Backing up and updating original JSON...{Colors.ENDC}")
        backup_path = backup_file(json_file_path, project_root)
        if backup_path:
            print(f"Backup saved to: {backup_path}")
        save_json_file(json_file_path, data)
        print(f"{Colors.GREEN}Original JSON updated{Colors.ENDC}")

    return stats


def print_summary(stats: dict) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Processing Summary{Colors.ENDC}")
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
        description="Fetch paper data from AMiner APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Fetch all papers (skip existing)
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json

    # Force update all existing files
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json --mode update

    # Merge new data with existing files
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json --mode merge

    # Fetch specific papers only
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json --paper-ids AIA67 AIA206

    # Custom output directory and delay
    python fetch_paper_data.py ../data/aaai-26/program/aia-track-oral-talks.json --output-dir ./output --delay 2.0
        """
    )

    parser.add_argument(
        "json_file",
        type=str,
        help="Path to the JSON file containing paper information"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for paper JSON files (default: data/aminer/papers)"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["skip", "update", "merge"],
        default="skip",
        help="Processing mode: skip (default), update, or merge"
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
        default=1.0,
        help="Delay between API requests in seconds (default: 1.0)"
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
        print(f"Error: File not found: {json_file_path}")
        sys.exit(1)

    # Determine output directory
    project_root = get_project_root()
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        output_dir = project_root / "data" / "aminer" / "papers"

    print(f"Output directory: {output_dir}")
    print(f"Mode: {args.mode}")
    print(f"Delay: {args.delay}s")
    if args.target_paper_ids:
        print(f"Target paper IDs: {len(args.target_paper_ids)} specified")
    print()

    # Process papers
    stats = process_papers(
        json_file_path=json_file_path,
        output_dir=output_dir,
        mode=args.mode,
        target_paper_ids=args.target_paper_ids,
        delay=args.delay,
        verbose=args.verbose
    )

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
