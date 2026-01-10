---
name: verify-crawl
description: Verify that FireCrawl scraped Markdown files match their original web pages. Use this skill when user wants to check if crawled content is accurate, complete, or when they mention verifying scraped data.
content: fork
---

# Verify FireCrawl Crawled Content

This skill verifies that Markdown files scraped by FireCrawl accurately reflect the content of the original web pages.

## When to Use

- User asks to verify crawled/scraped Markdown files
- User wants to check if crawled content matches original web pages
- User mentions checking for errors or missing content in scraped files

## Workflow

1. **Read the Markdown file** specified by the user
2. **Extract metadata** from the YAML frontmatter:
   - `source_url`: The original URL that was scraped
   - `scraped_at`: When the content was scraped
3. **Fetch the original web page** using the `WebFetch` tool with the `source_url`
4. **Compare content** between the Markdown file and the freshly fetched content
5. **Generate verification report**

## File Format Expected

The Markdown files should have this structure:

```markdown
---
source_url: https://example.com/page
scraped_at: 2026-01-09
---

# Page Title

Content...
```

## Comparison Criteria

When comparing, check for:

1. **Title Match**: Does the main heading match?
2. **Key Sections Present**: Are all major sections from the original present in the scraped file?
3. **Important Data Accuracy**: Are dates, names, numbers accurately captured?
4. **Link Integrity**: Are important links preserved?
5. **Content Completeness**: Is there significant missing content?

## Output Format

Return the verification result in this format:

```
File: <file_path>
URL: <source_url>
Status: PASS | FAIL
Comment: <brief explanation of findings>
```

### Status Definitions

- **PASS**: The Markdown file accurately represents the original web page content with no significant discrepancies
- **FAIL**: There are notable differences, missing content, or errors between the Markdown and the original page

## Example Usage

User: "Verify the crawled file at data/aaai-26/bridge-program/bridge-program.md"

Steps:
1. Read `data/aaai-26/bridge-program/bridge-program.md`
2. Extract `source_url` from frontmatter
3. Fetch the original URL using `WebFetch` tool
4. Compare the two versions
5. Output verification report

## Important Notes

- If the original page has been updated since scraping, note this in the comment
- Focus on content accuracy, not formatting differences (minor whitespace/formatting differences are acceptable)
- If the page requires JavaScript rendering, mention this as a potential cause for discrepancies
