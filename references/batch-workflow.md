# Batch Multi-Folder Workflow

Efficient pattern for processing 10+ papers across multiple subfolders.

**Core principle: 逐篇独立处理，最后合并.** Each paper gets its own LLM call with full output token budget. Do NOT feed multiple papers into one call.

## Step 1: Discover Folders and PDFs

```python
# List subfolders
terminal("ls -d <base>/*/")

# List PDFs per folder
for folder in folders:
    pdfs = [f for f in os.listdir(folder) if f.endswith('.pdf')]
```

## Step 2: Batch Extract Text (execute_code)

```python
import fitz, os

for pdf_name in sorted(pdfs):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    # Save to temp/ dir
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
```

**Speed**: ~4 seconds for 18 papers (3.8s measured).

**Detect scanned PDFs**: If `len(text.strip()) < 100` and every page has exactly 1 image → scanned. Flag for patent/OCR handling.

## Step 3: Individual Processing (delegate_task)

**Critical: 1 paper per subagent, NOT 6.**

Split all papers into rounds of 3 (max concurrent subagents). Each subagent processes exactly 1 paper.

```
Round 1: delegate_task(tasks=[论文1, 论文2, 论文3])  → 3 个独立笔记
Round 2: delegate_task(tasks=[论文4, 论文5, 论文6])  → 3 个独立笔记
...
Round N: delegate_task(tasks=[论文16, 论文17, 论文18]) → 3 个独立笔记
```

**Subagent配置 per mode:**

| Mode | Output per paper | Subagent prompt includes |
|------|-----------------|-------------------------|
| 极简速读 batch | `speed-read/<name>.md` (2-3KB) | 文件路径 + speed-read模板字段要求 + "respond in Chinese" |
| 快速解读 batch | `quick-read/<name>.md` (6-10KB) | 文件路径 + deep-read模板(跳过模块4) + "respond in Chinese" |
| 完整解读 batch | `deep-read/<name>/deep-read.md` (12KB+) | 完整pipeline，串行不并行 |

**Subagent toolsets**: `["terminal", "file"]` — they need to read files.

**Typical timing**:
- 极简速读: ~30-60s/round × 6 rounds = 6-8 min for 18 papers
- 快速解读: ~60-120s/round × 6 rounds = 10-15 min for 18 papers
- 完整解读: 串行，每篇5-8 min，18篇 ≈ 90-140 min

## Step 4: Compile Results

After all individual notes are generated, the main agent reads them all and compiles:

```python
# Read all individual notes
for note_file in sorted(glob("speed-read/*.md")):
    content = read_file(note_file)
    # Extract key fields for comparison table
```

**Compilation output structure:**
1. **逐篇速读列表** — 按文件夹/主题分组，每篇的结构化摘要
2. **横向对比表** — 年份、期刊/来源、方法、关键结果、不足、最致命问题
3. **综合启示** — 关联用户课题，综合各篇发现
4. **高频主题统计** — 哪些主题出现最多

**Output filename**: `文献速读汇总_<topic>.md` or `文献解读汇总_<topic>.md`

## Pitfalls

1. **Don't send full text to subagents.** Subagents read from files themselves via read_file.
2. **1 paper per subagent is non-negotiable.** 2+ papers per subagent = quality degradation from shared output tokens.
3. **Subagent file paths must use Windows paths** (C:\...) not POSIX (/c/...), since file reads go through Python.
4. **Patents in mixed folders**: Detect from filename patterns (US/CN/EP + number). Route to Google Patents browser lookup instead of text extraction.
5. **Subagent patent fabrication**: Subagents may invent patent details when they can't verify. Always spot-check patents yourself via browser.
6. **Round-robin batching**: If a round has <3 papers (e.g., last round has 1-2), still delegate — don't skip.
7. **完整解读 batch is serial**, not parallel — MinerU and NBLM have API rate limits. Process one paper at a time, save result, move to next.
