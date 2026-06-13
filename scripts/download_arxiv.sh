#!/bin/bash
# download_arxiv.sh — Download paper PDF from arXiv
# Usage: bash download_arxiv.sh <arxiv_id_or_url> [output_path]

set -euo pipefail

INPUT="${1:?Usage: download_arxiv.sh <arxiv_id_or_url> [output_path]}"
OUTPUT="${2:-paper.pdf}"

# Extract arXiv ID from URL or use directly
if [[ "$INPUT" =~ arxiv\.org/(abs|pdf)/([0-9]+\.[0-9]+) ]]; then
    ARXIV_ID="${BASH_REMATCH[2]}"
elif [[ "$INPUT" =~ ^[0-9]+\.[0-9]+$ ]]; then
    ARXIV_ID="$INPUT"
elif [[ "$INPUT" =~ ^[0-9]+\.[0-9]+v[0-9]+$ ]]; then
    ARXIV_ID="$INPUT"
else
    echo "ERROR: Cannot parse arXiv ID from: $INPUT"
    echo "Expected format: 1706.03762 or https://arxiv.org/abs/1706.03762"
    exit 1
fi

echo "=== Downloading arXiv Paper ==="
echo "arXiv ID: $ARXIV_ID"
echo "Output:   $OUTPUT"

# Download PDF
PDF_URL="https://arxiv.org/pdf/${ARXIV_ID}.pdf"
echo "URL:      $PDF_URL"

curl -L -o "$OUTPUT" "$PDF_URL" --progress-bar

if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    SIZE=$(wc -c < "$OUTPUT")
    echo ""
    echo "=== Download Complete ==="
    echo "File: $OUTPUT ($SIZE bytes)"
else
    echo "ERROR: Download failed"
    exit 1
fi
