---
name: aminer-paper
description: Query academic paper information from AMiner, including paper search, advanced search with filters, and paper details. Use when user asks about academic papers, research publications, or specific paper information.
---

# AMiner Paper Query

This skill provides access to AMiner's paper database APIs for searching and retrieving detailed information about academic papers.

**IMPORTANT: All commands MUST be executed with `python` prefix. Do NOT run the script directly without `python`.**

## Prerequisites

The `AMINER_API_KEY` environment variable must be set with a valid AMiner API key.

## Available Commands

### 1. Paper Search (Basic)

Search for papers by title. This is the basic search interface with limited filtering options.

```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search --title "<title>" [--page <n>] [--size <n>]
```

**Parameters:**
- `--title`: Paper title to search for (required)
- `--page`: Page number starting from 0 (default: 0)
- `--size`: Results per page (default: 10, **maximum: 20**)

**Example:**
```bash
# Search for papers about LongSplat
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search --title "LongSplat"

# Search with pagination
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search --title "neural network" --page 1 --size 20
```

**Response fields:**
- `id`: Paper ID
- `title`: Paper title in English
- `title_zh`: Paper title in Chinese (if available)
- `doi`: Digital Object Identifier
- `total`: Total number of matching papers

**Pagination:** Check the `total` field to see if more results exist. Use `--page 1`, `--page 2`, etc. to fetch more pages.

### 2. Paper Search Pro (Advanced)

Search for papers with advanced filtering options including keyword, abstract, author, organization, and venue filters. Use this when basic search doesn't provide enough filtering capabilities.

```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro [--title <title>] [--keyword <kw>] [--abstract <abs>] [--author <auth>] [--org <org>] [--venue <venue>] [--order <order>] [--page <n>] [--size <n>]
```

**Parameters:**
- `--title`: Paper title to search for (optional)
- `--keyword`: Keywords to search for (optional)
- `--abstract`: Abstract content to search for (optional)
- `--author`: Author name to search for (optional)
- `--org`: Organization/institution to search for (optional)
- `--venue`: Venue/journal name to search for (optional)
- `--order`: Sort order - use `year` or `n_citation` for descending sort (optional)
- `--page`: Page number starting from 0 (default: 0)
- `--size`: Results per page (default: 10, **maximum: 100**)

**Note:** At least one search parameter (title, keyword, abstract, author, org, or venue) must be provided.

**Examples:**
```bash
# Search by title and author
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --title "neural network" --author "Hinton"

# Search by keyword and venue
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --keyword "machine learning" --venue "NeurIPS"

# Search with citation-based sorting
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --title "transformer" --order "n_citation" --size 20

# Search by organization
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --org "Stanford" --keyword "deep learning"

# Complex search with multiple filters
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --title "3D reconstruction" --author "Li" --venue "CVPR" --order "year"
```

**Response fields:**
- `id`: Paper ID
- `title`: Paper title in English
- `title_zh`: Paper title in Chinese (if available)
- `doi`: Digital Object Identifier
- `total`: Total number of matching papers

**Sorting options:**
- `year`: Sort by publication year (descending)
- `n_citation`: Sort by citation count (descending)
- No `--order`: Default relevance-based sorting

### 3. Paper Detail

Get detailed information about a specific paper using its ID.

```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-detail <paper_id>
```

**Example:**
```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-detail 6880406d163c01c8507070d4
```

**Response fields:**
- `id`: Paper ID
- `title`: English title
- `title_zh`: Chinese title (if available)
- `abstract`: Abstract in English
- `abstract_zh`: Abstract in Chinese (if available)
- `authors`: List of authors with the following fields:
  - `id`: Author ID (if available)
  - `name`: Author name
  - `org`: Organization affiliation (if available)
  - `org_zh`: Chinese organization name (if available)
- `doi`: Digital Object Identifier
- `issn`: International Standard Serial Number
- `issue`: Issue number
- `volume`: Volume number
- `keywords`: List of keywords in English
- `keywords_zh`: List of keywords in Chinese (if available)
- `venue`: Venue/journal information:
  - `raw`: Venue name in English
  - `raw_zh`: Venue name in Chinese (if available)
  - `t`: Venue type
- `year`: Publication year

## Workflow Examples

### Find papers on a specific topic

1. Start with a basic search:
```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search --title "Gaussian Splatting"
```

2. If you need more filtering, use the pro search:
```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --title "Gaussian Splatting" --venue "CVPR" --order "n_citation"
```

3. Get detailed information about a specific paper:
```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-detail <paper_id_from_search>
```

### Find papers by a specific author

Use the pro search with author filter:
```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --author "Yann LeCun" --order "n_citation" --size 20
```

### Find recent papers from a conference

```bash
python .claude/skills/aminer-paper/aminer_paper_api.py paper-search-pro --venue "NeurIPS" --order "year" --size 50
```

## When to Use Which Search API

### Use Basic Search when:
- You only need to search by paper title
- You want a quick, simple search
- You don't need advanced filtering

### Use Pro Search when:
- You need to filter by multiple criteria (author, venue, organization, etc.)
- You want to sort results by year or citation count
- Basic search doesn't provide enough control
- You need to retrieve more than 20 results per page (up to 100)

## Error Handling

- If `AMINER_API_KEY` is not set, the script will exit with an error message.
- If a paper search returns no results, the `data` array will be empty.
- For pro search, at least one search parameter must be provided, otherwise an error will be shown.
- API errors (e.g., invalid paper ID) return `success: false` with an error message.

## API Documentation

For more details, refer to the official AMiner API documentation:
- Paper Search: https://www.aminer.cn/open/docs?id=64f03e746221825d961dbde4
- Paper Search Pro: https://www.aminer.cn/open/docs?id=66471a81d0efa2bb8d4e8c08
- Paper Detail: https://www.aminer.cn/open/docs?id=6522534c07bac596e60d91db
