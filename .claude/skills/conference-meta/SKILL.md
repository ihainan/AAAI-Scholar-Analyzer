---
name: conference-meta
description: Generate meta.json metadata files for academic conferences. Use when user wants to create conference metadata, needs to generate meta.json for a conference directory, or asks about conference information structure.
---

# Conference Metadata Generator

This skill guides the generation of `meta.json` files for academic conferences, typically used by client applications to display conference information.

## When to Use

- User asks to create a `meta.json` for a conference
- User wants to generate metadata for a conference directory
- User asks about what fields should be in conference metadata
- Conference data has been crawled and needs a metadata summary

## Prerequisites

Conference data should already be crawled and stored in a directory structure like:

```
data/<conference-id>/
├── conference-info/
│   └── index.md          # Main conference info
├── calls/                # Call for papers
├── special-tracks/       # Special tracks info
├── workshops-tutorials/  # Workshops and tutorials
└── ...
```

Each Markdown file should have YAML frontmatter with `source_url` for reference.

## Meta.json Schema

The `meta.json` file should contain the following fields:

```json
{
  "name": "string (required)",
  "shortName": "string (required)",
  "edition": "number (required)",
  "year": "number (required)",
  "dates": {
    "start": "string (YYYY-MM-DD, required)",
    "end": "string (YYYY-MM-DD, required)"
  },
  "location": {
    "venue": "string (required)",
    "city": "string (required)",
    "country": "string (required)"
  },
  "description": "string (required)",
  "logo_url": "string (URL, required)",
  "urls": [
    {
      "url": "string (URL, required)",
      "name": "string (required)",
      "description": "string (required)"
    }
  ],
  "timezone": "string (IANA timezone, required)",
  "socialMedia": {
    "twitter": "string (URL, optional)",
    "linkedin": "string (URL, optional)",
    "facebook": "string (URL, optional)",
    "youtube": "string (URL, optional)"
  },
  "tags": ["string array (required)"]
}
```

## Field Descriptions

| Field | Description | Data Source |
|-------|-------------|-------------|
| `name` | Full official conference name | Local: `conference-info/index.md` |
| `shortName` | Abbreviated name (e.g., "AAAI-26") | Local: `conference-info/index.md` |
| `edition` | Conference edition number (e.g., 40 for 40th) | Local: extract from name |
| `year` | Conference year | Local: extract from dates |
| `dates.start` | First day of conference (YYYY-MM-DD) | Local: `conference-info/index.md` |
| `dates.end` | Last day of conference (YYYY-MM-DD) | Local: `conference-info/index.md` |
| `location.venue` | Venue name (e.g., "Singapore EXPO") | Local: `conference-info/index.md` |
| `location.city` | City name | Local: `conference-info/index.md` |
| `location.country` | Country name | Local: `conference-info/index.md` |
| `description` | Conference description/purpose | Local: `conference-info/index.md` |
| `logo_url` | URL to conference logo image | Online: scrape official website |
| `urls` | Array of useful conference links | Local + Online: combine both sources |
| `timezone` | IANA timezone (e.g., "Asia/Singapore") | Derive from location |
| `socialMedia` | Social media account URLs | Online: search or scrape |
| `tags` | Research topic tags | Local: extract from tracks/calls |

## Workflow

### Step 1: Read Local Content

Read the main conference info file to extract basic information:

```bash
# Read the main index file
Read data/<conference-id>/conference-info/index.md
```

Extract:
- Conference name and edition
- Dates (start and end)
- Location (venue, city, country)
- Description

### Step 2: Scrape Official Website

Use `firecrawl_scrape` or `WebFetch` to get additional info from the official website:

```
# Get logo URL, social links, and additional URLs
firecrawl_scrape: <official_conference_url>
```

Look for:
- Logo image URL (usually in header or og:image meta tag)
- Navigation menu links for the `urls` array

### Step 3: Find Social Media Accounts

Search for official social media accounts:

```
WebSearch: "<organization_name> twitter linkedin official"
```

Common patterns:
- Twitter/X: Often `@RealAAAI` or `@<conference_name>`
- LinkedIn: Organization page URL

### Step 4: Extract Research Tags

Read special tracks and calls to identify research topics:

```bash
# List special tracks
ls data/<conference-id>/special-tracks/

# Read track descriptions for topic extraction
Read data/<conference-id>/special-tracks/*.md
```

Common AI conference tags include:
- Artificial Intelligence
- Machine Learning
- Deep Learning
- Natural Language Processing
- Computer Vision
- Robotics
- Knowledge Representation
- Planning and Scheduling
- Multi-Agent Systems
- Reinforcement Learning

### Step 5: Determine Timezone

Map the conference city to IANA timezone:

| City | Timezone |
|------|----------|
| Singapore | Asia/Singapore |
| Vancouver | America/Vancouver |
| New York | America/New_York |
| London | Europe/London |
| Tokyo | Asia/Tokyo |
| Sydney | Australia/Sydney |
| Paris | Europe/Paris |
| Seoul | Asia/Seoul |

### Step 6: Compile URLs Array

Include these standard URLs when available:

1. **Official Website** - Main conference homepage
2. **Registration** - Registration portal
3. **Author Kit** - Paper submission templates
4. **Call for Papers** - Main technical track CFP
5. **Accommodations** - Hotel and travel info
6. **Program** - Schedule overview
7. **Invited Speakers** - Keynote information
8. **Workshops** - Workshop program

Format each URL entry:
```json
{
  "url": "https://...",
  "name": "Short Name",
  "description": "Brief description of what this link provides"
}
```

### Step 7: Generate meta.json

Write the compiled information to `meta.json`:

```bash
Write data/<conference-id>/meta.json
```

## Example Output

```json
{
  "name": "The 40th Annual AAAI Conference on Artificial Intelligence",
  "shortName": "AAAI-26",
  "edition": 40,
  "year": 2026,
  "dates": {
    "start": "2026-01-20",
    "end": "2026-01-27"
  },
  "location": {
    "venue": "Singapore EXPO",
    "city": "Singapore",
    "country": "Singapore"
  },
  "description": "The purpose of the AAAI conference series is to promote research in Artificial Intelligence (AI) and foster scientific exchange between researchers, practitioners, scientists, students, and engineers across the entirety of AI and its affiliated disciplines.",
  "logo_url": "https://aaai.org/wp-content/uploads/2025/01/AAAI-26_Mark-Inverse-300x187.png",
  "urls": [
    {
      "url": "https://aaai.org/conference/aaai/aaai-26/",
      "name": "Official Website",
      "description": "AAAI-26 official conference homepage"
    },
    {
      "url": "https://aaai.org/conference/aaai/aaai-26/registration/",
      "name": "Registration",
      "description": "Conference registration information and portal"
    }
  ],
  "timezone": "Asia/Singapore",
  "socialMedia": {
    "twitter": "https://twitter.com/RealAAAI",
    "linkedin": "https://www.linkedin.com/company/association-for-the-advancement-of-artificial-intelligence-aaai-"
  },
  "tags": [
    "Artificial Intelligence",
    "Machine Learning",
    "Deep Learning",
    "Natural Language Processing",
    "Computer Vision"
  ]
}
```

## Validation Checklist

Before finalizing, verify:

- [ ] All required fields are present
- [ ] Dates are in YYYY-MM-DD format
- [ ] All URLs are valid and accessible
- [ ] Logo URL points to an actual image
- [ ] Timezone is a valid IANA timezone string
- [ ] Tags are relevant to the conference topics
- [ ] JSON is valid (no trailing commas, proper quoting)

## Error Handling

- **Missing local files**: Note which fields couldn't be populated and why
- **Unreachable URLs**: Mark as "unavailable" and note in comments
- **Social media not found**: Omit the field rather than guessing
- **Ambiguous information**: Prefer official sources over third-party

## Notes

- Always prefer local crawled data over re-scraping when possible
- Keep descriptions concise (1-3 sentences)
- Use the organization's official social media accounts, not conference-specific ones if they don't exist
- Tags should reflect the main research areas covered by the conference
