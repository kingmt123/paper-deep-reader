# NotebookLM Key Figure Analysis Workflow

## Purpose
Use NotebookLM to identify and deeply analyze the most important figures in a paper, generating individual analysis files (one per figure).

## Why NotebookLM for Figures
- NotebookLM can "see" the PDF and its figures (multimodal)
- Lower hallucination rate than LLM text-only analysis
- Can reference specific figure content with paper context

## Workflow

### Step 1: Upload PDF to NotebookLM
```bash
# Create notebook
notebooklm create "图片分析 - Paper Title" --json

# Upload PDF
notebooklm source add paper.pdf --notebook <id> --json

# Wait for processing
notebooklm source wait <source_id> --timeout 180
```

### Step 2: Identify Key Figures
Ask a concise prompt (~50 chars, avoid timeout):
```
找出论文中最重要的4张图，按重要性排序。每张说明：Figure编号、标题、内容、为什么重要。
```

Response format to expect:
```
### 1. Figure X: Title
*   **内容**: ...
*   **为什么重要**: ...
```

### Step 3: Deep Analysis per Figure
For each identified figure, ask:
```
对Figure X进行深度解读：具体元素、关键数据、如何支持核心论点、可得结论、局限性。引用论文原文。
```

**CRITICAL**: Keep prompts short (<100 chars). Long Chinese prompts timeout at 180s.

### Step 4: Generate Output Files
For each figure, create `figures_analysis/figure_N_analysis.md`:
```markdown
# Figure N: Title

> 论文图片深度解读 | NotebookLM 分析

![Figure N](../images/hash.jpg)

---

## 在论文中的重要性
{importance}

---

## NotebookLM 深度解读
{deep analysis from NotebookLM}
```

Plus `figures_analysis/summary.md` with overview table.

## Pitfalls
- **Timeout**: Long prompts (>200 chars) timeout at 180s. Keep prompts concise.
- **Image matching**: MinerU Cloud images have hash filenames. Match by searching paper.md for "Fig. N" near `![](images/...)` references.
- **Subprocess upload**: `notebooklm source add` may fail from Python subprocess. Use `--notebook-id` flag to skip upload if already done from terminal.
- **Rate limiting**: NotebookLM may rate-limit rapid sequential questions. Add 3s delay between questions.

## Script
`scripts/analyze_key_figures.py` automates this workflow.
