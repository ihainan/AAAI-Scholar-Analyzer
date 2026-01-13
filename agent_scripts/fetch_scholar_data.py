#!/usr/bin/env python3
"""
Fetch scholar data from AMiner APIs and save to individual JSON files.

This script reads a JSON file containing scholar information with validated
AMiner IDs, fetches specified data from AMiner APIs, and saves the data to
individual JSON files. By default, only fetches basic detail information.

Usage:
    python fetch_scholar_data.py <json_file_path> [options]

Example:
    # Fetch only details (default)
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json

    # Fetch details and papers
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --fetch detail papers

    # Fetch all available data
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --fetch all

    # Update existing files with new data
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --mode update --fetch all

    # Fetch specific scholars only
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --ids 53f466dfdabfaedd74e6b9e2
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """Get the project root directory (parent of agent_scripts)."""
    return Path(__file__).parent.parent.resolve()


# Add the aminer skill directory to the path for importing
sys.path.insert(0, str(get_project_root() / ".claude/skills/aminer"))

from aminer_api import (
    get_person_detail,
    get_person_figure,
    get_person_projects,
    get_person_all_papers,
    get_person_patents,
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
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def get_validated_scholars(data: dict) -> list[dict]:
    """
    Extract scholars with validated AMiner IDs from the data.

    Returns only scholars where:
    - aminer_validation.status == "success"
    - aminer_validation.is_same_person == True (if present) OR
      confidence is not "low" (for newer validation format)
    - aminer_id exists and is not empty/failed
    """
    scholars = []
    for talent in data.get("talents", []):
        validation = talent.get("aminer_validation", {})
        aminer_id = talent.get("aminer_id", "")

        # Skip if no aminer_id or failed
        if not aminer_id or aminer_id == "failed":
            continue

        # Skip if validation failed
        if validation.get("status") != "success":
            continue

        # Check validation criteria based on format
        if "is_same_person" in validation:
            # Old format: check is_same_person
            if validation.get("is_same_person") is not True:
                continue
        elif "confidence" in validation:
            # New format: skip only if confidence is "low"
            if validation.get("confidence") == "low":
                continue
        else:
            # Unknown format with success status - include it
            pass

        scholars.append(talent)

    return scholars


def fetch_scholar_data(
    aminer_id: str,
    fetch_fields: set[str] = None,
    verbose: bool = False
) -> dict:
    """
    Fetch specified data for a scholar from AMiner APIs.

    Args:
        aminer_id: The scholar's AMiner ID
        fetch_fields: Set of fields to fetch (detail, figure, projects, papers, patents)
                     If None, defaults to {'detail'}
        verbose: Whether to print detailed progress

    Returns:
        Dictionary containing requested data from AMiner APIs.
        Only includes fields that were successfully fetched.
    """
    if fetch_fields is None:
        fetch_fields = {'detail'}

    result = {
        "aminer_id": aminer_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = []

    # Fetch person detail
    if 'detail' in fetch_fields:
        if verbose:
            print(f"       person-detail... ", end="", flush=True)
        try:
            detail_resp = get_person_detail(aminer_id)
            if detail_resp.get("success"):
                result["detail"] = detail_resp.get("data")
                if verbose:
                    print(f"{Colors.GREEN}OK{Colors.ENDC}")
            else:
                error_msg = detail_resp.get("message", "Unknown error")
                errors.append(f"person-detail: {error_msg}")
                if verbose:
                    print(f"{Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
        except Exception as e:
            errors.append(f"person-detail: {str(e)}")
            if verbose:
                print(f"{Colors.RED}ERROR{Colors.ENDC} ({str(e)})")

    # Fetch person figure (profile)
    if 'figure' in fetch_fields:
        if verbose:
            print(f"       person-figure... ", end="", flush=True)
        try:
            figure_resp = get_person_figure(aminer_id)
            if figure_resp.get("success"):
                result["figure"] = figure_resp.get("data")
                if verbose:
                    print(f"{Colors.GREEN}OK{Colors.ENDC}")
            else:
                error_msg = figure_resp.get("message", "Unknown error")
                errors.append(f"person-figure: {error_msg}")
                if verbose:
                    print(f"{Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
        except Exception as e:
            errors.append(f"person-figure: {str(e)}")
            if verbose:
                print(f"{Colors.RED}ERROR{Colors.ENDC} ({str(e)})")

    # Fetch person projects
    if 'projects' in fetch_fields:
        if verbose:
            print(f"       person-projects... ", end="", flush=True)
        try:
            projects_resp = get_person_projects(aminer_id)
            if projects_resp.get("success"):
                projects_data = projects_resp.get("data", [])
                result["projects"] = projects_data
                if verbose:
                    count = len(projects_data) if projects_data else 0
                    print(f"{Colors.GREEN}OK{Colors.ENDC} ({count} projects)")
            else:
                error_msg = projects_resp.get("message", "Unknown error")
                errors.append(f"person-projects: {error_msg}")
                if verbose:
                    print(f"{Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
        except Exception as e:
            errors.append(f"person-projects: {str(e)}")
            if verbose:
                print(f"{Colors.RED}ERROR{Colors.ENDC} ({str(e)})")

    # Fetch all papers
    if 'papers' in fetch_fields:
        if verbose:
            print(f"       person-papers... ", end="", flush=True)
        try:
            papers_resp = get_person_all_papers(aminer_id)
            if papers_resp.get("success"):
                papers_data = papers_resp.get("data", [])
                result["papers"] = papers_data
                if verbose:
                    count = len(papers_data) if papers_data else 0
                    print(f"{Colors.GREEN}OK{Colors.ENDC} ({count} papers)")
            else:
                error_msg = papers_resp.get("message", "Unknown error")
                errors.append(f"person-papers: {error_msg}")
                if verbose:
                    print(f"{Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
        except Exception as e:
            errors.append(f"person-papers: {str(e)}")
            if verbose:
                print(f"{Colors.RED}ERROR{Colors.ENDC} ({str(e)})")

    # Fetch patents
    if 'patents' in fetch_fields:
        if verbose:
            print(f"       person-patents... ", end="", flush=True)
        try:
            patents_resp = get_person_patents(aminer_id)
            if patents_resp.get("success"):
                patents_data = patents_resp.get("data", [])
                result["patents"] = patents_data
                if verbose:
                    count = len(patents_data) if patents_data else 0
                    print(f"{Colors.GREEN}OK{Colors.ENDC} ({count} patents)")
            else:
                error_msg = patents_resp.get("message", "Unknown error")
                errors.append(f"person-patents: {error_msg}")
                if verbose:
                    print(f"{Colors.RED}FAILED{Colors.ENDC} ({error_msg})")
        except Exception as e:
            errors.append(f"person-patents: {str(e)}")
            if verbose:
                print(f"{Colors.RED}ERROR{Colors.ENDC} ({str(e)})")

    # Only add errors list if there are errors
    if errors:
        result["errors"] = errors

    return result


def merge_scholar_data(existing: dict, new_data: dict) -> dict:
    """
    Merge new scholar data into existing data.

    Preserves existing fields and updates with new data where available.
    Only updates fields that are present in new_data.
    """
    merged = existing.copy()

    # Update timestamp
    merged["fetched_at"] = new_data["fetched_at"]

    # Update each data section if present in new data
    for key in ["detail", "figure", "projects", "papers", "patents"]:
        if key in new_data:
            merged[key] = new_data[key]

    # Merge errors
    existing_errors = existing.get("errors", [])
    new_errors = new_data.get("errors", [])
    if existing_errors or new_errors:
        merged["errors"] = list(set(existing_errors + new_errors))
    elif "errors" in merged:
        del merged["errors"]

    return merged


def process_scholars(
    json_file_path: Path,
    output_dir: Path,
    mode: str = "skip",
    fetch_fields: set[str] = None,
    target_ids: Optional[list[str]] = None,
    delay: float = 1.0,
    verbose: bool = False
) -> dict:
    """
    Process all validated scholars and fetch their AMiner data.

    Args:
        json_file_path: Path to the JSON file containing scholar information
        output_dir: Directory to save individual scholar JSON files
        mode: Processing mode - "skip", "update", or "merge"
        fetch_fields: Set of fields to fetch (detail, figure, projects, papers, patents)
        target_ids: Optional list of specific AMiner IDs to process
        delay: Delay between API requests in seconds
        verbose: Whether to print detailed progress

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

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Track statistics
    stats = {
        "total": len(scholars),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "partial": 0,
        "failed": 0,
        "failed_ids": []
    }

    for idx, scholar in enumerate(scholars, 1):
        name = scholar.get("name", "Unknown")
        aminer_id = scholar.get("aminer_id")
        output_file = output_dir / f"{aminer_id}.json"

        # Check if file exists and handle based on mode
        if output_file.exists():
            if mode == "skip":
                print(f"[{idx}/{stats['total']}] {Colors.DIM}Skipping{Colors.ENDC} {name} ({aminer_id}) - file exists")
                stats["skipped"] += 1
                continue
            elif mode == "merge":
                existing_data = load_json_file(output_file)
            # For "update" mode, we'll overwrite

        print(f"[{idx}/{stats['total']}] {Colors.CYAN}Fetching{Colors.ENDC} {name} ({aminer_id})")

        # Fetch data from AMiner APIs
        scholar_data = fetch_scholar_data(aminer_id, fetch_fields=fetch_fields, verbose=verbose)

        # Merge with existing data if in merge mode
        if mode == "merge" and output_file.exists():
            scholar_data = merge_scholar_data(existing_data, scholar_data)

        # Determine success status
        has_errors = "errors" in scholar_data and len(scholar_data.get("errors", [])) > 0
        has_any_data = any(scholar_data.get(key) is not None
                          for key in ["detail", "figure", "projects", "papers", "patents"])

        if has_errors:
            if has_any_data:
                status = "partial"
                stats["partial"] += 1
                status_color = Colors.YELLOW
            else:
                status = "failed"
                stats["failed"] += 1
                stats["failed_ids"].append(aminer_id)
                status_color = Colors.RED
        else:
            status = "success"
            stats["success"] += 1
            status_color = Colors.GREEN

        # Save the data
        save_json_file(output_file, scholar_data)
        print(f"       {status_color}[{status.upper()}]{Colors.ENDC} Saved to: {output_file.name}")

        stats["processed"] += 1

        # Rate limiting
        if idx < stats["total"] and delay > 0:
            time.sleep(delay)

    return stats


def print_summary(stats: dict) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Processing Summary{Colors.ENDC}")
    print("=" * 60)
    print(f"Total scholars:     {stats['total']}")
    print(f"Skipped:            {stats['skipped']}")
    print(f"Processed:          {stats['processed']}")
    print(f"  - Success:        {Colors.GREEN}{stats['success']}{Colors.ENDC}")
    print(f"  - Partial:        {Colors.YELLOW}{stats['partial']}{Colors.ENDC}")
    print(f"  - Failed:         {Colors.RED}{stats['failed']}{Colors.ENDC}")

    if stats["failed_ids"]:
        print(f"\n{Colors.RED}Failed AMiner IDs:{Colors.ENDC}")
        for aminer_id in stats["failed_ids"]:
            print(f"  - {aminer_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch scholar data from AMiner APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Fetch only details for all validated scholars (skip existing)
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json

    # Fetch details and papers
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --fetch detail papers

    # Fetch all available data
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --fetch all

    # Force update all existing files with new data
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --mode update --fetch all

    # Fetch specific scholars only
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --ids 53f466dfdabfaedd74e6b9e2

    # Custom output directory and delay
    python fetch_scholar_data.py ../data/aaai-26-ai-talents.json --output-dir ./output --delay 2.0
        """
    )

    parser.add_argument(
        "json_file",
        type=str,
        help="Path to the JSON file containing scholar information"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for scholar JSON files (default: data/aminer/scholars)"
    )

    parser.add_argument(
        "--fetch",
        nargs="+",
        choices=["detail", "figure", "projects", "papers", "patents", "all"],
        default=["detail"],
        help="Fields to fetch: detail, figure, projects, papers, patents, all (default: detail)"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["skip", "update", "merge"],
        default="skip",
        help="Processing mode: skip (default), update, or merge"
    )

    parser.add_argument(
        "--ids",
        nargs="+",
        dest="target_ids",
        help="Only process specific AMiner IDs"
    )

    parser.add_argument(
        "--ids-file",
        type=str,
        dest="ids_file",
        help="File containing AMiner IDs to process (one per line)"
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
        output_dir = project_root / "data" / "aminer" / "scholars"

    # Collect target IDs
    target_ids = args.target_ids or []
    if args.ids_file:
        ids_file_path = Path(args.ids_file).resolve()
        if ids_file_path.exists():
            with open(ids_file_path, 'r') as f:
                file_ids = [line.strip() for line in f if line.strip()]
                target_ids.extend(file_ids)
        else:
            print(f"Warning: IDs file not found: {ids_file_path}")

    target_ids = list(set(target_ids)) if target_ids else None

    # Process fetch fields
    fetch_fields = set(args.fetch)
    if 'all' in fetch_fields:
        fetch_fields = {'detail', 'figure', 'projects', 'papers', 'patents'}

    print(f"Output directory: {output_dir}")
    print(f"Mode: {args.mode}")
    print(f"Fetch fields: {', '.join(sorted(fetch_fields))}")
    print(f"Delay: {args.delay}s")
    if target_ids:
        print(f"Target IDs: {len(target_ids)} specified")
    print()

    # Process scholars
    stats = process_scholars(
        json_file_path=json_file_path,
        output_dir=output_dir,
        mode=args.mode,
        fetch_fields=fetch_fields,
        target_ids=target_ids,
        delay=args.delay,
        verbose=args.verbose
    )

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
