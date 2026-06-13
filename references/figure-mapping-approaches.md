# Figure-Caption Mapping Approaches

## Problem
Extracted images are named `page4_img1.png`, `page15_img5.png` (by page number). The deep-read note needs to know which image is the system architecture, which is the experiment result, etc. Guessing image names by page number fails consistently.

## Solution: figure_mapper.py (v1.5.0)

### Method 1: Layout-based (MinerU extraction, high confidence)
When MinerU extracts the PDF, `layout.json` contains image blocks with bounding boxes:
```json
{"type": "image", "bbox": [43, 63, 281, 110], "page_idx": 1}
```
The script finds text blocks containing "Fig. N | caption" near each image block using spatial proximity (same page, closest vertical distance).

### Method 2: Text-only (PyMuPDF extraction, medium confidence)
When only `paper.md` is available (no layout.json):
1. Parse paper.md for "Fig. N | caption" or "Figure N. caption" patterns
2. Estimate page number from character position in file
3. Match to closest unused image file by page number

### Method 3: NotebookLM supplement (when automated matching insufficient)
Use `analyze_figures.py` to ask NotebookLM about specific figures in the uploaded PDF. NotebookLM can identify figure content from the PDF directly.

## Key Lessons
- **Never guess image filenames** — always verify with `ls images/` and pass actual filenames to subagents
- **Subagents consistently guess wrong filenames** — the #1 cause of "no images" in outputs
- **PyMuPDF image captions are in paper.md text, not layout.json** — need text pattern matching
- **MinerU layout.json has "image" type blocks but no "caption" type** — captions may be in adjacent text blocks or in paper.md
- **Page numbers in filenames may not match PDF page numbers** — PyMuPDF extracts from page 1, but PDF internal numbering may differ

## GitHub Research Results
- **grobidOrg/grobid** (4.9k stars): ML for extracting info from scholarly docs, includes figure-caption pairing
- **titipata/scipdf_parser** (454 stars): Python PDF parser for scientific publications with figure extraction
- **vlln/pdffigures-mcp-server**: PDFFigures 2.0 (Allen AI) via FastAPI
- No single tool solves the problem perfectly for arbitrary PDFs

## Usage
```bash
# After extraction, run figure mapper
python scripts/figure_mapper.py <output_dir>

# Check results
cat <output_dir>/figure_map.md

# Use in deep-read note generation
# The LLM reads figure_map.md and uses matched filenames
```
