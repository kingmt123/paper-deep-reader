---
name: paper-deep-reader
description: "Deep-read academic papers with MinerU Cloud extraction, LLM analysis, and NotebookLM key figure analysis. Outputs: Markdown notes + HTML + per-figure analysis files. Activates on /paper-deep-reader, 'deep read this paper', '精读论文', '解读论文', '分析这篇论文', '读一下这篇paper', '帮我读这篇PDF', '帮我读一下这篇论文', '解读一下这篇论文', '帮我解读这篇论文', '读一下这个PDF', '组会汇报', '帮我速读这篇论文', '快速总结一下这篇论文', '批量速读', '论文速读', '读一下文件夹中的论文', '帮我读一下这些论文', '帮我处理一下文件夹中的论文', DOI input, arXiv URL input, or any PDF attachment with a reading/analysis request."
version: 3.0.0
author: User
license: MIT
metadata:
  hermes:
    tags: [academic, paper-reading, mineru, notebooklm, research]
    related_skills: [notebooklm, arxiv]
---

# paper-deep-reader

Deep reading of academic papers. MinerU Cloud extracts structured content, LLM generates the analysis, NotebookLM identifies and analyzes key figures.

## When to Use

- User provides a PDF file and asks to read/analyze/understand it
- User provides a DOI or arXiv URL with a reading request
- User says: "帮我读一下这篇论文", "解读一下这篇论文", "精读论文", "组会汇报", "帮我速读这篇论文", etc.

**Don't use for:** quick summaries (use arxiv), literature search (use arxiv).

## Four Modes

When triggered, ask user which mode:

| 模式 | 流程 | 耗时 | 输出 |
|------|------|------|------|
| **完整解读** (默认) | MinerU Cloud + NBLM图片分析 + LLM精读 + HTML | 5-8分钟 | deep-read.md + html + figures_analysis/ |
| **快速解读** | 仅LLM分析（不走MinerU，不走NBLM） | 1-2分钟 | deep-read.md + html |
| **仅分析图片** | MinerU Cloud + NBLM图片分析 | 3-4分钟 | images/ + figures_analysis/ |
| **极简速读** | MinerU Cloud + LLM速读（仅模块1/2/5） | 30-60秒 | speed-read.md |

**Quick mode** skips MinerU extraction and NotebookLM entirely. LLM reads the PDF directly (if local) or existing `paper.md` (if previously extracted). No images embedded in output.

**Figures-only mode** runs MinerU extraction + NotebookLM figure analysis but skips LLM note generation. Output: `images/` + `figures_analysis/`.

**Speed-read mode** uses MinerU Cloud for extraction, then LLM generates a ~2KB note with only: basic info (module 1), core problems & contributions (module 2), evaluation (module 5). No figures, no HTML, no NotebookLM. Template: `templates/speed-read.md`. Ideal for batch processing multiple papers.

**Output location:** Save results in the current Hermes working directory. Create a subfolder named after the paper (e.g., `paper-readings/<paper_short_name>/`). If user specifies a path, use that instead.

**Default to "完整解读" if user doesn't specify.**

**Batch mode:** If user says "读一下文件夹中的论文" or provides multiple PDFs, ask: process all papers (batch speed-read) or select specific ones?

## Prerequisites

```bash
pip install pymupdf "notebooklm-py[browser]"

# MinerU API token
# Get from https://mineru.net → API密钥
# Save to: <skill_dir>/.mineru_token

# NotebookLM (one-time login)
notebooklm login
notebooklm auth check --test --json
```

## Workflow

### Step 1: Extract Content (MinerU Cloud)

```bash
python scripts/extract_paper.py <input> <output_dir>
```

| Input | Flow |
|-------|------|
| Local PDF | MinerU Cloud direct upload (pre-signed URL). Fallback: PyMuPDF |
| arXiv URL | MinerU API URL endpoint |
| DOI | CrossRef → URL → MinerU API |
| PDF URL | MinerU API directly |

Output: `paper.md` + `images/` + `metadata.json` + `layout.json`

### Step 2: NotebookLM Key Figure Analysis (条件执行)

**仅在"完整解读"和"仅分析图片"模式下执行。快速解读模式跳过此步骤。**

```bash
python scripts/analyze_key_figures.py <pdf_path> <output_dir> [--max-figures 4]
```

1. Creates new NotebookLM notebook, uploads PDF
2. Asks NotebookLM to identify the 3-5 most important figures
3. For each key figure, asks for deep analysis (use short prompts ~50 chars to avoid timeout)
4. Generates individual files: `figures_analysis/figure_N_analysis.md`

Each file contains:
- Image reference from `images/` (MinerU Cloud)
- NotebookLM overview (figure's role in the paper)
- NotebookLM deep analysis (detailed解读 + paper quotes)

Output: `figures_analysis/` with per-figure markdown files + `summary.md`

### Step 3: LLM Deep Analysis

**仅在"完整解读"和"快速解读"模式下执行。仅分析图片模式跳过此步骤。**

Read `paper.md` + `metadata.json` + `figures_analysis/summary.md` (if available), generate structured note using `templates/deep-read.md` + `references/prompts.md`.

**Key rules:**
- LLM is the primary analysis engine (12KB+ target)
- Paper type determines structure (Survey/Method/System/Experimental/Application)
- **Module 3 (方法/技术内容)**: 6 required subsections — problem formulation, method overview, core algorithm, key design decisions, comparison with related methods, strengths & potential issues. See `templates/deep-read.md` for detailed structure per paper type.
- **Module 4 (实验/结果/证据)**: 6 required subsections — methodology, quantitative results (with interpretation), qualitative results, computational cost, credibility assessment, limitations. See `templates/deep-read.md` for details.
- Metadata: API-verified = ground truth. Missing → "未提供"
- Images: embed 3-6 key figures from `images/` with `![caption](images/filename.png)`
- Read `figures_analysis/` and incorporate NotebookLM's figure insights
- Formulas: symbol-by-symbol + physical meaning + role + assumptions
- Limitations: 5 dimensions (author-stated / assumptions / data / method scope / cannot prove)
- Quotes: max 1-3 per section. Analysis > quotes
- Content depth: explain WHY, not just WHAT

### Step 4: Generate HTML

```bash
python scripts/generate_html.py note.md [output.html] [--theme light|dark]
```

Embedded images (base64), KaTeX math, Mermaid diagrams, responsive design.

### Step 5: Quality Gate

| Dimension | Weight |
|-----------|--------|
| Metadata accuracy | 10% |
| Content completeness & richness | 20% |
| Content depth (WHY not WHAT) | 15% |
| Figure accuracy + NotebookLM insights | 15% |
| Formula accuracy | 10% |
| Original quotes (1-3/section) | 5% |
| Limitations (5 dimensions) | 10% |
| Critical thinking | 15% |

Score < 6 → regenerate. Target: 8.0+.

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `extract_paper.py` | MinerU Cloud extraction + PyMuPDF fallback |
| `mineru_api.py` | Standalone MinerU Cloud API (upload→poll→download) |
| `analyze_key_figures.py` | NotebookLM key figure identification + per-figure analysis |
| `notebooklm_analyze.py` | NotebookLM paper-level analysis (methodology/results/limitations) |
| `figure_mapper.py` | Map images to captions |
| `generate_metadata.py` | Metadata extraction (PyMuPDF + CrossRef + S2) |
| `generate_index.py` | Hierarchical section index for long papers |
| `generate_comparison.py` | Multi-paper comparison report |
| `generate_html.py` | HTML output with KaTeX + Mermaid |
| `download_arxiv.sh` | arXiv PDF download |

## Common Pitfalls

1. **MinerU Cloud only accepts URLs or pre-signed upload.** For local PDFs, `mineru_api.py` handles: POST /file-urls/batch → PUT to pre-signed URL → poll → download ZIP. Use `curl --ssl-no-revoke` on Windows.

2. **NotebookLM is REQUIRED.** Both `analyze_key_figures.py` and `notebooklm_analyze.py` exit(1) if: not logged in, no notebook, upload fails, or timeout. Clear error messages with fix instructions.

3. **NotebookLM must upload current PDF.** Never reuse old notebooks without adding the current paper. Querying wrong paper = completely wrong results.

4. **NotebookLM subprocess upload fails on Windows.** `notebooklm source add` works from terminal but fails silently (exit 1) via Python `subprocess.run()`. Root cause: Unicode filenames (em-dash ‑, parentheses, >80 chars) or PATH/env propagation. Workaround: (a) run `notebooklm source add` from terminal, (b) pass `--notebook-id <id>` to the script which skips upload. Both `analyze_key_figures.py` and `notebooklm_analyze.py` accept this flag.

5. **analyze_key_figures.py question timeout.** NotebookLM `ask` with long Chinese prompts (>200 chars) can timeout at 180s. Use shorter prompts (~50 chars) or increase timeout. Break complex figure analysis into 2 shorter calls instead of 1 long one.

6. **MinerU Cloud image filenames are hashes.** `1752da165d332b6c...jpg` not `page3_imgM.png`. Sort by size for importance. `figure_mapper.py` handles this.

7. **Quotes: selective, not excessive.** Max 1-3 per section. Analysis > quotes.

8. **Content depth: explain WHY.** Target 12KB+. A 6KB note is too thin.

9. **Metadata hallucination.** API metadata = ground truth. PDF-extracted = "(PDF提取)". Missing = "未提供".

10. **HTML must be a rich product.** Embed images (base64), card layouts, KaTeX, Mermaid. Not a styled MD copy.

11. **Python 3.11 rejects inline regex flags.** Use `re.IGNORECASE` parameter, never `(?i)` mid-pattern.

12. **NotebookLM has no mindmap command.** Use Mermaid in Markdown instead.

## Verification Checklist

- [ ] MinerU Cloud extracts text, formulas, figures correctly
- [ ] Metadata verified (CrossRef/arXiv API, no hallucination)
- [ ] NotebookLM key figure analysis completed (figures_analysis/)
- [ ] Paper type identified via LLM
- [ ] Deep-read note contains 3-6 key figures with correct captions
- [ ] Content depth: each module explains WHY
- [ ] HTML embeds images (check `data:image` count > 0)
- [ ] Formulas: 4 components (symbols + meaning + role + assumptions)
- [ ] Limitations: 5 dimensions
- [ ] Quality gate score ≥ 8.0
