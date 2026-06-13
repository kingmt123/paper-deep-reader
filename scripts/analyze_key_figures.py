#!/usr/bin/env python3
"""
analyze_key_figures.py — NotebookLM key figure identification + deep analysis.

Uploads PDF to NotebookLM, asks it to identify the 3-5 most important figures,
then generates individual analysis files (one per figure) with deep解读.

Usage:
    python analyze_key_figures.py <pdf_path> <output_dir> [--max-figures 4] [--notebook-id ID]

Output:
    figures_analysis/
    ├── figure_1_analysis.md   — Figure 1 image + deep analysis
    ├── figure_2_analysis.md   — Figure 2 image + deep analysis
    ├── ...
    └── summary.md             — Overview of all key figures
"""

import json
import os
import sys
import re
import time
import subprocess
import argparse


def run_nb(*args, timeout=120, retries=2):
    """Run notebooklm command with retry."""
    cmd = ["notebooklm"] + list(args)
    env = os.environ.copy()
    home = os.path.expanduser("~")
    for p in [os.path.join(home, "AppData", "Roaming", "npm"), os.path.join(home, ".local", "bin")]:
        if os.path.isdir(p) and p not in env.get("PATH", ""):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")

    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                env=env, shell=(os.name == "nt")
            )
            if result.returncode == 0:
                return result.stdout.strip()
            stderr = (result.stderr or "").strip()
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                print(f"  [FAIL] notebooklm {' '.join(args[:2])}: {stderr[:200]}")
                return None
        except subprocess.TimeoutExpired:
            if attempt < retries:
                time.sleep(2)
            else:
                return None
        except FileNotFoundError:
            print("  [FAIL] 'notebooklm' not found. pip install notebooklm-py")
            return None
    return None


def check_auth():
    out = run_nb("auth", "check", "--test", "--json", timeout=30, retries=1)
    if out:
        try:
            d = json.loads(out)
            return d.get("status") == "ok" and d.get("checks", {}).get("token_fetch", False)
        except json.JSONDecodeError:
            pass
    return False


def create_notebook(title):
    out = run_nb("create", title, "--json", timeout=60, retries=2)
    if out:
        try:
            d = json.loads(out)
            return d.get("id") or d.get("notebook_id") or d.get("notebook", {}).get("id")
        except json.JSONDecodeError:
            pass
    return None


def add_source(notebook_id, pdf_path):
    out = run_nb("source", "add", pdf_path, "--notebook", notebook_id, "--json", timeout=120)
    if out:
        try:
            d = json.loads(out)
            return d.get("source_id") or d.get("id")
        except json.JSONDecodeError:
            pass
    return None


def wait_source(notebook_id, source_id, timeout=180):
    out = run_nb("source", "wait", source_id, "--timeout", str(timeout), timeout=timeout + 30)
    return out is not None


def ask(question, notebook_id):
    out = run_nb("ask", question, "--notebook", notebook_id, "--json", timeout=180)
    if out:
        try:
            d = json.loads(out)
            return d.get("answer", "") or d.get("response", "")
        except json.JSONDecodeError:
            pass
    out = run_nb("ask", question, "--notebook", notebook_id, timeout=180)
    return out


def find_image_for_figure(figure_desc, images_dir, paper_md_path):
    """Try to match a figure description to an actual image file."""
    paper_text = ""
    if os.path.exists(paper_md_path):
        with open(paper_md_path, "r", encoding="utf-8", errors="ignore") as f:
            paper_text = f.read()

    images = []
    if os.path.isdir(images_dir):
        for f in os.listdir(images_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                fpath = os.path.join(images_dir, f)
                sz = os.path.getsize(fpath)
                images.append((f, sz))
    images.sort(key=lambda x: x[1], reverse=True)

    fig_match = re.search(r'[Ff]ig(?:ure)?\.?\s*(\d+)', figure_desc)
    if fig_match:
        fig_num = fig_match.group(1)
        pattern = rf'[Ff]ig(?:ure)?\.?\s*{fig_num}.*?\n.*?!?\[.*?\]\((images/[^)]+)\)'
        m = re.search(pattern, paper_text, re.DOTALL)
        if m:
            img_ref = m.group(1)
            img_name = os.path.basename(img_ref)
            for fname, sz in images:
                if fname == img_name or img_name in fname:
                    return fname, sz

    if images:
        return images[0]

    return None, 0


def main():
    parser = argparse.ArgumentParser(description="NotebookLM key figure analysis")
    parser.add_argument("pdf", help="Paper PDF file")
    parser.add_argument("output_dir", nargs="?", default=".")
    parser.add_argument("--notebook-id", "-n", default=None,
                        help="Existing notebook ID (skip notebook creation and PDF upload)")
    parser.add_argument("--max-figures", type=int, default=4, help="Max key figures to analyze")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip PDF upload (use when source already added manually)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    images_dir = os.path.join(args.output_dir, "images")
    paper_md = os.path.join(args.output_dir, "paper.md")
    figures_dir = os.path.join(args.output_dir, "figures_analysis")
    os.makedirs(figures_dir, exist_ok=True)

    # ── Step 1: Check auth (REQUIRED) ──
    if not check_auth():
        print("\n" + "="*60)
        print("❌  NotebookLM 未登录")
        print("="*60)
        print("  notebooklm login")
        print("="*60)
        sys.exit(1)

    # ── Step 2: Get or create notebook ──
    notebook_id = args.notebook_id
    if not notebook_id:
        pdf_name = os.path.splitext(os.path.basename(args.pdf))[0][:50]
        title = f"图片分析 - {pdf_name}"
        print(f"[NotebookLM] Creating notebook: {title}")
        notebook_id = create_notebook(title)
        if not notebook_id:
            print("❌  无法创建 notebook")
            sys.exit(1)
        print(f"  ✓ Created: {notebook_id}")

    print(f"[NotebookLM] Notebook: {notebook_id[:20]}...")

    # ── Step 3: Upload PDF (skip if --skip-upload or --notebook-id with manual upload) ──
    if not args.skip_upload:
        print(f"[NotebookLM] Uploading PDF...")
        source_id = add_source(notebook_id, args.pdf)
        if not source_id:
            print("\n" + "="*60)
            print("⚠️  PDF 上传失败（subprocess 常见问题）")
            print("="*60)
            print("  请手动上传后重试:")
            print(f'  notebooklm source add "{args.pdf}" --notebook {notebook_id}')
            print(f"  然后重新运行: python {sys.argv[0]} \"{args.pdf}\" \"{args.output_dir}\" --notebook-id {notebook_id} --skip-upload")
            print("="*60)
            sys.exit(1)

        print(f"[NotebookLM] Processing...")
        if not wait_source(notebook_id, source_id):
            print("❌  PDF 处理超时")
            sys.exit(1)
        print("  ✓ PDF ready")

    # ── Step 4: Ask NotebookLM to identify key figures ──
    # CRITICAL: Keep prompts SHORT (~50 chars) to avoid 180s timeout
    print(f"\n[NotebookLM] Identifying key figures...")
    identify_prompt = f"找出论文中最重要的{args.max_figures}张图，按重要性排序。每张说明Figure编号、标题、内容、为什么重要。"
    figures_answer = ask(identify_prompt, notebook_id)
    if not figures_answer:
        print("❌  NotebookLM 无法识别图片")
        sys.exit(1)
    print(f"  ✓ Identified key figures ({len(figures_answer)} chars)")

    # ── Step 5: Deep analysis for each figure ──
    fig_sections = re.split(r'(?=##?\s*Figure\s*\d+)', figures_answer)
    fig_sections = [s.strip() for s in fig_sections if s.strip() and re.match(r'##?\s*Figure', s.strip())]

    print(f"\n[NotebookLM] Deep analysis for {len(fig_sections)} figures...")

    analysis_results = []
    for i, section in enumerate(fig_sections):
        fig_match = re.search(r'Figure\s*(\d+)', section)
        fig_num = fig_match.group(1) if fig_match else str(i+1)
        fig_title_match = re.search(r'##?\s*Figure\s*\d+[:\s]*(.+?)(?:\n|$)', section)
        fig_title = fig_title_match.group(1).strip() if fig_title_match else f"Figure {fig_num}"

        print(f"\n  [{i+1}/{len(fig_sections)}] Figure {fig_num}: {fig_title[:50]}...")

        # Short prompt to avoid timeout
        deep_prompt = f"对Figure {fig_num}进行深度解读：具体元素、关键数据、如何支持核心论点、可得结论。引用论文原文。"
        deep_answer = ask(deep_prompt, notebook_id)

        if not deep_answer:
            print(f"    ✗ No response")
            continue

        print(f"    ✓ {len(deep_answer)} chars")

        img_file, img_size = find_image_for_figure(f"Figure {fig_num} {fig_title}", images_dir, paper_md)

        analysis_results.append({
            "figure_num": fig_num,
            "title": fig_title,
            "overview": section,
            "deep_analysis": deep_answer,
            "image_file": img_file,
            "image_size": img_size,
        })

        time.sleep(3)

    # ── Step 6: Generate individual analysis files ──
    print(f"\n[Output] Generating {len(analysis_results)} figure analysis files...")

    for result in analysis_results:
        fig_num = result["figure_num"]
        filename = f"figure_{fig_num}_analysis.md"
        filepath = os.path.join(figures_dir, filename)

        lines = [
            f"# Figure {fig_num}: {result['title']}",
            "",
            f"> 论文图片深度解读 | NotebookLM 分析",
            "",
        ]

        if result["image_file"]:
            rel_path = f"../images/{result['image_file']}"
            lines.append(f"![Figure {fig_num}]({rel_path})")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 概述")
        lines.append("")
        lines.append(result["overview"])
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 深度解读")
        lines.append("")
        lines.append(result["deep_analysis"])

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  ✓ {filename}")

    # ── Step 7: Generate summary ──
    summary_path = os.path.join(figures_dir, "summary.md")
    lines = [
        "# 关键图片分析摘要",
        "",
        f"> 共识别 {len(analysis_results)} 张关键图片",
        "",
        "| # | Figure | 标题 | 图片文件 | 分析文件 |",
        "|---|--------|------|----------|----------|",
    ]
    for i, r in enumerate(analysis_results):
        img = r["image_file"] or "未匹配"
        lines.append(f"| {i+1} | Figure {r['figure_num']} | {r['title'][:40]} | {img} | [分析](figure_{r['figure_num']}_analysis.md) |")

    lines.append("")
    lines.append("## 使用方式")
    lines.append("")
    lines.append("每个分析文件包含：")
    lines.append("1. 图片引用（来自 MinerU Cloud 提取的 images/）")
    lines.append("2. NotebookLM 的概述（图片在论文中的角色）")
    lines.append("3. NotebookLM 的深度解读（详细分析 + 论文引用）")
    lines.append("")
    lines.append("这些分析可直接嵌入精读笔记的相关章节中。")

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✓ summary.md")

    # Save raw results
    json_path = os.path.join(figures_dir, "analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "notebook_id": notebook_id,
            "pdf": args.pdf,
            "figures_analyzed": len(analysis_results),
            "figures": analysis_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n=== Key Figure Analysis Complete ===")
    print(f"Figures: {len(analysis_results)}")
    print(f"Output: {figures_dir}/")


if __name__ == "__main__":
    main()
