#!/usr/bin/env python3
"""
Generate authors.json from AAAI program data and AMiner paper data.

This script extracts author information from conference program JSON files,
matches authors with AMiner IDs when available, and generates a comprehensive
authors database.

Usage:
    python generate_authors_data.py [--program-dir DIR] [--aminer-dir DIR] [--output FILE]
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
import argparse


class AuthorDataGenerator:
    """Generator for creating authors.json from program and AMiner data."""

    def __init__(self, program_dir: str, aminer_papers_dir: str):
        """
        Initialize the generator.

        Args:
            program_dir: Directory containing program JSON files
            aminer_papers_dir: Directory containing AMiner paper JSON files
        """
        self.program_dir = Path(program_dir)
        self.aminer_papers_dir = Path(aminer_papers_dir)

        # Data structures
        self.authors_data = defaultdict(lambda: {
            'papers': [],
            'collaborators': set(),
            'tracks': set(),
            'sources': set(),
            'source_urls': set()
        })

        # AMiner paper cache: {paper_id: paper_data}
        self.aminer_papers_cache = {}

    def load_aminer_papers(self) -> None:
        """Load all AMiner paper JSON files into cache."""
        print(f"Loading AMiner papers from {self.aminer_papers_dir}...")

        json_files = list(self.aminer_papers_dir.glob("*.json"))
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    aminer_id = data.get('aminer_id')
                    if aminer_id:
                        self.aminer_papers_cache[aminer_id] = data
            except Exception as e:
                print(f"Warning: Failed to load {json_file}: {e}")

        print(f"Loaded {len(self.aminer_papers_cache)} AMiner papers")

    def extract_source_url_from_md(self, md_file: Path) -> Optional[str]:
        """
        Extract source_url from markdown file frontmatter.

        Args:
            md_file: Path to markdown file

        Returns:
            Source URL if found, None otherwise
        """
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                in_frontmatter = False
                for line in lines:
                    if line.strip() == '---':
                        if not in_frontmatter:
                            in_frontmatter = True
                        else:
                            break
                    elif in_frontmatter and line.startswith('source_url:'):
                        return line.split('source_url:', 1)[1].strip()
        except Exception as e:
            print(f"Warning: Failed to extract URL from {md_file}: {e}")

        return None

    def process_program_file(self, json_file: Path) -> None:
        """
        Process a single program JSON file.

        Args:
            json_file: Path to program JSON file
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            papers = data.get('papers', [])

            # Get source URL from corresponding markdown file
            md_file = json_file.with_suffix('.md')
            source_url = None
            if md_file.exists():
                source_url = self.extract_source_url_from_md(md_file)

            # Relative path for sources field
            relative_source = f"program/{json_file.name}"

            for paper in papers:
                authors = paper.get('authors', [])
                track = paper.get('track') or 'Unknown'

                # Paper information
                paper_info = {
                    'paper_id': paper.get('paper_id'),
                    'title': paper.get('title'),
                    'track': track,
                    'session': paper.get('session'),
                    'date': paper.get('date'),
                    'room': paper.get('room')
                }

                # AMiner paper ID if available
                aminer_paper_id = paper.get('aminer_paper_id')
                if aminer_paper_id:
                    paper_info['aminer_paper_id'] = aminer_paper_id

                # Process each author
                for author_name in authors:
                    author_data = self.authors_data[author_name]

                    # Add paper
                    author_data['papers'].append(paper_info)

                    # Add track
                    author_data['tracks'].add(track)

                    # Add collaborators (all other authors)
                    for other_author in authors:
                        if other_author != author_name:
                            author_data['collaborators'].add(other_author)

                    # Add source
                    author_data['sources'].add(relative_source)

                    # Add source URL
                    if source_url:
                        author_data['source_urls'].add(source_url)

        except Exception as e:
            print(f"Error processing {json_file}: {e}")

    def match_aminer_id(self, author_name: str, papers: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Try to match author with AMiner ID through their papers.

        Args:
            author_name: Name of the author
            papers: List of papers by this author

        Returns:
            Dict with aminer_id and validation info, or None if no match
        """
        for paper in papers:
            aminer_paper_id = paper.get('aminer_paper_id')
            if not aminer_paper_id:
                continue

            # Get AMiner paper data
            aminer_paper = self.aminer_papers_cache.get(aminer_paper_id)
            if not aminer_paper:
                continue

            # Try to match author name
            aminer_authors = aminer_paper.get('detail', {}).get('authors', [])
            for aminer_author in aminer_authors:
                aminer_author_name = aminer_author.get('name', '')
                aminer_author_id = aminer_author.get('id')

                # Simple name matching (exact match for now)
                if aminer_author_name == author_name and aminer_author_id:
                    return {
                        'aminer_id': aminer_author_id,
                        'aminer_validation': {
                            'status': 'success',
                            'matched_via': f"paper:{paper['paper_id']},aminer_paper:{aminer_paper_id}",
                            'confidence': 'high',
                            'matched_at': datetime.now().isoformat()
                        },
                        'affiliation': aminer_author.get('org')  # May be None
                    }

        return None

    def generate_description(self, author_name: str, author_data: Dict) -> str:
        """
        Generate description for an author.

        Args:
            author_name: Name of the author
            author_data: Author's data including papers, collaborators, etc.

        Returns:
            Generated description text
        """
        papers = author_data['papers']
        tracks = sorted([t for t in author_data['tracks'] if t is not None])
        collaborators = sorted(list(author_data['collaborators']))[:5]  # Top 5

        # Build description
        desc_parts = [
            f"{author_name} is an author at AAAI-26"
        ]

        # Paper count and tracks
        paper_count = len(papers)
        if paper_count == 1:
            desc_parts.append(f"presenting 1 paper in the {tracks[0]} track")
        else:
            track_str = ", ".join(tracks)
            desc_parts.append(f"presenting {paper_count} papers across {track_str} track{'s' if len(tracks) > 1 else ''}")

        description = ", ".join(desc_parts) + "."

        # Add collaborators
        if collaborators:
            collab_str = ", ".join(collaborators)
            if len(author_data['collaborators']) > 5:
                collab_str += ", and others"
            description += f" Collaborating with {collab_str}."

        return description

    def generate_authors_json(self) -> Dict:
        """
        Generate the final authors.json structure.

        Returns:
            Dictionary ready to be serialized as JSON
        """
        talents = []

        print(f"\nProcessing {len(self.authors_data)} authors...")

        for author_name in sorted(self.authors_data.keys()):
            author_data = self.authors_data[author_name]

            # Build talent entry
            # Filter out None values and sort tracks
            valid_tracks = sorted([t for t in author_data['tracks'] if t is not None])
            talent = {
                'name': author_name,
                'roles': [f"{track} Track Author" for track in valid_tracks]
            }

            # Add papers
            talent['papers'] = author_data['papers']

            # Add statistics
            talent['statistics'] = {
                'total_papers': len(author_data['papers']),
                'tracks': valid_tracks,
                'collaborators_count': len(author_data['collaborators'])
            }

            # Add collaborators
            if author_data['collaborators']:
                talent['collaborators'] = sorted(list(author_data['collaborators']))

            # Generate description
            talent['description'] = self.generate_description(author_name, author_data)

            # Add sources
            talent['sources'] = sorted(author_data['sources'])
            talent['source_urls'] = sorted(author_data['source_urls'])

            # Try to match AMiner ID
            aminer_match = self.match_aminer_id(author_name, author_data['papers'])
            if aminer_match:
                talent['aminer_id'] = aminer_match['aminer_id']
                talent['aminer_validation'] = aminer_match['aminer_validation']

                # Add affiliation if available
                if aminer_match.get('affiliation'):
                    talent['affiliation'] = aminer_match['affiliation']

            talents.append(talent)

        # Build final structure
        result = {
            'metadata': {
                'description': 'AAAI-26 Authors Information',
                'conference': 'AAAI-26',
                'dates': 'January 20-27, 2026',
                'location': 'Singapore EXPO, Singapore',
                'extracted_from': 'AAAI 2026 Program Schedule',
                'extraction_date': datetime.now().strftime('%Y-%m-%d'),
                'total_authors': len(talents),
                'base_path': 'data/aaai-26'
            },
            'authors': talents
        }

        return result

    def run(self, output_file: str) -> None:
        """
        Run the full pipeline to generate authors.json.

        Args:
            output_file: Path to output JSON file
        """
        print("Starting author data generation...")

        # Step 1: Load AMiner papers
        self.load_aminer_papers()

        # Step 2: Process all program JSON files
        print(f"\nProcessing program files from {self.program_dir}...")
        json_files = list(self.program_dir.glob("*.json"))
        for json_file in json_files:
            print(f"  Processing {json_file.name}...")
            self.process_program_file(json_file)

        # Step 3: Generate final JSON
        print("\nGenerating authors.json...")
        result = self.generate_authors_json()

        # Step 4: Write output
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Successfully generated {output_file}")
        print(f"  Total authors: {result['metadata']['total_authors']}")

        # Print statistics
        aminer_matched = sum(1 for author in result['authors'] if 'aminer_id' in author)
        print(f"  Authors with AMiner ID: {aminer_matched}")
        print(f"  Match rate: {aminer_matched/result['metadata']['total_authors']*100:.1f}%")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate authors.json from AAAI program and AMiner data'
    )
    parser.add_argument(
        '--program-dir',
        default='data/aaai-26/program',
        help='Directory containing program JSON files (default: data/aaai-26/program)'
    )
    parser.add_argument(
        '--aminer-dir',
        default='data/aminer/papers',
        help='Directory containing AMiner paper JSON files (default: data/aminer/papers)'
    )
    parser.add_argument(
        '--output',
        default='data/aaai-26/authors.json',
        help='Output file path (default: data/aaai-26/authors.json)'
    )

    args = parser.parse_args()

    # Create generator and run
    generator = AuthorDataGenerator(args.program_dir, args.aminer_dir)
    generator.run(args.output)


if __name__ == '__main__':
    main()
