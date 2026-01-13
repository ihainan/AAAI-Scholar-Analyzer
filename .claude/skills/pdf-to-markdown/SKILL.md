---
name: pdf-to-markdown
description: Convert PDF files to Markdown using MinerU API. Use when user wants to convert a PDF (from URL or local path) to Markdown format. Supports both remote URLs and local file paths.
---

# PDF to Markdown Converter

Convert PDF documents to clean Markdown files using the MinerU document parsing service.

## Prerequisites

- MinerU API service running (default: `http://localhost:9999`)
- `curl` and `jq` installed

## Configuration

Set environment variables to customize behavior:

```bash
# Set MinerU API endpoint (required if not using default)
export MINERU_API_URL="http://your-mineru-server:9999"

# Set document language (optional, default: en)
export MINERU_LANG="ch"  # Use "ch" for Chinese, "en" for English
```

## Usage

Use the conversion script located at `scripts/pdf_to_markdown.sh`:

```bash
# Convert from local file
./scripts/pdf_to_markdown.sh /path/to/input.pdf /path/to/output.md

# Convert from URL
./scripts/pdf_to_markdown.sh "https://example.com/document.pdf" /path/to/output.md
```

## Parameters

| Parameter | Description |
|-----------|-------------|
| `input` | PDF source - can be a local file path or HTTP/HTTPS URL |
| `output` | Output path for the generated Markdown file |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MINERU_API_URL` | `http://localhost:9999` | MinerU API endpoint URL |
| `MINERU_LANG` | `en` | Document language (`en` for English, `ch` for Chinese, etc.) |

## Examples

### Convert a local PDF

```bash
./scripts/pdf_to_markdown.sh ./report.pdf ./report.md
```

### Convert a PDF from URL

```bash
./scripts/pdf_to_markdown.sh "https://arxiv.org/pdf/1706.03762.pdf" ./attention.md
```

### Specify Chinese language

```bash
MINERU_LANG=ch ./scripts/pdf_to_markdown.sh ./chinese_doc.pdf ./output.md
```

### Use custom API endpoint

```bash
MINERU_API_URL="http://192.168.1.100:9999" ./scripts/pdf_to_markdown.sh ./doc.pdf ./output.md
```

## How It Works

1. The script detects if the input is a URL or local path
2. If URL, downloads the PDF to a temporary file
3. Calls MinerU API with appropriate parameters
4. Extracts Markdown content from the JSON response
5. Saves to the specified output path
6. Cleans up temporary files

## Troubleshooting

If conversion fails:

1. **Check MinerU service**: Ensure the API is running at the configured endpoint
2. **Verify input**: Confirm the PDF exists and is accessible
3. **Check permissions**: Ensure write access to the output directory
4. **Review logs**: The script outputs error messages to stderr
