# paper-deep-reader

Hermes Agent skill for deep reading academic papers. Extracts structured content via MinerU Cloud API, analyzes with NotebookLM for key figure identification, and generates comprehensive reading notes with HTML output.

## Features

- **MinerU Cloud API extraction** — PDF to structured Markdown with LaTeX formulas, tables, and figures
- **NotebookLM key figure analysis** — AI-powered identification and deep analysis of the most important figures
- **LLM deep reading** — 5-module structured analysis (info, contributions, methodology, experiments, evaluation)
- **4 reading modes** — Full analysis, quick read, figures-only, speed-read
- **Multiple input formats** — Local PDF, arXiv URL, DOI, PDF URL
- **Rich HTML output** — Embedded images, KaTeX math rendering, Mermaid diagrams

## Reading Modes

| Mode | Flow | Time | Output |
|------|------|------|--------|
| **Full Analysis** (default) | MinerU Cloud + NotebookLM figures + LLM + HTML | 5-8 min | deep-read.md + html + figures_analysis/ |
| **Quick Read** | LLM only (no MinerU, no NotebookLM) | 1-2 min | deep-read.md + html |
| **Figures Only** | MinerU Cloud + NotebookLM figures | 3-4 min | images/ + figures_analysis/ |
| **Speed Read** | MinerU Cloud + LLM (modules 1/2/5 only) | 30-60s | speed-read.md |

## Prerequisites

```bash
# Python dependencies
pip install pymupdf "notebooklm-py[browser]"

# MinerU API token
# Get from https://mineru.net → API密钥
# Save to: <skill_dir>/.mineru_token

# NotebookLM (one-time login)
notebooklm login
notebooklm auth check --test --json
```

## Installation

This is a Hermes Agent skill. To install:

1. Copy the skill directory to your Hermes skills folder:
   ```bash
   # Windows
   cp -r paper-deep-reader ~/AppData/Local/hermes/skills/research/
   
   # Linux/macOS
   cp -r paper-deep-reader ~/.hermes/skills/research/
   ```

2. Save your MinerU API token:
   ```bash
   echo "your_token_here" > <skill_dir>/.mineru_token
   ```

3. Login to NotebookLM:
   ```bash
   notebooklm login
   ```

## Usage

### Via Hermes Agent

```
# Full analysis
"帮我解读这篇论文" + attach PDF

# Speed read
"帮我速读这篇论文" + attach PDF

# Batch processing
"帮我处理一下文件夹中的论文" + provide folder path

# With DOI
"帮我读一下 10.3390/bioengineering11060550"

# With arXiv URL
"帮我读一下 https://arxiv.org/abs/1706.03762"
```

### Direct Script Usage

```bash
# Extract content from local PDF
python scripts/extract_paper.py paper.pdf ./output

# Extract from URL
python scripts/extract_paper.py https://arxiv.org/abs/1706.03762 ./output

# Extract from DOI
python scripts/extract_paper.py 10.3390/bioengineering11060550 ./output

# MinerU Cloud API standalone
python scripts/mineru_api.py paper.pdf ./output

# Key figure analysis
python scripts/analyze_key_figures.py paper.pdf ./output --max-figures 4

# NotebookLM paper analysis
python scripts/notebooklm_analyze.py paper.pdf ./output --sections methodology results limitations

# Generate HTML from note
python scripts/generate_html.py note.md output.html --theme light

# Multi-paper comparison
python scripts/generate_comparison.py paper_A/ paper_B/ -o comparison.md

# Build index for long papers (>20 pages)
python scripts/generate_index.py paper.md index.json -m metadata.json
```

## Output Structure

```
output/
├── paper.md              MinerU Cloud extracted Markdown
├── images/               Extracted figures
├── metadata.json         CrossRef-verified metadata
├── layout.json           MinerU layout data
├── extraction_log.md     Extraction diagnostics
├── figures_analysis/     NotebookLM key figure analysis
│   ├── figure_1_analysis.md
│   ├── figure_2_analysis.md
│   ├── summary.md
│   └── analysis.json
├── deep-read.md          LLM reading note (full analysis)
├── deep-read.html        Rich HTML output
└── speed-read.md         Speed-read note (modules 1/2/5 only)
```

## Scripts

| Script | Purpose |
|--------|---------|
| `extract_paper.py` | Unified extraction (MinerU Cloud + PyMuPDF fallback) |
| `mineru_api.py` | Standalone MinerU Cloud API (upload → poll → download) |
| `analyze_key_figures.py` | NotebookLM key figure identification + per-figure analysis |
| `notebooklm_analyze.py` | NotebookLM paper-level analysis (methodology/results/limitations) |
| `analyze_figures.py` | NotebookLM figure analysis (legacy) |
| `figure_mapper.py` | Map images to captions |
| `generate_metadata.py` | Metadata extraction (PyMuPDF + CrossRef + Semantic Scholar) |
| `generate_index.py` | Hierarchical section index for long papers |
| `generate_comparison.py` | Multi-paper comparison report |
| `generate_html.py` | HTML output with KaTeX + Mermaid |
| `download_arxiv.sh` | arXiv PDF download |

## Key Technical Details

### MinerU Cloud API (Local PDF Upload)

The skill uses MinerU Cloud's pre-signed URL upload flow:

1. `POST /api/v4/file-urls/batch` → get pre-signed upload URL + batch_id
2. `PUT <upload_url>` → upload PDF bytes (no Content-Type header!)
3. `GET /api/v4/extract-results/batch/<batch_id>` → poll until done
4. Download ZIP → extract paper.md + images/

**Windows note:** Use `curl --ssl-no-revoke` for all curl calls (Windows SSL revocation check fails against Aliyun CDN).

### NotebookLM Integration

- NotebookLM is **required** for figure analysis — scripts exit(1) on auth/upload failure
- Always uploads the **current PDF** before asking questions (never reuses old notebooks)
- Creates a new notebook per paper to avoid cross-contamination

### Dual-Track Analysis

- **LLM** is the primary analysis engine (generates 12KB+ notes)
- **NotebookLM** supplements with core findings (methodology/results/limitations)
- NotebookLM's "cannot prove" analysis is merged into the evaluation module

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MinerU API returns 403 | Publisher blocks MinerU Cloud. PyMuPDF fallback auto-activates. |
| SSL error on upload/download | Add `--ssl-no-revoke` to curl commands. |
| NotebookLM not authenticated | Run `notebooklm login` |
| NotebookLM upload fails | Filename may have special chars. Rename PDF to ASCII-only name. |
| Python regex error | Use `re.IGNORECASE` flag, never `(?i)` inline. |
| PPT images not embedded | (Removed in v3.0.0 — PPT module no longer included) |

## License

MIT
