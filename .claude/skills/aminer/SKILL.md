---
name: aminer
description: Query academic information from AMiner, including organization search, organization details, scholar search, scholar details, projects, papers, research profile, and patents. Use when user asks about universities, research institutions, or academic scholars.
---

# AMiner Academic Query

This skill provides access to AMiner's academic database APIs for querying information about research organizations and scholars.

**IMPORTANT: All commands MUST be executed with `python` prefix. Do NOT run the script directly without `python`.**

## Prerequisites

The `AMINER_API_KEY` environment variable must be set with a valid AMiner API key.

## Available Commands

### 1. Organization Search

Find organization IDs by name. Organization IDs are required for other API calls.

```bash
python .claude/skills/aminer/aminer_api.py org-search "<org_name>"
```

**Example:**
```bash
python .claude/skills/aminer/aminer_api.py org-search "University of Alberta"
```

**Response fields:**
- `org_id`: The unique identifier for the organization (empty string if not found)
- `org_name`: The matched organization name

**Note:** If an organization is not found, `org_id` will be an empty string.

### 2. Organization Details

Get detailed information about organizations by their IDs.

```bash
python .claude/skills/aminer/aminer_api.py org-detail <org_id>
```

**Example:**
```bash
python .claude/skills/aminer/aminer_api.py org-detail 5f71b2941c455f439fe3cd7c
```

**Response fields:**
- `id`: Organization ID
- `name`: English name
- `name_zh`: Chinese name
- `name_en`: English name
- `aliases`: Alternative names for the organization
- `acronyms`: Abbreviations
- `type`: Organization type (e.g., TYPE_EDUCATION)
- `image`: URL to organization logo/image

### 3. Scholar Search

Search for scholars by name, optionally filtered by organization.

```bash
python .claude/skills/aminer/aminer_api.py person-search --name "<scholar_name>" [--org-id <org_id>] [--offset <n>] [--size <n>]
```

**Parameters:**
- `--name`: Scholar name to search for (required)
- `--org-id`: Filter by organization ID(s) (optional, can specify multiple)
- `--offset`: Pagination offset (default: 0)
- `--size`: Results per page (default: 10, **maximum: 10**)

**Example:**
```bash
# Search globally
python .claude/skills/aminer/aminer_api.py person-search --name "Adam Parker"

# Search within a specific organization
python .claude/skills/aminer/aminer_api.py person-search --name "Adam Parker" --org-id 5f71b2941c455f439fe3cd7c
```

**Response fields:**
- `id`: Scholar ID
- `name`: Scholar name
- `name_zh`: Chinese name (if available)
- `org`: Organization affiliation
- `org_id`: Organization ID
- `org_zh`: Chinese organization name
- `interests`: Research interests/keywords
- `n_citation`: Citation count
- `total`: Total number of matching scholars

**Pagination:** API returns max 10 results per request. Check `total` field to see if more exist, then use `--offset 10`, `--offset 20`, etc. to fetch more pages.

### 4. Scholar Details

Get detailed information about a scholar by their ID.

```bash
python .claude/skills/aminer/aminer_api.py person-detail <person_id>
```

**Example:**
```bash
python .claude/skills/aminer/aminer_api.py person-detail 53f466dfdabfaedd74e6b9e2
```

**Response fields:**
- `id`: Scholar ID
- `name`: English name
- `name_zh`: Chinese name
- `bio`: Biography in English
- `bio_zh`: Biography in Chinese
- `edu`: Education history in English
- `edu_zh`: Education history in Chinese
- `honor`: List of honors/awards
- `orgs`: Current organization affiliations
- `org_zhs`: Organizations in Chinese
- `position`: Current position
- `position_zh`: Position in Chinese

### 5. Scholar Projects

Get projects associated with a scholar.

```bash
python .claude/skills/aminer/aminer_api.py person-projects <person_id>
```

**Example:**
```bash
python .claude/skills/aminer/aminer_api.py person-projects 53f466dfdabfaedd74e6b9e2
```

**Response fields:**
- `id`: Project ID
- `titles`: Project titles (with language info)
- `country`: Country code
- `project_source`: Project source (e.g., NSFC_CITEXS)
- `fund_amount`: Funding amount
- `fund_currency`: Funding currency
- `start_date`: Start date
- `end_date`: End date

### 6. Scholar Papers

Get papers authored by a scholar with client-side pagination.

```bash
python .claude/skills/aminer/aminer_api.py person-papers <person_id> [--offset <n>] [--size <n>]
```

**Parameters:**
- `person_id`: Scholar ID (required)
- `--offset`: Pagination offset (default: 0)
- `--size`: Results per page (default: 20, **maximum: 20**)

**Example:**
```bash
# Get first 20 papers
python .claude/skills/aminer/aminer_api.py person-papers 53f466dfdabfaedd74e6b9e2

# Get papers 21-40
python .claude/skills/aminer/aminer_api.py person-papers 53f466dfdabfaedd74e6b9e2 --offset 20

# Get 10 papers starting from offset 30
python .claude/skills/aminer/aminer_api.py person-papers 53f466dfdabfaedd74e6b9e2 --offset 30 --size 10
```

**Response fields:**
- `id`: Paper ID
- `author_id`: Author's scholar ID
- `title`: Paper title in English
- `title_zh`: Paper title in Chinese
- `total`: Total number of papers
- `offset`: Current offset
- `size`: Current page size

**Note:** The API returns all papers at once, but the client provides pagination to limit response size.

### 7. Scholar Profile/Figure

Get scholar's research profile including interests, education history, and work experience.

```bash
python .claude/skills/aminer/aminer_api.py person-figure <person_id>
```

**Example:**
```bash
python .claude/skills/aminer/aminer_api.py person-figure 53f466dfdabfaedd74e6b9e2
```

**Response fields:**
- `id`: Scholar ID
- `ai_domain`: AI research domain
- `ai_interests`: List of research interests with order/weight
  - `name`: Interest name
  - `order`: Weight/importance score
- `edus`: Education history
  - `org`: Institution name
  - `department`: Department
  - `position`: Position type (13=PhD, 14=Master, 15=Bachelor)
  - `position_extra`: Position description
  - `start_year`: Start year
  - `end_year`: End year
- `works`: Work experience
  - `org`: Organization name
  - `department`: Department
  - `position`: Position type
  - `position_extra`: Position description
  - `start_year`: Start year
  - `end_year`: End year (if applicable)

### 8. Scholar Patents

Get patents associated with a scholar.

```bash
python .claude/skills/aminer/aminer_api.py person-patents <person_id>
```

**Example:**
```bash
python .claude/skills/aminer/aminer_api.py person-patents 53f466dfdabfaedd74e6b9e2
```

**Response fields:**
- `patent_id`: Patent ID
- `person_id`: Scholar ID
- `title`: Patent titles by language
  - `en`: English title(s)
  - `fr`: French title(s) (if available)
  - Other language codes as applicable

## Workflow Examples

### Find scholars at a university

1. First, get the organization ID:
```bash
python .claude/skills/aminer/aminer_api.py org-search "MIT"
```

2. Then search for scholars at that organization:
```bash
python .claude/skills/aminer/aminer_api.py person-search --name "John" --org-id <org_id_from_step1>
```

### Get organization information

1. Search for the organization:
```bash
python .claude/skills/aminer/aminer_api.py org-search "Stanford University"
```

2. Get detailed information:
```bash
python .claude/skills/aminer/aminer_api.py org-detail <org_id>
```

## Error Handling

- If `AMINER_API_KEY` is not set, the script will exit with an error message.
- If an organization is not found, the `org_id` field in the response will be empty.
- If a scholar search returns no results, the `data` array will be empty.
- API errors (e.g., invalid org ID for detail query) return `success: false` with an error message.

## API Documentation

For more details, refer to the official AMiner API documentation:
- Organization Search: https://www.aminer.cn/open/docs?id=652529e09a86cfd3829b5f7b
- Organization Detail: https://www.aminer.cn/open/docs?id=6525285f9a86cfd3829b5f7a
- Person Search: https://www.aminer.cn/open/docs?id=671a19a46e728a29db292f73
- Person Detail: https://www.aminer.cn/open/docs?id=650c01ada35ad00c78dbb65f
- Person Projects: https://www.aminer.cn/open/docs?id=69314320b7a55c2e5218f96d
- Person Papers: https://www.aminer.cn/open/docs?id=652252e007bac596e60d91da
- Person Figure: https://www.aminer.cn/open/docs?id=650c0336a35ad00c78dbb661
- Person Patents: https://www.aminer.cn/open/docs?id=6524fa8c228b43f5d3572641
