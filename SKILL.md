---
name: paper-deep-reader
description: "Deep-read academic papers with MinerU Cloud extraction, LLM analysis, and NotebookLM key figure analysis. Outputs: Markdown notes + HTML + per-figure analysis files. Activates on /paper-deep-reader, 'deep read this paper', '精读论文', '解读论文', '分析这篇论文', '读一下这篇paper', '帮我读这篇PDF', '帮我读一下这篇论文', '解读一下这篇论文', '帮我解读这篇论文', '读一下这个PDF', '组会汇报', '帮我速读这篇论文', '快速总结一下这篇论文', '批量速读', '论文速读', '读一下文件夹中的论文', '帮我读一下这些论文', '帮我处理一下文件夹中的论文', '总结论文和专利', '分析这些专利', DOI input, arXiv URL input, or any PDF attachment with a reading/analysis request."
version: 3.2.0
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
| **极简速读 batch** | 每篇独立子代理 + 编译汇总 | 30-60秒/篇 × N | paper-readings/speed-read/*.md + 汇总.md |
| **快速解读 batch** | 每篇独立子代理 + 编译汇总 | 1-2分钟/篇 × N | paper-readings/quick-read/*.md + 汇总.md |
| **完整解读 batch** | 逐篇串行pipeline + 编译对比报告 | 5-8分钟/篇 × N | paper-readings/<name>/ + 跨论文对比报告.md |

**Quick mode** skips MinerU extraction and NotebookLM entirely. LLM reads the PDF directly (if local) or existing `paper.md` (if previously extracted). No images embedded in output.

**Figures-only mode** runs MinerU extraction + NotebookLM figure analysis but skips LLM note generation. Output: `images/` + `figures_analysis/`.

**Speed-read mode** uses MinerU Cloud for extraction, then LLM generates a ~2KB note with only: basic info (module 1), core problems & contributions (module 2), evaluation (module 5). No figures, no HTML, no NotebookLM. Template: `templates/speed-read.md`. Ideal for batch processing multiple papers.

**Output location:** Save results in the current Hermes working directory. Create a subfolder named after the paper (e.g., `paper-readings/<paper_short_name>/`). If user specifies a path, use that instead.

**Default to "完整解读" if user doesn't specify.**

**Batch modes — three tiers:**

| 批量模式 | 每篇处理方式 | 每篇输出大小 | 适用场景 |
|----------|-------------|-------------|----------|
| **批量极简速读** | 独立子代理，1篇/代理 | 2-3KB speed-read.md | 10+篇快速摸底 |
| **批量快速解读** | 独立子代理，1篇/代理 | 6-10KB quick-read.md | 5-10篇需要方法概要 |
| **批量完整解读** | 串行完整pipeline | 12KB+ deep-read.md + HTML | 3-5篇深度精读 |

**CRITICAL: Never put multiple papers in one LLM call for batch processing.** The fixed output token budget gets divided among papers, causing each to be compressed to generic template-filling (e.g., "实验规模不足" as a one-size-fits-all criticism). Each paper MUST get its own LLM call with full output tokens.

**Batch processing flow (all three tiers):**
```
Step 1: execute_code — batch-extract text with PyMuPDF (~4s for 18 papers, saves to temp/)
Step 2: delegate_task — each subagent processes 1 paper individually
         3 concurrent subagents × 1 paper each = 3 papers per round
         18 papers = 6 rounds, ~8-12 min total
Step 3: 主代理读取所有独立笔记文件，编译汇总：
         - 按文件夹/主题分组的逐篇列表
         - 横向对比表（年份/期刊/方法/关键结果/不足）
         - 综合启示（关联用户课题）
         - "每个最致命问题"直评表
```

**Subagent template usage:** Subagents use existing templates — speed-read tier uses `templates/speed-read.md` (modules 1/2/5 only), quick-read tier uses `templates/deep-read.md` (modules 1/2/3/5, skip module 4). Pass template path in subagent context.

**Edge case: last round with <3 papers.** If total papers mod 3 leaves 1 or 2, the last `delegate_task` call has 1 or 2 tasks. This is fine — just pass fewer tasks. Don't pad with duplicates.

**Mixed folder (papers + patents):** If user says "总结论文和专利" or the folder contains patent PDFs alongside papers, detect document type from filenames (look for "US" + patent number patterns, or IPC codes). Patents use a different summary structure — see `references/patent-identification.md`. For scanned patent PDFs (no text layer), skip MinerU and use Google Patents browser lookup by patent number.

**Batch compilation output:** After all papers processed individually, compile into a single summary file (e.g., `文献速读汇总_<topic>.md` or `文献解读汇总_<topic>.md`). Structure: (1) grouped by folder/topic, (2)横向对比表 across all documents (year, journal, method, key results, limitations), (3) 综合启示 section connecting findings to user's research, (4) 每篇最致命问题表 (one-line "most fatal flaw" per paper). For patent identification and summarization workflow, see `references/patent-identification.md`.

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

## User Style Preferences

- **Weakness/limitation analysis**: Be DIRECT and SPECIFIC. No hedging, no filler. List concrete problems with evidence. Use a comparison table at the end summarizing each document's "most fatal flaw" (最大问题). User explicitly said "直接告诉我" — they want the honest assessment, not diplomatic understatement.
- **Methodology transparency**: When asked "你是如何总结的", be honest about what was actually done vs. the full skill workflow. Don't pretend MinerU/NBLM was used when it wasn't.
- **Chinese output**: All summaries in Chinese unless user specifies otherwise. Patent names translated to Chinese with original English in parentheses.
- **Batch quality over speed**: User explicitly identified that batch processing degrades per-paper quality. Always prioritize per-paper analysis depth over processing speed. One paper per LLM call is non-negotiable for batch modes. If user asks for 18 papers, take 10 minutes with good quality rather than 3 minutes with generic output.

## Common Pitfalls

1. **MinerU Cloud only accepts URLs or pre-signed upload.** For local PDFs, `mineru_api.py` handles: POST /file-urls/batch → PUT to pre-signed URL → poll → download ZIP. Use `curl --ssl-no-revoke` on Windows.

2. **NotebookLM is REQUIRED.** Both `analyze_key_figures.py` and `notebooklm_analyze.py` exit(1) if: not logged in, no notebook, upload fails, or timeout. Clear error messages with fix instructions.

3. **NotebookLM must upload current PDF.** Never reuse old notebooks without adding the current paper. Querying wrong paper = completely wrong results.

4. **NotebookLM subprocess upload fails on Windows.** `notebooklm source add` works from terminal but fails silently (exit 1) via Python `subprocess.run()`. Root cause: Unicode filenames (em-dash ‑, parentheses, >80 chars) or PATH/env propagation. Workaround: (a) run `notebooklm source add` from terminal, (b) pass `--notebook-id <id>` to the script which skips upload. Both `analyze_key_figures.py` and `notebooklm_analyze.py` accept this flag.

5. **analyze_key_figures.py question timeout AND subprocess upload.** Two issues: (a) Long Chinese prompts (>200 chars) timeout at 180s. Script uses short prompts (~50 chars). If still timeout, reduce `--max-figures`. (b) `notebooklm source add` fails from Python subprocess on Windows (Unicode filenames, PATH issues). Workaround: upload manually from terminal, then pass `--notebook-id <id> --skip-upload` to the script.

6. **MinerU Cloud image filenames are hashes.** `1752da165d332b6c...jpg` not `page3_imgM.png`. Sort by size for importance. `figure_mapper.py` handles this.

7. **Quotes: selective, not excessive.** Max 1-3 per section. Analysis > quotes.

8. **Content depth: explain WHY.** Target 12KB+. A 6KB note is too thin.

9. **Metadata hallucination.** API metadata = ground truth. PDF-extracted = "(PDF提取)". Missing = "未提供".

10. **HTML must be a rich product.** Embed images (base64), card layouts, KaTeX, Mermaid. Not a styled MD copy.

13. **Scanned/image-based PDFs have no text layer.** Common with US/Chinese patents. PyMuPDF `get_text()` returns empty string, every page has exactly 1 image. Do NOT attempt MinerU extraction. Instead: (a) identify the document type from filename, (b) for patents, extract patent number and look up on Google Patents (`patents.google.com/patent/<number>/en`), (c) for other scanned PDFs, use `vision_analyze` on page images at 150 DPI (200+ DPI causes API errors). See `references/patent-identification.md`.

14. **USPTO PatentsView API has migrated.** The old `api.patentsview.org` endpoint now redirects to `data.uspto.gov`. Direct API queries may fail silently. Use Google Patents browser lookup instead — it renders client-side JS but the snapshot contains all metadata (title, inventors, assignee, dates, abstract, classifications).

15. **Subagent delegation for patent search is unreliable.** Subagents may fabricate patent details (inventor names, abstracts) when they can't access the actual source. Always verify patent metadata yourself via Google Patents browser lookup. Do NOT trust subagent-reported patent abstracts without verification.

16. **Ambiguous patent filenames.** Filenames like "USDistributed training..." may start with "US" (country code) followed by the title — the patent number is not in the filename. Use Google Patents search with key title words to identify the actual patent number.

17. **Python 3.11 rejects inline regex flags.** Use `re.IGNORECASE` parameter, never `(?i)` mid-pattern.

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
