#!/usr/bin/env python3
"""
generate_comparison.py — Generate multi-paper comparison report.

Reads extracted paper data from multiple directories and generates a structured
comparison report. Each directory should contain paper.md + metadata.json.

Usage: python generate_comparison.py <dir1> <dir2> [dir3 ...] [output.md]

Example:
  python generate_comparison.py paper_A/ paper_B/ comparison.md
  python generate_comparison.py ./paper_A ./paper_B ./paper_C  # output defaults to comparison.md
"""

import sys
import os
import re
import json
import argparse
from datetime import datetime


def load_paper(paper_dir: str) -> dict:
    """Load paper data from a directory containing paper.md + metadata.json."""
    paper = {"dir": paper_dir}

    # Load metadata
    meta_path = os.path.join(paper_dir, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            paper["metadata"] = json.load(f)
    else:
        paper["metadata"] = {}

    # Load paper content
    md_path = os.path.join(paper_dir, "paper.md")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            paper["content"] = f.read()
    else:
        paper["content"] = ""

    # Load index if available
    idx_path = os.path.join(paper_dir, "paper_index.json")
    if os.path.exists(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            paper["index"] = json.load(f)
    else:
        paper["index"] = None

    return paper


def extract_key_info(paper: dict) -> dict:
    """Extract key comparison-relevant information from a paper."""
    meta = paper.get("metadata", {})
    content = paper.get("content", "")
    index = paper.get("index", {})

    info = {
        "title": meta.get("title", "Unknown"),
        "authors": meta.get("authors", "N/A"),
        "journal": meta.get("journal", "N/A"),
        "year": meta.get("year", "N/A"),
        "doi": meta.get("doi", "N/A"),
        "abstract": meta.get("abstract", ""),
    }

    # Extract sections from index or content
    if index and "sections" in index:
        info["sections"] = [
            {"heading": s["heading"], "level": s["level"],
             "summary": s.get("summary", ""), "char_count": s.get("char_count", 0)}
            for s in index["sections"]
        ]
        info["total_chars"] = index.get("total_chars", 0)
        info["total_formulas"] = index.get("total_formulas", 0)
        info["total_figures"] = index.get("total_figures", 0)
    else:
        # Parse sections from content
        sections = []
        for match in re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE):
            level = len(match.group(1))
            heading = match.group(2).strip()
            sections.append({"heading": heading, "level": level, "summary": "", "char_count": 0})
        info["sections"] = sections
        info["total_chars"] = len(content)
        info["total_formulas"] = 0
        info["total_figures"] = 0

    # Extract method-related sections
    method_keywords = ["method", "approach", "framework", "model", "architecture",
                       "algorithm", "方法", "模型", "架构", "算法"]
    info["method_sections"] = [
        s for s in info["sections"]
        if any(kw in s["heading"].lower() for kw in method_keywords)
    ]

    # Extract experiment-related sections
    exp_keywords = ["experiment", "evaluation", "result", "performance",
                    "实验", "评估", "结果", "性能"]
    info["experiment_sections"] = [
        s for s in info["sections"]
        if any(kw in s["heading"].lower() for kw in exp_keywords)
    ]

    # Extract limitations
    limit_keywords = ["limitation", "不足", "局限", "future", "未来"]
    info["limitation_sections"] = [
        s for s in info["sections"]
        if any(kw in s["heading"].lower() for kw in limit_keywords)
    ]

    # Try to detect if paper has code
    info["has_code"] = bool(re.search(
        r'github\.com|gitlab\.com|code\s*(?:is\s*)?(?:available|released)',
        content, re.IGNORECASE
    ))

    # Try to detect paper type
    title_lower = info["title"].lower()
    abstract_lower = info.get("abstract", "").lower()[:500]
    combined = title_lower + " " + abstract_lower

    if any(w in combined for w in ["survey", "review", "综述"]):
        info["paper_type"] = "Survey/Review"
    elif any(w in combined for w in ["design", "development", "设计"]):
        info["paper_type"] = "System/Design"
    elif any(w in combined for w in ["experiment", "validation", "test", "实验"]):
        info["paper_type"] = "Experimental"
    elif any(w in combined for w in ["application", "applied", "应用"]):
        info["paper_type"] = "Application"
    else:
        info["paper_type"] = "Method"

    return info


def generate_comparison(papers: list) -> str:
    """Generate the comparison report."""
    n = len(papers)
    if n < 2:
        return "Error: Need at least 2 papers for comparison."

    # Build paper overview table
    paper_table_rows = []
    for i, p in enumerate(papers):
        row = f"| {i+1} | {p['title'][:50]} | {p['authors'][:30]} | {p['journal'][:25]} | {p['year']} | {p['doi'][:30]} |"
        paper_table_rows.append(row)

    # Build column headers for comparison tables
    col_headers = " | ".join([f"论文{i+1}" for i in range(n)])
    col_separator = "|".join(["------"] * (n + 1))

    # Build method comparison table
    method_rows = []
    for field in ["paper_type", "has_code"]:
        values = " | ".join([str(p.get(field, "N/A")) for p in papers])
        label = "论文类型" if field == "paper_type" else "开源代码"
        method_rows.append(f"| {label} | {values} |")

    # Build sections overview
    sections_overview = []
    for i, p in enumerate(papers):
        sec_list = [f"{s['heading']}" for s in p.get("sections", []) if s["level"] <= 2]
        sections_overview.append(f"### 论文{i+1}: {p['title'][:40]}\n" + "\n".join(f"- {s}" for s in sec_list[:10]))

    # Build limitations table
    limit_rows = []
    for i, p in enumerate(papers):
        limits = p.get("limitation_sections", [])
        if limits:
            limit_text = "; ".join([s["heading"] for s in limits[:3]])
        else:
            limit_text = "（需从正文中提取）"
        limit_rows.append(f"| 论文{i+1} | {limit_text} |")

    # Build stats table
    stats_rows = []
    for field, label in [("total_chars", "总字符数"), ("total_formulas", "公式数"),
                          ("total_figures", "图片数")]:
        values = " | ".join([f"{p.get(field, 0):,}" for p in papers])
        stats_rows.append(f"| {label} | {values} |")

    # Assemble report
    report = f"""# 多论文对比分析

> 论文数量: {n} 篇
> 生成日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}
> 对比维度: 研究问题、方法、实验、贡献、不足

---

## 📋 论文概览

| # | 标题 | 作者 | 期刊/会议 | 年份 | DOI |
|---|------|------|-----------|------|-----|
{chr(10).join(paper_table_rows)}

### 摘要

{chr(10).join([f"**论文{i+1}** ({p['title'][:40]}): {p.get('abstract', 'N/A')[:300]}..." for i, p in enumerate(papers)])}

### 统计信息

| 维度 | {col_headers} |
|------|{col_separator}|
{chr(10).join(stats_rows)}

---

## ❓ 研究问题对比

| 维度 | {col_headers} |
|------|{col_separator}|
| 论文类型 | {" | ".join([p.get("paper_type", "N/A") for p in papers])} |
| 核心问题 | {" | ".join(["（需分析）"] * n)} |
| 研究目标 | {" | ".join(["（需分析）"] * n)} |

**TODO: LLM 分析**
> 请基于各论文的摘要和引言，分析：
> 1. 各论文研究问题的异同
> 2. 是否存在互补或递进关系
> 3. 问题定义的差异

---

## 🔬 方法对比

| 维度 | {col_headers} |
|------|{col_separator}|
{chr(10).join(method_rows)}

### 章节结构对比

{chr(10).join(sections_overview)}

**TODO: LLM 分析**
> 请基于各论文的方法部分，分析：
> 1. 核心技术路线的差异
> 2. 创新点对比
> 3. 方法论优劣

---

## 📊 实验结果对比

**TODO: LLM 分析**
> 请基于各论文的实验部分，分析：
> 1. 共同基准测试的结果对比（构建对比表格）
> 2. 各方法的优势场景
> 3. 实验设计的差异

---

## ✅ 贡献与优势

**TODO: LLM 分析**
> 请为每篇论文列出 3-5 个核心贡献和优势。

---

## ⚠️ 不足与局限

| 论文 | 已知不足 |
|------|----------|
{chr(10).join(limit_rows)}

**TODO: LLM 分析**
> 请基于各论文的不足部分和你的判断，分析：
> 1. 各论文的具体局限
> 2. 共性问题
> 3. 哪些不足已被其他论文解决

---

## 🔗 相互关系

**TODO: LLM 分析**
> 请分析：
> 1. 引用关系（谁引用了谁）
> 2. 技术演进路线
> 3. 互补性分析

---

## 💡 综合评价与启发

**TODO: LLM 分析**
> 请总结：
> 1. 从这些论文中看到的研究趋势
> 2. 尚未解决的研究空白
> 3. 值得探索的未来方向
> 4. 实践建议

---

## 📚 原文关键摘录

**TODO: LLM 分析**
> 请从每篇论文中提取 3-5 条关键原文引用，涵盖核心贡献、方法创新、实验结论。
"""

    return report


def generate_content_json(papers: list) -> dict:
    """Generate a content JSON for PPT generation (comparison slides)."""
    n = len(papers)
    slides = []

    # Title slide
    slides.append({
        "type": "title",
        "title": "多论文对比分析",
        "subtitle": f"{n} 篇论文 · {datetime.now().strftime('%Y-%m-%d')}",
    })

    # Overview slide
    overview_content = [f"论文{i+1}: {p['title'][:50]}" for i, p in enumerate(papers)]
    slides.append({
        "type": "content",
        "title": "论文概览",
        "content": overview_content,
    })

    # Paper comparison table
    if n <= 4:  # Only for manageable number of papers
        headers = ["维度"] + [f"论文{i+1}" for i in range(n)]
        rows = []
        rows.append(["年份"] + [p.get("year", "N/A") for p in papers])
        rows.append(["期刊"] + [p.get("journal", "N/A")[:20] for p in papers])
        rows.append(["类型"] + [p.get("paper_type", "N/A") for p in papers])
        slides.append({
            "type": "table",
            "title": "基本信息对比",
            "table": {"headers": headers, "rows": rows},
        })

    # End slide
    slides.append({"type": "end"})

    return {
        "title": "多论文对比分析",
        "authors": "",
        "journal": "",
        "year": datetime.now().strftime("%Y"),
        "doi": "",
        "slides": slides,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate multi-paper comparison report")
    parser.add_argument("dirs", nargs="+", help="Paper directories (each with paper.md + metadata.json)")
    parser.add_argument("--output", "-o", default="comparison.md", help="Output comparison report (default: comparison.md)")
    parser.add_argument("--content-json", "-c", default=None, help="Also generate content JSON for PPT")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    args = parser.parse_args()

    if len(args.dirs) < 2:
        print("[ERROR] Need at least 2 paper directories for comparison.")
        sys.exit(1)

    # Load papers
    papers = []
    for d in args.dirs:
        if not os.path.isdir(d):
            print(f"[WARNING] Not a directory: {d}, skipping")
            continue

        paper = load_paper(d)
        if not paper["content"]:
            print(f"[WARNING] No paper.md found in {d}, skipping")
            continue

        info = extract_key_info(paper)
        papers.append(info)

        if not args.quiet:
            print(f"[Loaded] {info['title'][:60]} ({info['journal']}, {info['year']})")

    if len(papers) < 2:
        print("[ERROR] Fewer than 2 valid papers loaded. Cannot compare.")
        sys.exit(1)

    # Generate comparison report
    report = generate_comparison(papers)

    # Save report
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)

    if not args.quiet:
        print(f"\n=== Comparison Report Generated ===")
        print(f"Papers: {len(papers)}")
        print(f"Output: {args.output}")

    # Optionally generate content JSON for PPT
    if args.content_json:
        content = generate_content_json(papers)
        with open(args.content_json, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        if not args.quiet:
            print(f"Content JSON: {args.content_json}")


if __name__ == "__main__":
    main()
