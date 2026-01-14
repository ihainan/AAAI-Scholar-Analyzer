#!/usr/bin/env python3
"""
Generate index files for optimized frontend queries.

This script reads papers.json and authors.json to generate various index files
that enable fast lookups and queries on the frontend without loading full data.

Generated indexes:
- papers_by_author.json: Map author names to their paper IDs
- authors_with_aminer.json: Lightweight list of authors with AMiner IDs
- papers_by_track.json: Map tracks to their paper IDs
- stats.json: Overall statistics

Usage:
    python generate_indexes.py <conference_dir> [options]

Example:
    # Generate all indexes
    python generate_indexes.py ../../data/aaai-26

    # Generate specific indexes only
    python generate_indexes.py ../../data/aaai-26 --types papers_by_author authors_with_aminer
"""

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for common_utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from common_utils import (
    Colors,
    load_json_file,
    save_json_file,
)


def generate_papers_by_author_index(papers: list[dict]) -> dict:
    """
    Generate index mapping author names to paper IDs.

    Args:
        papers: List of paper dictionaries

    Returns:
        Dictionary mapping author_name (lowercase) -> list of paper_ids
    """
    author_papers = defaultdict(list)

    for paper in papers:
        paper_id = paper.get("paper_id")
        authors = paper.get("authors", [])

        for author in authors:
            if author:
                # Use lowercase for consistent lookups
                author_key = author.lower()
                author_papers[author_key].append(paper_id)

    return dict(author_papers)


def generate_authors_with_aminer_index(authors: list[dict]) -> dict:
    """
    Generate lightweight index of authors with AMiner IDs.

    Args:
        authors: List of author dictionaries from authors.json

    Returns:
        Dictionary with metadata and lightweight author list
    """
    lightweight_authors = []

    for author in authors:
        lightweight_authors.append({
            "name": author.get("name"),
            "aminer_id": author.get("aminer_id"),
            "paper_count": author.get("paper_count", 0),
            "h_index": author.get("h_index", 0),
            "n_citation": author.get("n_citation", 0),
            "organization": author.get("organization", "")
        })

    return {
        "metadata": {
            "total": len(lightweight_authors),
            "generated_at": datetime.now(timezone.utc).isoformat()
        },
        "authors": lightweight_authors
    }


def generate_papers_by_track_index(papers: list[dict]) -> dict:
    """
    Generate index mapping tracks to paper IDs.

    Args:
        papers: List of paper dictionaries

    Returns:
        Dictionary mapping track_name -> list of paper_ids
    """
    track_papers = defaultdict(list)

    for paper in papers:
        paper_id = paper.get("paper_id")
        track = paper.get("track")

        if track:
            track_papers[track].append(paper_id)

    return dict(track_papers)


def generate_stats(papers: list[dict], authors: list[dict]) -> dict:
    """
    Generate overall statistics.

    Args:
        papers: List of paper dictionaries
        authors: List of author dictionaries

    Returns:
        Dictionary containing various statistics
    """
    # Track statistics
    track_counts = defaultdict(int)
    presentation_counts = defaultdict(int)
    aminer_status_counts = defaultdict(int)

    for paper in papers:
        track = paper.get("track")
        if track:
            track_counts[track] += 1

        # Try to infer presentation type from _source_file
        source_file = paper.get("_source_file", "")
        if "oral" in source_file.lower():
            presentation_counts["oral"] += 1
        elif "poster" in source_file.lower():
            presentation_counts["poster"] += 1
        else:
            presentation_counts["unknown"] += 1

        # AMiner validation status
        validation = paper.get("aminer_validation", {})
        status = validation.get("status", "none")
        aminer_status_counts[status] += 1

    # Author statistics
    total_authors_with_aminer = len(authors)
    avg_papers_per_author = sum(a.get("paper_count", 0) for a in authors) / total_authors_with_aminer if total_authors_with_aminer > 0 else 0

    # Calculate average h-index (filter out None values)
    h_indices = [a.get("h_index") for a in authors if a.get("h_index") is not None]
    avg_h_index = sum(h_indices) / len(h_indices) if h_indices else 0

    # Top authors by h-index (filter out None values)
    top_authors_by_hindex = sorted(
        [a for a in authors if a.get("h_index") is not None],
        key=lambda x: x.get("h_index"),
        reverse=True
    )[:10]

    top_authors_list = [
        {
            "name": a.get("name"),
            "aminer_id": a.get("aminer_id"),
            "h_index": a.get("h_index"),
            "paper_count": a.get("paper_count", 0)
        }
        for a in top_authors_by_hindex
    ]

    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat()
        },
        "papers": {
            "total": len(papers),
            "with_aminer_id": aminer_status_counts.get("success", 0),
            "without_aminer_id": aminer_status_counts.get("not_found", 0) + aminer_status_counts.get("failed", 0),
            "by_track": dict(track_counts),
            "by_presentation": dict(presentation_counts),
            "by_aminer_status": dict(aminer_status_counts)
        },
        "authors": {
            "total_with_aminer": total_authors_with_aminer,
            "avg_papers_per_author": round(avg_papers_per_author, 2),
            "avg_h_index": round(avg_h_index, 2),
            "top_by_hindex": top_authors_list
        }
    }


def generate_indexes(
    conference_dir: Path,
    index_types: list[str] = None
) -> dict:
    """
    Generate all or specific index files.

    Args:
        conference_dir: Conference directory containing papers.json and authors.json
        index_types: List of index types to generate (None = all)

    Returns:
        Statistics about generated indexes
    """
    papers_json = conference_dir / "papers.json"
    authors_json = conference_dir / "authors.json"
    indexes_dir = conference_dir / "indexes"

    # Validate input files
    if not papers_json.exists():
        print(f"{Colors.RED}Error: papers.json not found at {papers_json}{Colors.ENDC}")
        sys.exit(1)

    authors_exist = authors_json.exists()
    if not authors_exist:
        print(f"{Colors.YELLOW}Warning: authors.json not found at {authors_json}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Will skip author-related indexes{Colors.ENDC}\n")

    # Load data
    print(f"Loading papers.json...")
    papers_data = load_json_file(papers_json)
    papers = papers_data.get("papers", [])
    print(f"  Loaded {len(papers)} papers\n")

    authors = []
    if authors_exist:
        print(f"Loading authors.json...")
        authors_data = load_json_file(authors_json)
        authors = authors_data.get("authors", [])
        print(f"  Loaded {len(authors)} authors\n")

    # Ensure indexes directory exists
    indexes_dir.mkdir(parents=True, exist_ok=True)

    # Determine which indexes to generate
    all_types = ["papers_by_author", "authors_with_aminer", "papers_by_track", "stats"]
    if index_types:
        types_to_generate = [t for t in index_types if t in all_types]
    else:
        types_to_generate = all_types

    # Skip author-related indexes if authors.json doesn't exist
    if not authors_exist:
        types_to_generate = [t for t in types_to_generate if t not in ["authors_with_aminer"]]

    stats = {
        "generated": [],
        "skipped": []
    }

    # Generate papers_by_author
    if "papers_by_author" in types_to_generate:
        print(f"{Colors.CYAN}Generating papers_by_author.json...{Colors.ENDC}")
        index_data = generate_papers_by_author_index(papers)
        output_path = indexes_dir / "papers_by_author.json"
        save_json_file(output_path, index_data)
        print(f"{Colors.GREEN}  Generated with {len(index_data)} authors{Colors.ENDC}\n")
        stats["generated"].append("papers_by_author")

    # Generate authors_with_aminer
    if "authors_with_aminer" in types_to_generate and authors_exist:
        print(f"{Colors.CYAN}Generating authors_with_aminer.json...{Colors.ENDC}")
        index_data = generate_authors_with_aminer_index(authors)
        output_path = indexes_dir / "authors_with_aminer.json"
        save_json_file(output_path, index_data)
        print(f"{Colors.GREEN}  Generated with {len(authors)} authors{Colors.ENDC}\n")
        stats["generated"].append("authors_with_aminer")

    # Generate papers_by_track
    if "papers_by_track" in types_to_generate:
        print(f"{Colors.CYAN}Generating papers_by_track.json...{Colors.ENDC}")
        index_data = generate_papers_by_track_index(papers)
        output_path = indexes_dir / "papers_by_track.json"
        save_json_file(output_path, index_data)
        print(f"{Colors.GREEN}  Generated with {len(index_data)} tracks{Colors.ENDC}\n")
        stats["generated"].append("papers_by_track")

    # Generate stats
    if "stats" in types_to_generate:
        print(f"{Colors.CYAN}Generating stats.json...{Colors.ENDC}")
        stats_data = generate_stats(papers, authors)
        output_path = indexes_dir / "stats.json"
        save_json_file(output_path, stats_data)
        print(f"{Colors.GREEN}  Generated statistics{Colors.ENDC}\n")
        stats["generated"].append("stats")

    return stats


def print_summary(stats: dict) -> None:
    """Print generation summary."""
    print("=" * 60)
    print(f"{Colors.BOLD}Index Generation Summary{Colors.ENDC}")
    print("=" * 60)
    print(f"Generated: {len(stats['generated'])}")
    for index_type in stats["generated"]:
        print(f"  {Colors.GREEN}✓{Colors.ENDC} {index_type}")

    if stats["skipped"]:
        print(f"\nSkipped: {len(stats['skipped'])}")
        for index_type in stats["skipped"]:
            print(f"  {Colors.YELLOW}-{Colors.ENDC} {index_type}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate index files for optimized frontend queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "conference_dir",
        type=str,
        help="Conference directory containing papers.json and authors.json"
    )

    parser.add_argument(
        "--types",
        nargs="+",
        choices=["papers_by_author", "authors_with_aminer", "papers_by_track", "stats"],
        help="Specific index types to generate (default: all)"
    )

    args = parser.parse_args()

    # Resolve directory path
    conference_dir = Path(args.conference_dir).resolve()
    if not conference_dir.exists():
        print(f"{Colors.RED}Error: Directory not found: {conference_dir}{Colors.ENDC}")
        sys.exit(1)

    if not conference_dir.is_dir():
        print(f"{Colors.RED}Error: Not a directory: {conference_dir}{Colors.ENDC}")
        sys.exit(1)

    print(f"{Colors.BOLD}Generate Indexes{Colors.ENDC}")
    print(f"Conference directory: {conference_dir}")
    if args.types:
        print(f"Index types: {', '.join(args.types)}")
    else:
        print(f"Index types: all")
    print()

    # Generate indexes
    stats = generate_indexes(
        conference_dir=conference_dir,
        index_types=args.types
    )

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
