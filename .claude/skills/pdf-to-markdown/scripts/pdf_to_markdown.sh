#!/bin/bash
#
# PDF to Markdown Converter
# Converts PDF files (from URL or local path) to Markdown using MinerU API
#

set -e

# Configuration
MINERU_API_URL="${MINERU_API_URL:-http://localhost:9999}"
MINERU_LANG="${MINERU_LANG:-en}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

usage() {
    echo "Usage: $0 <input_pdf> <output_md>"
    echo ""
    echo "Arguments:"
    echo "  input_pdf   PDF source (local path or URL)"
    echo "  output_md   Output Markdown file path"
    echo ""
    echo "Environment variables:"
    echo "  MINERU_API_URL  API endpoint (default: http://localhost:9999)"
    echo "  MINERU_LANG     Document language (default: en)"
    echo ""
    echo "Examples:"
    echo "  $0 ./document.pdf ./output.md"
    echo "  $0 'https://example.com/doc.pdf' ./output.md"
    echo "  MINERU_LANG=ch $0 ./chinese.pdf ./output.md"
    exit 1
}

is_url() {
    local input="$1"
    [[ "$input" =~ ^https?:// ]]
}

cleanup() {
    if [[ -n "$TEMP_PDF" && -f "$TEMP_PDF" ]]; then
        rm -f "$TEMP_PDF"
    fi
    if [[ -n "$TEMP_JSON" && -f "$TEMP_JSON" ]]; then
        rm -f "$TEMP_JSON"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Check arguments
if [[ $# -ne 2 ]]; then
    log_error "Invalid number of arguments"
    usage
fi

INPUT="$1"
OUTPUT="$2"

# Check dependencies
for cmd in curl jq; do
    if ! command -v "$cmd" &> /dev/null; then
        log_error "Required command '$cmd' not found. Please install it."
        exit 1
    fi
done

# Determine input source
if is_url "$INPUT"; then
    log_info "Detected URL input: $INPUT"

    # Create temporary file for downloaded PDF
    TEMP_PDF=$(mktemp --suffix=.pdf)

    log_info "Downloading PDF..."
    if ! curl -sL "$INPUT" -o "$TEMP_PDF"; then
        log_error "Failed to download PDF from URL"
        exit 1
    fi

    # Verify download
    if [[ ! -s "$TEMP_PDF" ]]; then
        log_error "Downloaded file is empty"
        exit 1
    fi

    PDF_PATH="$TEMP_PDF"
    log_info "Downloaded to temporary file"
else
    log_info "Detected local file input: $INPUT"

    # Check if file exists
    if [[ ! -f "$INPUT" ]]; then
        log_error "File not found: $INPUT"
        exit 1
    fi

    PDF_PATH="$INPUT"
fi

# Create output directory if needed
OUTPUT_DIR=$(dirname "$OUTPUT")
if [[ ! -d "$OUTPUT_DIR" ]]; then
    log_info "Creating output directory: $OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR"
fi

# Create temporary file for API response
TEMP_JSON=$(mktemp --suffix=.json)

# Call MinerU API
log_info "Converting PDF to Markdown (language: $MINERU_LANG)..."
log_info "API endpoint: $MINERU_API_URL/file_parse"

HTTP_CODE=$(curl -s -w "%{http_code}" -X POST "${MINERU_API_URL}/file_parse" \
    -F "files=@${PDF_PATH}" \
    -F "return_md=true" \
    -F "return_images=false" \
    -F "lang_list=${MINERU_LANG}" \
    -F "response_format_zip=false" \
    -o "$TEMP_JSON")

# Check HTTP response
if [[ "$HTTP_CODE" != "200" ]]; then
    log_error "API request failed with HTTP code: $HTTP_CODE"
    if [[ -f "$TEMP_JSON" ]]; then
        log_error "Response: $(cat "$TEMP_JSON")"
    fi
    exit 1
fi

# Extract Markdown from JSON response
# API returns two possible formats:
# Format 1: [{"md": "..."}]
# Format 2: {"results": {"filename": {"md_content": "..."}}}

MD_CONTENT=""

# Try format 1 first
if jq -e '.[0].md' "$TEMP_JSON" > /dev/null 2>&1; then
    MD_CONTENT=$(jq -r '.[0].md' "$TEMP_JSON")
# Try format 2
elif jq -e '.results' "$TEMP_JSON" > /dev/null 2>&1; then
    # Get the first result's md_content
    MD_CONTENT=$(jq -r '.results | to_entries | .[0].value.md_content // empty' "$TEMP_JSON")
fi

if [[ -z "$MD_CONTENT" ]]; then
    log_error "Invalid API response - could not extract markdown content"
    log_error "Response: $(cat "$TEMP_JSON" | head -c 500)"
    exit 1
fi

# Save Markdown to output file
echo "$MD_CONTENT" > "$OUTPUT"

# Verify output
if [[ ! -s "$OUTPUT" ]]; then
    log_warn "Output file is empty - PDF may not contain extractable text"
fi

OUTPUT_SIZE=$(wc -c < "$OUTPUT")
log_info "Conversion complete!"
log_info "Output: $OUTPUT ($OUTPUT_SIZE bytes)"
