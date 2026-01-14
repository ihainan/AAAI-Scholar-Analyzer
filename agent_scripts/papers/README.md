# Papers Scripts

This directory contains scripts for processing and managing paper data across different conferences and venues.

## Scripts

### merge_tracks.py

Merge multiple track JSON files into a single consolidated papers.json file.

**Features:**
- Automatically detects and merges all JSON files in a directory
- Preserves source tracking information for each paper
- Removes duplicates based on paper_id
- Generates comprehensive statistics
- Supports custom filtering patterns
- Works with any conference using the same JSON format

**Usage:**

```bash
# Basic usage - merge all JSON files
python merge_tracks.py ../data/aaai-26/program

# Specify custom output path
python merge_tracks.py ../data/aaai-26/program -o ../data/aaai-26/all-papers.json

# Filter files by pattern (e.g., only oral talks)
python merge_tracks.py ../data/aaai-26/program --pattern "*oral-talks.json"

# Keep duplicate papers instead of removing them
python merge_tracks.py ../data/aaai-26/program --no-deduplicate

# Specify conference name
python merge_tracks.py ../data/aaai-26/program --conference "AAAI-26"
```

**Input Format:**

Each JSON file should have the following structure:

```json
{
  "metadata": {
    "source": "Track Name",
    "source_url": "...",
    "total_papers": 50
  },
  "papers": [
    {
      "paper_id": "AIA67",
      "title": "Paper Title",
      "authors": ["Author 1", "Author 2"],
      "track": "AIA",
      ...
    }
  ]
}
```

**Output Format:**

```json
{
  "metadata": {
    "conference": "AAAI-26",
    "merged_at": "2026-01-14T...",
    "total_papers": 2556,
    "total_sources": 7,
    "sources": [
      {
        "file_name": "aia-track-oral-talks.json",
        "track": "AIA",
        "presentation_type": "oral",
        "paper_count": 50
      }
    ],
    "statistics": {
      "track_breakdown": {...},
      "presentation_breakdown": {...},
      "aminer_validation": {...}
    }
  },
  "papers": [
    {
      "paper_id": "AIA67",
      "_source_file": "aia-track-oral-talks.json",
      ...
    }
  ]
}
```

**Statistics Generated:**

- Total papers and sources
- Track breakdown (papers per track)
- Presentation type breakdown (oral vs poster)
- AMiner validation statistics
- Duplicate detection

## Adding New Scripts

When adding new scripts to this directory:

1. Follow the existing code style and structure
2. Include comprehensive docstrings with usage examples
3. Use argparse for command-line arguments
4. Use the Colors class for terminal output
5. Add proper error handling
6. Update this README with script documentation
