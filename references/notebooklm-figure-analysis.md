# NotebookLM Figure Analysis Workflow (v1.2.1)

## Automated Workflow (Recommended)

Use `scripts/analyze_figures.py` for end-to-end figure analysis:

```bash
python scripts/analyze_figures.py paper.pdf [output_dir] --images-dir images/
```

### What it does:
1. Checks NotebookLM authentication
2. Creates notebook and uploads PDF
3. Selects top figures by file size (skips logos/title page)
4. For each figure (up to 6): description + classification + key takeaway
5. Outputs: `figure_analysis.json` + `figure_snippets.md`

### Key: `figure_snippets.md` is auto-generated Markdown ready for embedding.
Step 5 of the workflow MUST read this file and embed the descriptions.

## Manual Workflow (fallback)

```bash
notebooklm create "精读 - {title}" --json
notebooklm source add ./paper.pdf --json
notebooklm source wait <source_id>
notebooklm ask "Describe Figure N in detail" --json
```

## Prompt Patterns

**General figure analysis:**
```
Describe EACH figure in this paper in detail. For each figure:
1. What it shows (components, axes, labels)
2. Key components and labels
3. The main message
```

**Flowchart/diagram deep dive:**
```
Figure N shows a flowchart/diagram. Please describe:
1. Every step in the flowchart
2. Every number and data point visible
3. Every label and text element
4. The overall flow and decision points
```

## Integration with Deep-Read Note

The `figure_snippets.md` output contains pre-formatted Markdown like:

```markdown
### 🏗️ 架构图

![MRVF系统总体架构](images/page5_img1.png)
> **类型**: System architecture diagram showing 4 modules
> **描述**: The figure shows the MRVF telerobotic system...
> **关键信息**: The system integrates UR5 robot, PHANToM Omni...
```

Embed these directly in the relevant sections of the deep-read note.

## Pitfalls

1. NotebookLM has rate limits. The script adds 3-second delays between questions.
2. If NotebookLM fails, fall back to `vision_analyze` on extracted images.
3. Always verify figure descriptions against the actual paper content.
