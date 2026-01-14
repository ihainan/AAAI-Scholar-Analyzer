# Papers Scripts

This directory contains scripts for processing paper and author data for academic conferences. The scripts form a complete pipeline from merging track files to generating optimized indexes for frontend queries.

## Pipeline Overview

```
Track JSON files (program/*.json)
    ↓
[1. merge_tracks.py]
    ↓
papers.json
    ↓
[2. enrich_papers_aminer.py]
    ↓
papers.json (with AMiner IDs) + aminer/papers/*.json
    ↓
[3. enrich_authors_aminer.py]
    ↓
authors.json + aminer/authors/*.json
    ↓
[4. generate_indexes.py]
    ↓
indexes/*.json (optimized for frontend)
```

## Quick Start

### Run Complete Pipeline

```bash
# Set AMiner API credentials
export AMINER_AUTH="Bearer xxx"
export AMINER_SIGNATURE="xxx"
export AMINER_TIMESTAMP="xxx"

# Run full pipeline
cd agent_scripts/papers
python build_pipeline.py ../../data/aaai-26
```

### Run Individual Steps

```bash
# 1. Merge tracks
python merge_tracks.py ../../data/aaai-26/program

# 2. Enrich papers with AMiner data
python enrich_papers_aminer.py ../../data/aaai-26/papers.json

# 3. Extract and enrich authors
python enrich_authors_aminer.py ../../data/aaai-26/papers.json

# 4. Generate indexes
python generate_indexes.py ../../data/aaai-26
```

## Scripts

### 1. merge_tracks.py

Merge multiple track JSON files into a single `papers.json` file.

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
```

**Input:** Directory with track JSON files
**Output:** `papers.json` with merged data

### 2. enrich_papers_aminer.py

Enrich `papers.json` with AMiner data by searching for each paper and fetching detailed information.

**Features:**
- Searches AMiner by paper title
- Adds `aminer_paper_id` to papers.json
- Persists detailed data to `aminer/papers/{paper_id}.json`
- Skips papers already enriched (unless `--force`)
- Marks not_found papers to avoid re-searching
- Rate limiting support

**Usage:**

```bash
# Basic usage (skip papers that already have AMiner ID)
python enrich_papers_aminer.py ../../data/aaai-26/papers.json

# Force refresh all papers including those marked as not_found
python enrich_papers_aminer.py ../../data/aaai-26/papers.json --force

# Process specific papers only
python enrich_papers_aminer.py ../../data/aaai-26/papers.json --paper-ids AIA67 MAIN123

# Custom delay between API calls
python enrich_papers_aminer.py ../../data/aaai-26/papers.json --delay 2.0
```

**Input:** `papers.json`
**Output:** Updated `papers.json` + `aminer/papers/*.json`

### 3. enrich_authors_aminer.py

Extract all authors from `papers.json` and enrich with AMiner data via local data-proxy API.

**Features:**
- Extracts unique authors from papers
- Searches AMiner by author name
- Only includes authors found on AMiner (with AMiner ID)
- Uses AMiner ID as unique identifier
- Generates `authors.json` with author details
- Persists detailed data to `aminer/authors/{aminer_id}.json`
- Supports incremental updates
- Rate limiting support

**Usage:**

```bash
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

# Force refresh all authors
python enrich_authors_aminer.py ../../data/aaai-26/papers.json --force

# Custom delay
python enrich_authors_aminer.py ../../data/aaai-26/papers.json --delay 3.0
```

**Input:** `papers.json`
**Output:** `authors.json` + `aminer/authors/*.json`
**Requirements:** AMiner API credentials (via environment variables or command line)

### 4. generate_indexes.py

Generate optimized index files for fast frontend queries.

**Features:**
- Creates lightweight indexes for common queries
- Generates multiple index types
- Computes overall statistics
- Optimizes for frontend performance

**Generated Indexes:**
- `papers_by_author.json` - Map author names to paper IDs
- `authors_with_aminer.json` - Lightweight list of authors with AMiner IDs
- `papers_by_track.json` - Map tracks to paper IDs
- `stats.json` - Overall statistics

**Usage:**

```bash
# Generate all indexes
python generate_indexes.py ../../data/aaai-26

# Generate specific indexes only
python generate_indexes.py ../../data/aaai-26 --types papers_by_author authors_with_aminer
```

**Input:** `papers.json` and `authors.json`
**Output:** `indexes/*.json`

### 5. build_pipeline.py

Run the complete data processing pipeline with one command.

**Features:**
- Executes all steps in correct order
- Progress tracking and error handling
- Support for resuming from specific step
- Support for running only specific steps
- Configurable delays for rate limiting

**Usage:**

```bash
# Run full pipeline
python build_pipeline.py ../../data/aaai-26

# Start from a specific step
python build_pipeline.py ../../data/aaai-26 --start-from enrich-authors

# Run only specific steps
python build_pipeline.py ../../data/aaai-26 --steps merge enrich-papers

# Force re-processing with custom delays
python build_pipeline.py ../../data/aaai-26 --force --paper-delay 2.0 --author-delay 3.0
```

**Pipeline Steps:**
1. `merge` - Merge track JSON files
2. `enrich-papers` - Enrich papers with AMiner data
3. `enrich-authors` - Extract and enrich authors
4. `generate-indexes` - Generate index files

## Data Structure

### Input Format (Track JSON)

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
      "date": "...",
      "session": "...",
      "room": "..."
    }
  ]
}
```

### Output Format (papers.json)

```json
{
  "metadata": {
    "conference": "AAAI-26",
    "merged_at": "2026-01-14T...",
    "total_papers": 2513,
    "total_sources": 7,
    "sources": [...],
    "statistics": {...}
  },
  "papers": [
    {
      "paper_id": "AIA67",
      "title": "...",
      "authors": ["Author 1", "Author 2"],
      "track": "AIA",
      "aminer_paper_id": "67eb4a10...",
      "aminer_validation": {
        "status": "success",
        "matched_at": "2026-01-14T..."
      },
      "_source_file": "aia-track-oral-talks.json"
    }
  ]
}
```

### Output Format (authors.json)

```json
{
  "metadata": {
    "total_authors": 2800,
    "generated_at": "2026-01-14T...",
    "source": "papers.json"
  },
  "authors": [
    {
      "name": "Alice Smith",
      "normalized_name": "alice smith",
      "aminer_id": "53f46a3c...",
      "aminer_name": "Alice Smith",
      "aminer_name_zh": "...",
      "papers": ["AIA67", "MAIN123"],
      "paper_count": 2,
      "h_index": 25,
      "n_citation": 1500,
      "n_pubs": 100,
      "organization": "MIT",
      "position": "Professor"
    }
  ]
}
```

### Directory Structure After Pipeline

```
data/
├── aminer/                          # AMiner cache (global, shared across conferences)
│   ├── papers/
│   │   └── {aminer_id}.json        # Detailed paper data (by AMiner ID)
│   └── scholars/
│       └── {aminer_id}.json        # Scholar AMiner data (by AMiner ID)
│
├── enriched/                        # Enriched data cache (global)
│   └── scholars/
│       └── {aminer_id}.json        # Scholar enriched data (indices, etc.)
│
└── aaai-26/                         # Conference-specific data
    ├── papers.json                  # All papers with AMiner IDs
    ├── authors.json                 # All authors with AMiner IDs
    └── indexes/
        ├── papers_by_author.json    # Author → Paper IDs mapping
        ├── authors_with_aminer.json # Lightweight author list
        ├── papers_by_track.json     # Track → Paper IDs mapping
        └── stats.json               # Overall statistics
```

## Frontend Integration

The generated data structure is optimized for frontend performance:

1. **Papers List Page**: Load `papers.json` (1-2MB) for all paper info
2. **Paper Detail Page**: Load `data/aminer/papers/{aminer_id}.json` on demand
3. **Authors List Page**: Load `indexes/authors_with_aminer.json` (lightweight)
4. **Author Detail Page**:
   - Load `data/aminer/scholars/{aminer_id}.json` for basic info (name, bio, orgs)
   - Load `data/enriched/scholars/{aminer_id}.json` for metrics (h-index, citations)
5. **Statistics Dashboard**: Load `indexes/stats.json`

## Common Workflows

### Initial Setup for New Conference

```bash
# 1. Run complete pipeline
python build_pipeline.py ../../data/new-conference-26

# This will:
# - Merge all track files
# - Enrich papers with AMiner
# - Extract and enrich authors
# - Generate indexes
```

### Update Existing Data

```bash
# Update papers only
python enrich_papers_aminer.py ../../data/aaai-26/papers.json --force

# Update authors only
python enrich_authors_aminer.py ../../data/aaai-26/papers.json --force

# Regenerate indexes
python generate_indexes.py ../../data/aaai-26
```

### Process Specific Papers/Authors

```bash
# Specific papers
python enrich_papers_aminer.py ../../data/aaai-26/papers.json --paper-ids AIA67 MAIN123

# Specific authors (process all, filter happens automatically)
python enrich_authors_aminer.py ../../data/aaai-26/papers.json
```

## Error Handling

- **Papers not found on AMiner**: Marked with `aminer_validation.status = "not_found"`, won't be searched again unless `--force`
- **API failures**: Marked with `aminer_validation.status = "failed"`, can be retried
- **Missing credentials**: Author enrichment will be skipped with warning
- **Pipeline failures**: Pipeline stops on first error, can be resumed with `--start-from`

## Performance Considerations

- **Rate Limiting**: Use `--delay` to control API request rate
  - Papers: Default 1.0s (can handle ~3600 papers/hour)
  - Authors: Default 2.0s (can handle ~1800 authors/hour)
- **Incremental Updates**: Scripts skip already processed items by default
- **Caching**: AMiner API uses 15-day cache, use `--force-refresh` to bypass
- **Parallel Processing**: Not currently supported, but can be added if needed

## Troubleshooting

### AMiner credentials not working

```bash
# Verify credentials are set
echo $AMINER_AUTH
echo $AMINER_SIGNATURE
echo $AMINER_TIMESTAMP

# Check for whitespace/newlines
echo "$AMINER_AUTH" | od -c
```

### Pipeline fails at author enrichment

```bash
# Check if data-proxy API is running
curl http://localhost:37804/health

# Run author enrichment separately with verbose output
python enrich_authors_aminer.py ../../data/aaai-26/papers.json -v
```

### Papers not matching on AMiner

- Check paper title formatting
- Try manual search on AMiner website
- Some papers may not be indexed yet

## Development

### Adding New Index Types

Edit `generate_indexes.py` and add your index generation function:

```python
def generate_my_custom_index(papers: list[dict]) -> dict:
    # Your index logic here
    return index_data
```

### Extending Pipeline

Add new step to `build_pipeline.py`:

```python
PIPELINE_STEPS.append({
    "id": "my-step",
    "name": "My Custom Step",
    "script": "my_script.py",
    "description": "What it does",
    "requires": ["input files"],
    "produces": ["output files"]
})
```

## See Also

- [USAGE_EXAMPLES.md](./USAGE_EXAMPLES.md) - Detailed usage examples
- [../README.md](../README.md) - Main agent_scripts documentation
- [AMiner API Documentation](https://www.aminer.cn/api_cn) - AMiner API reference
