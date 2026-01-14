# merge_tracks.py Usage Examples

This document provides practical examples for using the `merge_tracks.py` script with different scenarios.

## Example 1: Basic Usage (AAAI-26)

Merge all JSON files in the AAAI-26 program directory:

```bash
cd agent_scripts/papers
python merge_tracks.py ../../data/aaai-26/program
```

**Output:**
- Creates `data/aaai-26/papers.json` with 2,513 papers
- Automatically detects and removes 43 duplicates
- Generates statistics for tracks and presentation types

## Example 2: Custom Output Location

Save the merged file to a different location:

```bash
python merge_tracks.py ../../data/aaai-26/program \
  -o ../../data/aaai-26/all-papers-merged.json
```

## Example 3: Filter Specific File Types

Merge only oral presentation files:

```bash
python merge_tracks.py ../../data/aaai-26/program \
  --pattern "*oral-talks.json"
```

Merge only poster presentation files:

```bash
python merge_tracks.py ../../data/aaai-26/program \
  --pattern "*poster-presentations.json"
```

## Example 4: Keep Duplicates

If you want to keep all papers including duplicates:

```bash
python merge_tracks.py ../../data/aaai-26/program \
  --no-deduplicate
```

**Note:** This will include all 2,556 papers (43 duplicates retained).

## Example 5: Using with Other Conferences

The script is designed to work with any conference using the same JSON format.

### Future Conference (e.g., NeurIPS-25)

```bash
# Assuming directory structure: data/neurips-25/tracks/
python merge_tracks.py ../../data/neurips-25/tracks \
  --conference "NeurIPS-25"
```

### Custom Conference with Different Naming

```bash
# For conferences with different file naming patterns
python merge_tracks.py ../../data/icml-25/sessions \
  --pattern "track-*.json" \
  --conference "ICML-25"
```

## Example 6: Integration with Other Scripts

### After Merging, Process with AMiner

```bash
# 1. Merge all tracks
python merge_tracks.py ../../data/aaai-26/program

# 2. Fetch AMiner data for papers
cd ..
python fetch_paper_data.py ../data/aaai-26/papers.json
```

### Generate Author Statistics

```bash
# 1. Merge papers
cd papers
python merge_tracks.py ../../data/aaai-26/program

# 2. Generate author data
cd ..
python generate_authors_data.py ../data/aaai-26/papers.json
```

## Understanding the Output

### Merged File Structure

```json
{
  "metadata": {
    "conference": "AAAI-26",              // Auto-detected or specified
    "merged_at": "2026-01-14T...",        // Timestamp
    "total_papers": 2513,                 // After deduplication
    "total_sources": 7,                   // Number of source files
    "sources": [                          // Detailed source tracking
      {
        "file_name": "aia-track-oral-talks.json",
        "track": "AIA",
        "presentation_type": "oral",
        "source": "AAAI-26 Aia Track Oral Talks",
        "source_url": "https://...",
        "paper_count": 50
      }
    ],
    "statistics": {                       // Comprehensive stats
      "track_breakdown": {...},
      "presentation_breakdown": {...},
      "aminer_validation": {...}
    }
  },
  "papers": [                             // All merged papers
    {
      "paper_id": "AIA67",
      "title": "...",
      "track": "AIA",
      "_source_file": "aia-track-oral-talks.json",  // Source tracking
      ...
    }
  ]
}
```

### Statistics Output

```
=== Merge Statistics ===

Total Papers: 2513
Total Sources: 7
Duplicates Removed: 43

Track Breakdown:
  AIA: 80 (3.2%)
  AISI: 107 (4.3%)
  ETA: 10 (0.4%)
  MAIN: 2359 (93.9%)

Presentation Type Breakdown:
  oral: 1171 (46.6%)
  poster: 1385 (55.1%)

AMiner Validation:
  Success: 1354 (53.9%)
  Not Found: 1104
  No Validation: 55
```

## Common Issues and Solutions

### Issue 1: No JSON files found

**Error:** `No JSON files found in data/aaai-26/program matching pattern '*.json'`

**Solution:** Check the directory path and ensure JSON files exist.

### Issue 2: Invalid JSON structure

**Warning:** `Warning: file.json missing 'metadata' or 'papers' field`

**Solution:** Verify the JSON file follows the expected structure. The script will skip invalid files and continue processing valid ones.

### Issue 3: Duplicate paper IDs

**Output:** `Duplicate paper_id found: 921`

**Solution:** This is informational only. The script automatically handles duplicates by keeping the first occurrence (unless `--no-deduplicate` is used).

## Tips

1. **Always review the statistics** after merging to ensure the output matches your expectations.

2. **Use filtering patterns** when you only need specific subsets of papers (e.g., only oral talks).

3. **Source tracking** - Each paper includes `_source_file` field to trace its origin.

4. **Conference auto-detection** works by finding patterns like "aaai-26" in the path. If detection fails, use `--conference` to specify manually.

5. **Backup important data** before running merge operations, although the script doesn't modify source files.

6. **Check for duplicates** - The script reports all duplicates found. Review if the count seems unexpectedly high.
