#!/usr/bin/env python3
"""
Merge multiple track JSON files into a single papers.json file.

This script scans a directory for JSON files containing paper data in a specific
format (with 'metadata' and 'papers' fields), merges all papers into a single
file, and generates comprehensive statistics about the merged data.

The script is designed to be reusable across different conferences and venues
that use the same JSON format for paper data.

Usage:
    python merge_tracks.py <input_dir> [options]

Example:
    # Merge all JSON files in the program directory
    python merge_tracks.py ../data/aaai-26/program

    # Specify custom output path
    python merge_tracks.py ../data/aaai-26/program -o ../data/aaai-26/all-papers.json

    # Filter files by pattern (e.g., only oral talks)
    python merge_tracks.py ../data/aaai-26/program --pattern "*oral-talks.json"
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


def get_project_root() -> Path:
    """Get the project root directory (grandparent of this script)."""
    return Path(__file__).parent.parent.parent.resolve()


def load_json_file(file_path: Path) -> dict:
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"{Colors.RED}Error parsing JSON file {file_path}: {e}{Colors.ENDC}")
        raise
    except Exception as e:
        print(f"{Colors.RED}Error reading file {file_path}: {e}{Colors.ENDC}")
        raise


def save_json_file(file_path: Path, data: dict) -> None:
    """Save data to a JSON file with proper formatting."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def validate_json_structure(data: dict, file_path: Path) -> bool:
    """
    Validate that JSON data has the expected structure.

    Expected structure:
    {
        "metadata": { ... },
        "papers": [ ... ]
    }
    """
    if not isinstance(data, dict):
        print(f"{Colors.YELLOW}Warning: {file_path.name} is not a JSON object{Colors.ENDC}")
        return False

    if 'metadata' not in data or 'papers' not in data:
        print(f"{Colors.YELLOW}Warning: {file_path.name} missing 'metadata' or 'papers' field{Colors.ENDC}")
        return False

    if not isinstance(data['papers'], list):
        print(f"{Colors.YELLOW}Warning: {file_path.name} 'papers' field is not a list{Colors.ENDC}")
        return False

    return True


def extract_track_info(file_path: Path, metadata: dict) -> Dict[str, any]:
    """
    Extract track information from file path and metadata.

    Returns a dictionary with track name and presentation type.
    """
    file_name = file_path.stem  # e.g., "aia-track-oral-talks"

    # Try to extract track from filename
    track_match = re.search(r'([a-zA-Z]+)-track', file_name)
    track_name = track_match.group(1).upper() if track_match else "UNKNOWN"

    # Try to determine presentation type
    if 'oral' in file_name.lower():
        presentation_type = 'oral'
    elif 'poster' in file_name.lower():
        presentation_type = 'poster'
    else:
        presentation_type = 'unknown'

    return {
        'file_name': file_path.name,
        'track': track_name,
        'presentation_type': presentation_type,
        'source': metadata.get('source', 'Unknown'),
        'source_url': metadata.get('source_url', '')
    }


def merge_papers(
    input_dir: Path,
    pattern: str = "*.json",
    deduplicate: bool = True
) -> Tuple[List[dict], List[Dict[str, any]], Set[str]]:
    """
    Merge papers from all matching JSON files in the input directory.

    Args:
        input_dir: Directory containing JSON files to merge
        pattern: Glob pattern for filtering files (default: "*.json")
        deduplicate: Whether to remove duplicate papers based on paper_id

    Returns:
        Tuple of (papers_list, sources_list, duplicate_ids)
    """
    json_files = sorted(input_dir.glob(pattern))

    if not json_files:
        print(f"{Colors.RED}No JSON files found in {input_dir} matching pattern '{pattern}'{Colors.ENDC}")
        return [], [], set()

    print(f"{Colors.CYAN}Found {len(json_files)} JSON files to merge{Colors.ENDC}\n")

    all_papers = []
    sources = []
    seen_paper_ids = set()
    duplicate_ids = set()

    for json_file in json_files:
        print(f"{Colors.DIM}Processing: {json_file.name}{Colors.ENDC}")

        data = load_json_file(json_file)

        # Validate structure
        if not validate_json_structure(data, json_file):
            continue

        # Extract track info
        track_info = extract_track_info(json_file, data['metadata'])
        papers = data['papers']

        # Track source information
        sources.append({
            **track_info,
            'paper_count': len(papers)
        })

        # Process papers
        added_count = 0
        for paper in papers:
            paper_id = paper.get('paper_id', '')

            if deduplicate and paper_id:
                if paper_id in seen_paper_ids:
                    duplicate_ids.add(paper_id)
                    print(f"{Colors.YELLOW}  Duplicate paper_id found: {paper_id}{Colors.ENDC}")
                    continue
                seen_paper_ids.add(paper_id)

            # Add source tracking to each paper
            paper['_source_file'] = json_file.name
            all_papers.append(paper)
            added_count += 1

        print(f"{Colors.GREEN}  Added {added_count} papers from {track_info['track']} ({track_info['presentation_type']}){Colors.ENDC}\n")

    return all_papers, sources, duplicate_ids


def generate_statistics(papers: List[dict], sources: List[Dict[str, any]]) -> Dict[str, any]:
    """Generate comprehensive statistics about the merged papers."""

    # Track statistics
    track_stats = {}
    presentation_stats = {}

    for source in sources:
        track = source['track']
        pres_type = source['presentation_type']
        count = source['paper_count']

        track_stats[track] = track_stats.get(track, 0) + count
        presentation_stats[pres_type] = presentation_stats.get(pres_type, 0) + count

    # AMiner validation statistics (optional - only if papers have this field)
    aminer_success = 0
    aminer_not_found = 0
    aminer_no_validation = 0
    has_aminer_data = False

    for paper in papers:
        if 'aminer_validation' in paper:
            has_aminer_data = True
            validation = paper.get('aminer_validation', {})
            status = validation.get('status', 'none')

            if status == 'success':
                aminer_success += 1
            elif status == 'not_found':
                aminer_not_found += 1
            else:
                aminer_no_validation += 1

    result = {
        'total_papers': len(papers),
        'total_sources': len(sources),
        'track_breakdown': track_stats,
        'presentation_breakdown': presentation_stats
    }

    # Only include AMiner stats if data exists
    if has_aminer_data:
        result['aminer_validation'] = {
            'success': aminer_success,
            'not_found': aminer_not_found,
            'no_validation': aminer_no_validation,
            'success_rate': f"{aminer_success / len(papers) * 100:.1f}%" if papers else "0%"
        }

    return result


def print_statistics(stats: Dict[str, any], duplicate_count: int) -> None:
    """Print formatted statistics to console."""
    print(f"\n{Colors.BOLD}=== Merge Statistics ==={Colors.ENDC}\n")

    print(f"{Colors.CYAN}Total Papers:{Colors.ENDC} {stats['total_papers']}")
    print(f"{Colors.CYAN}Total Sources:{Colors.ENDC} {stats['total_sources']}")

    if duplicate_count > 0:
        print(f"{Colors.YELLOW}Duplicates Removed:{Colors.ENDC} {duplicate_count}")

    print(f"\n{Colors.BOLD}Track Breakdown:{Colors.ENDC}")
    for track, count in sorted(stats['track_breakdown'].items()):
        percentage = count / stats['total_papers'] * 100
        print(f"  {track}: {count} ({percentage:.1f}%)")

    print(f"\n{Colors.BOLD}Presentation Type Breakdown:{Colors.ENDC}")
    for pres_type, count in sorted(stats['presentation_breakdown'].items()):
        percentage = count / stats['total_papers'] * 100
        print(f"  {pres_type}: {count} ({percentage:.1f}%)")

    # Only print AMiner stats if available
    if 'aminer_validation' in stats:
        aminer = stats['aminer_validation']
        print(f"\n{Colors.BOLD}AMiner Validation:{Colors.ENDC}")
        print(f"  Success: {aminer['success']} ({aminer['success_rate']})")
        print(f"  Not Found: {aminer['not_found']}")
        print(f"  No Validation: {aminer['no_validation']}")


def main():
    parser = argparse.ArgumentParser(
        description='Merge multiple track JSON files into a single papers.json file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'input_dir',
        type=Path,
        help='Directory containing JSON files to merge'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file path (default: <input_dir>/papers.json)'
    )

    parser.add_argument(
        '-p', '--pattern',
        default='*.json',
        help='Glob pattern for filtering input files (default: *.json)'
    )

    parser.add_argument(
        '--no-deduplicate',
        action='store_true',
        help='Do not remove duplicate papers (keep all occurrences)'
    )

    parser.add_argument(
        '--conference',
        help='Conference name for metadata (auto-detected from path if not provided)'
    )

    args = parser.parse_args()

    # Validate input directory
    if not args.input_dir.exists():
        print(f"{Colors.RED}Error: Input directory does not exist: {args.input_dir}{Colors.ENDC}")
        sys.exit(1)

    if not args.input_dir.is_dir():
        print(f"{Colors.RED}Error: Input path is not a directory: {args.input_dir}{Colors.ENDC}")
        sys.exit(1)

    # Determine output path
    output_path = args.output or (args.input_dir.parent / 'papers.json')

    # Auto-detect conference name from path
    conference_name = args.conference
    if not conference_name:
        # Try to extract from path (e.g., "aaai-26" from "data/aaai-26/program")
        for part in args.input_dir.parts:
            if re.match(r'[a-zA-Z]+-\d+', part):
                conference_name = part.upper()
                break
        if not conference_name:
            conference_name = "Unknown Conference"

    print(f"{Colors.BOLD}Merging papers from: {args.input_dir}{Colors.ENDC}")
    print(f"{Colors.BOLD}Output file: {output_path}{Colors.ENDC}\n")

    # Merge papers
    papers, sources, duplicate_ids = merge_papers(
        args.input_dir,
        pattern=args.pattern,
        deduplicate=not args.no_deduplicate
    )

    if not papers:
        print(f"{Colors.RED}No papers found to merge{Colors.ENDC}")
        sys.exit(1)

    # Generate statistics
    stats = generate_statistics(papers, sources)

    # Create merged data structure
    merged_data = {
        'metadata': {
            'conference': conference_name,
            'merged_at': datetime.now(timezone.utc).isoformat(),
            'total_papers': stats['total_papers'],
            'total_sources': stats['total_sources'],
            'sources': sources,
            'statistics': stats
        },
        'papers': papers
    }

    # Save merged file
    save_json_file(output_path, merged_data)

    # Print statistics
    print_statistics(stats, len(duplicate_ids))

    print(f"\n{Colors.GREEN}{Colors.BOLD}Successfully merged {stats['total_papers']} papers to: {output_path}{Colors.ENDC}")


if __name__ == '__main__':
    main()
