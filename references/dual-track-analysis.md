# Analysis Architecture (v3.0.0)

## Roles

- **LLM** = sole analysis engine for reading notes (modules 1-5)
- **NotebookLM** = key figure identification + per-figure deep analysis only
- NotebookLM does NOT generate or supplement the reading note itself

## Workflow

### Complete mode (完整解读)
1. MinerU Cloud → paper.md + images/
2. NotebookLM → figures_analysis/ (per-figure files)
3. LLM reads paper.md + figures_analysis/ → deep-read.md
4. HTML generation

### Quick mode (快速解读)
- LLM reads PDF directly → deep-read.md + HTML
- No MinerU, no NotebookLM

### Figures-only mode (仅分析图片)
- MinerU Cloud + NotebookLM → images/ + figures_analysis/
- No LLM note generation

### Speed-read mode (极简速读)
- MinerU Cloud + LLM → speed-read.md (~2KB, modules 1/2/5 only)

## NotebookLM Prompt Strategy

Use SHORT prompts (~50 chars) to avoid timeout. Long Chinese prompts (>200 chars) can timeout at 180s.

- "找出论文中最重要的4张图，按重要性排序"
- "对Figure N进行深度解读：具体元素、关键数据、如何支持核心论点"

If timeout occurs, break into shorter calls or reduce max-figures.
