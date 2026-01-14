#!/usr/bin/env python3
"""
Build complete paper data pipeline.

This script executes the full data processing pipeline in the correct order:
1. merge_tracks.py - Merge track JSON files into papers.json
2. enrich_papers_aminer.py - Enrich papers with AMiner data
3. enrich_authors_aminer.py - Extract authors and enrich with AMiner data
4. generate_indexes.py - Generate index files

Usage:
    python build_pipeline.py <conference_dir> [options]

Example:
    # Run full pipeline
    python build_pipeline.py ../../data/aaai-26

    # Start from a specific step
    python build_pipeline.py ../../data/aaai-26 --start-from enrich-authors

    # Run only specific steps
    python build_pipeline.py ../../data/aaai-26 --steps merge enrich-papers

    # With AMiner credentials
    export AMINER_AUTH="Bearer xxx"
    export AMINER_SIGNATURE="xxx"
    export AMINER_TIMESTAMP="xxx"
    python build_pipeline.py ../../data/aaai-26
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for common_utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from common_utils import Colors


# Pipeline steps definition
PIPELINE_STEPS = [
    {
        "id": "merge",
        "name": "Merge Tracks",
        "script": "merge_tracks.py",
        "description": "Merge track JSON files into papers.json",
        "requires": ["program directory with track JSON files"],
        "produces": ["papers.json"]
    },
    {
        "id": "enrich-papers",
        "name": "Enrich Papers",
        "script": "enrich_papers_aminer.py",
        "description": "Enrich papers with AMiner data",
        "requires": ["papers.json"],
        "produces": ["papers.json (updated)", "aminer/papers/*.json"]
    },
    {
        "id": "enrich-authors",
        "name": "Enrich Authors",
        "script": "enrich_authors_aminer.py",
        "description": "Extract authors and enrich with AMiner data",
        "requires": ["papers.json", "AMiner API credentials"],
        "produces": ["authors.json", "aminer/authors/*.json"]
    },
    {
        "id": "generate-indexes",
        "name": "Generate Indexes",
        "script": "generate_indexes.py",
        "description": "Generate index files for frontend",
        "requires": ["papers.json", "authors.json"],
        "produces": ["indexes/*.json"]
    }
]


def print_step_header(step_num: int, total_steps: int, step: dict):
    """Print step header."""
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}Step {step_num}/{total_steps}: {step['name']}{Colors.ENDC}")
    print("=" * 70)
    print(f"{Colors.DIM}{step['description']}{Colors.ENDC}")
    print()


def run_merge_tracks(conference_dir: Path, program_dir: Path) -> bool:
    """Run merge_tracks.py script."""
    script_path = Path(__file__).parent / "merge_tracks.py"
    papers_json = conference_dir / "papers.json"

    cmd = [
        sys.executable,
        str(script_path),
        str(program_dir),
        "-o", str(papers_json)
    ]

    print(f"{Colors.CYAN}Running: {' '.join(cmd)}{Colors.ENDC}\n")

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.RED}Error: merge_tracks.py failed with exit code {e.returncode}{Colors.ENDC}")
        return False


def run_enrich_papers(conference_dir: Path, force: bool = False, delay: float = 1.0) -> bool:
    """Run enrich_papers_aminer.py script."""
    script_path = Path(__file__).parent / "enrich_papers_aminer.py"
    papers_json = conference_dir / "papers.json"

    cmd = [
        sys.executable,
        str(script_path),
        str(papers_json),
        "--delay", str(delay)
    ]

    if force:
        cmd.append("--force")

    print(f"{Colors.CYAN}Running: {' '.join(cmd)}{Colors.ENDC}\n")

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.RED}Error: enrich_papers_aminer.py failed with exit code {e.returncode}{Colors.ENDC}")
        return False


def run_enrich_authors(conference_dir: Path, force: bool = False, delay: float = 2.0) -> bool:
    """Run enrich_authors_aminer.py script."""
    script_path = Path(__file__).parent / "enrich_authors_aminer.py"
    papers_json = conference_dir / "papers.json"

    cmd = [
        sys.executable,
        str(script_path),
        str(papers_json),
        "--delay", str(delay)
    ]

    if force:
        cmd.append("--force")

    print(f"{Colors.CYAN}Running: {' '.join(cmd)}{Colors.ENDC}\n")

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.RED}Error: enrich_authors_aminer.py failed with exit code {e.returncode}{Colors.ENDC}")
        return False


def run_generate_indexes(conference_dir: Path) -> bool:
    """Run generate_indexes.py script."""
    script_path = Path(__file__).parent / "generate_indexes.py"

    cmd = [
        sys.executable,
        str(script_path),
        str(conference_dir)
    ]

    print(f"{Colors.CYAN}Running: {' '.join(cmd)}{Colors.ENDC}\n")

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.RED}Error: generate_indexes.py failed with exit code {e.returncode}{Colors.ENDC}")
        return False


def check_aminer_credentials() -> bool:
    """Check if AMiner API credentials are set."""
    auth = os.environ.get("AMINER_AUTH")
    sig = os.environ.get("AMINER_SIGNATURE")
    ts = os.environ.get("AMINER_TIMESTAMP")

    return bool(auth and sig and ts)


def run_pipeline(
    conference_dir: Path,
    program_dir: Path,
    steps_to_run: list[str],
    force: bool = False,
    paper_delay: float = 1.0,
    author_delay: float = 2.0
) -> dict:
    """
    Run the pipeline.

    Args:
        conference_dir: Conference directory
        program_dir: Program directory with track JSON files
        steps_to_run: List of step IDs to run
        force: Force re-processing
        paper_delay: Delay for paper enrichment
        author_delay: Delay for author enrichment

    Returns:
        Statistics dictionary
    """
    stats = {
        "total_steps": len(steps_to_run),
        "completed": 0,
        "failed": 0,
        "skipped": 0
    }

    step_map = {step["id"]: step for step in PIPELINE_STEPS}

    for idx, step_id in enumerate(steps_to_run, 1):
        step = step_map[step_id]
        print_step_header(idx, stats["total_steps"], step)

        success = False

        if step_id == "merge":
            success = run_merge_tracks(conference_dir, program_dir)
        elif step_id == "enrich-papers":
            success = run_enrich_papers(conference_dir, force, paper_delay)
        elif step_id == "enrich-authors":
            # Check credentials before running
            if not check_aminer_credentials():
                print(f"{Colors.YELLOW}Warning: AMiner credentials not found{Colors.ENDC}")
                print(f"{Colors.YELLOW}Please set AMINER_AUTH, AMINER_SIGNATURE, and AMINER_TIMESTAMP environment variables{Colors.ENDC}")
                print(f"{Colors.RED}Skipping author enrichment{Colors.ENDC}")
                stats["skipped"] += 1
                continue
            success = run_enrich_authors(conference_dir, force, author_delay)
        elif step_id == "generate-indexes":
            success = run_generate_indexes(conference_dir)

        if success:
            print(f"\n{Colors.GREEN}✓ Step {idx}/{stats['total_steps']} completed successfully{Colors.ENDC}")
            stats["completed"] += 1
        else:
            print(f"\n{Colors.RED}✗ Step {idx}/{stats['total_steps']} failed{Colors.ENDC}")
            stats["failed"] += 1
            print(f"\n{Colors.RED}Pipeline stopped due to error{Colors.ENDC}")
            break

    return stats


def print_summary(stats: dict, start_time: datetime):
    """Print pipeline summary."""
    duration = datetime.now() - start_time
    duration_str = str(duration).split('.')[0]  # Remove microseconds

    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}Pipeline Summary{Colors.ENDC}")
    print("=" * 70)
    print(f"Total steps:     {stats['total_steps']}")
    print(f"Completed:       {Colors.GREEN}{stats['completed']}{Colors.ENDC}")
    print(f"Failed:          {Colors.RED}{stats['failed']}{Colors.ENDC}")
    print(f"Skipped:         {Colors.YELLOW}{stats['skipped']}{Colors.ENDC}")
    print(f"Duration:        {duration_str}")
    print()

    if stats["failed"] > 0:
        print(f"{Colors.RED}Pipeline completed with errors{Colors.ENDC}")
    elif stats["completed"] == stats["total_steps"]:
        print(f"{Colors.GREEN}Pipeline completed successfully!{Colors.ENDC}")


def main():
    parser = argparse.ArgumentParser(
        description="Build complete paper data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "conference_dir",
        type=str,
        help="Conference directory (e.g., data/aaai-26)"
    )

    parser.add_argument(
        "--program-dir",
        type=str,
        default=None,
        help="Program directory with track JSON files (default: <conference_dir>/program)"
    )

    parser.add_argument(
        "--start-from",
        type=str,
        choices=["merge", "enrich-papers", "enrich-authors", "generate-indexes"],
        help="Start pipeline from a specific step"
    )

    parser.add_argument(
        "--steps",
        nargs="+",
        choices=["merge", "enrich-papers", "enrich-authors", "generate-indexes"],
        help="Run only specific steps"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-processing (passed to enrich scripts)"
    )

    parser.add_argument(
        "--paper-delay",
        type=float,
        default=1.0,
        help="Delay between paper API requests in seconds (default: 1.0)"
    )

    parser.add_argument(
        "--author-delay",
        type=float,
        default=2.0,
        help="Delay between author API requests in seconds (default: 2.0)"
    )

    args = parser.parse_args()

    # Resolve paths
    conference_dir = Path(args.conference_dir).resolve()
    if not conference_dir.exists():
        print(f"{Colors.RED}Error: Conference directory not found: {conference_dir}{Colors.ENDC}")
        sys.exit(1)

    program_dir = Path(args.program_dir).resolve() if args.program_dir else conference_dir / "program"
    if not program_dir.exists():
        print(f"{Colors.RED}Error: Program directory not found: {program_dir}{Colors.ENDC}")
        sys.exit(1)

    # Determine steps to run
    all_step_ids = [step["id"] for step in PIPELINE_STEPS]

    if args.steps:
        steps_to_run = args.steps
    elif args.start_from:
        start_index = all_step_ids.index(args.start_from)
        steps_to_run = all_step_ids[start_index:]
    else:
        steps_to_run = all_step_ids

    # Print configuration
    print("=" * 70)
    print(f"{Colors.BOLD}Paper Data Pipeline{Colors.ENDC}")
    print("=" * 70)
    print(f"Conference directory: {conference_dir}")
    print(f"Program directory:    {program_dir}")
    print(f"Steps to run:         {', '.join(steps_to_run)}")
    print(f"Force re-processing:  {args.force}")
    print(f"Paper delay:          {args.paper_delay}s")
    print(f"Author delay:         {args.author_delay}s")

    # Check AMiner credentials if needed
    if "enrich-authors" in steps_to_run:
        if check_aminer_credentials():
            print(f"AMiner credentials:   {Colors.GREEN}✓ Found{Colors.ENDC}")
        else:
            print(f"AMiner credentials:   {Colors.YELLOW}⚠ Not found{Colors.ENDC}")
            print(f"{Colors.DIM}Set AMINER_AUTH, AMINER_SIGNATURE, and AMINER_TIMESTAMP environment variables{Colors.ENDC}")

    # Start pipeline
    start_time = datetime.now()

    stats = run_pipeline(
        conference_dir=conference_dir,
        program_dir=program_dir,
        steps_to_run=steps_to_run,
        force=args.force,
        paper_delay=args.paper_delay,
        author_delay=args.author_delay
    )

    # Print summary
    print_summary(stats, start_time)

    # Exit with appropriate code
    sys.exit(0 if stats["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
