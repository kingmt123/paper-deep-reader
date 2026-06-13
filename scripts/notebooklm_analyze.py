#!/usr/bin/env python3
"""
notebooklm_analyze.py — Upload PDF to NotebookLM and run deep analysis.

CRITICAL: Always uploads current PDF to notebook before asking questions.
Never asks questions without verifying the PDF is in the notebook.

Usage:
    python notebooklm_analyze.py <pdf_path> <output_dir> [--notebook-id ID]

Output:
    - notebooklm_analysis.json — structured analysis results
    - notebooklm_analysis.md   — Markdown summary for LLM consumption
"""

import json
import os
import sys
import time
import subprocess
import argparse


def run_nb(*args, timeout=60, retries=2):
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
                print(f"  [retry {attempt+1}/{retries}] notebooklm {' '.join(args[:2])} failed: {stderr[:120]}")
                time.sleep(2 ** attempt)
            else:
                print(f"  [FAIL] notebooklm {' '.join(args[:2])}: {stderr[:200]}")
                return None
        except subprocess.TimeoutExpired:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"  [FAIL] timeout after {retries+1} attempts")
                return None
        except FileNotFoundError:
            print("  [FAIL] 'notebooklm' not found. Install: pip install notebooklm-py")
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


def list_notebooks():
    out = run_nb("list", "--json", timeout=30, retries=1)
    if out:
        try:
            return json.loads(out).get("notebooks", [])
        except json.JSONDecodeError:
            pass
    return []


def create_notebook(title):
    """Create a new notebook. Returns notebook_id or None."""
    out = run_nb("create", title, "--json", timeout=60, retries=2)
    if out:
        try:
            d = json.loads(out)
            return d.get("id") or d.get("notebook_id") or d.get("notebook", {}).get("id")
        except json.JSONDecodeError:
            # Try to extract ID from plain text output
            if "id" in out.lower():
                return out
    return None


def add_source(notebook_id, pdf_path):
    """Add PDF as source. Returns source_id or None."""
    out = run_nb("source", "add", pdf_path, "--notebook", notebook_id, "--json", timeout=120)
    if out:
        try:
            d = json.loads(out)
            return d.get("source_id") or d.get("id")
        except json.JSONDecodeError:
            pass
    return None


def list_sources(notebook_id):
    """List sources in a notebook."""
    out = run_nb("source", "list", "--notebook", notebook_id, "--json", timeout=30)
    if out:
        try:
            return json.loads(out).get("sources", [])
        except json.JSONDecodeError:
            pass
    return []


def wait_source(notebook_id, source_id, timeout=180):
    """Wait for source processing to complete."""
    out = run_nb("source", "wait", source_id, "--timeout", str(timeout), timeout=timeout + 30)
    return out is not None


def ask(question, notebook_id):
    """Ask a question. Returns answer or None."""
    out = run_nb("ask", question, "--notebook", notebook_id, "--json", timeout=120)
    if out:
        try:
            d = json.loads(out)
            return d.get("answer", "") or d.get("response", "")
        except json.JSONDecodeError:
            pass
    out = run_nb("ask", question, "--notebook", notebook_id, timeout=120)
    return out


def save_empty_results(output_dir, status):
    """Save empty results when NotebookLM is unavailable."""
    with open(os.path.join(output_dir, "notebooklm_analysis.json"), "w") as f:
        json.dump({"status": status, "analyses": {}}, f, indent=2)
    with open(os.path.join(output_dir, "notebooklm_analysis.md"), "w") as f:
        f.write(f"<!-- NotebookLM: {status}, using LLM-only analysis -->\n")


def save_results(output_dir, notebook_id, pdf_path, results):
    """Save analysis results."""
    json_path = os.path.join(output_dir, "notebooklm_analysis.json")
    md_path = os.path.join(output_dir, "notebooklm_analysis.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "notebook_id": notebook_id,
            "pdf": pdf_path,
            "sections_analyzed": len(results),
            "analyses": results,
        }, f, ensure_ascii=False, indent=2)

    lines = ["<!-- NotebookLM 深度分析结果 → LLM 上下文 -->", ""]
    for section, data in results.items():
        lines.append(f"## NotebookLM: {section}")
        lines.append("")
        lines.append(data["answer"])
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, md_path


# Deep analysis prompts
ANALYSIS_PROMPTS = {
    "methodology": (
        "请详细分析这篇论文的方法论部分：\n"
        "1. 核心方法的技术路线是什么？\n"
        "2. 与同类方法相比有什么创新？\n"
        "3. 方法的关键假设是什么？\n"
        "4. 有哪些潜在的局限性？\n"
        "请引用论文原文支持你的回答。"
    ),
    "results": (
        "请分析这篇论文的实验部分：\n"
        "1. 主要实验结果是什么？\n"
        "2. 与 baseline 相比提升了多少？\n"
        "3. 实验设置是否合理？\n"
        "4. 结果是否支持论文的核心声明？\n"
        "请引用具体的表格和数据。"
    ),
    "limitations": (
        "这篇论文有哪些局限性？请从以下角度分析：\n"
        "1. 作者自己承认的局限\n"
        "2. 方法假设带来的限制\n"
        "3. 数据/实验规模的限制\n"
        "4. 不能从论文结果中得出的结论"
    ),
    "figures": (
        "请描述论文中最重要的3-5张图（Figure），包括：\n"
        "1. 每张图展示了什么内容\n"
        "2. 图中的关键数据或趋势\n"
        "3. 这些图如何支持论文的核心论点"
    ),
}


def print_auth_error():
    print("\n" + "="*60)
    print("⚠️  NotebookLM 未登录或认证已过期")
    print("="*60)
    print("  请先执行登录:")
    print("    notebooklm login")
    print("")
    print("  登录后验证:")
    print("    notebooklm auth check --test --json")
    print("")
    print("  如果 token 过期（超过几天未使用），需要重新登录。")
    print("="*60)
    print("  本次跳过 NotebookLM 分析，LLM 将使用文本-only 模式。")
    print("")


def main():
    parser = argparse.ArgumentParser(description="NotebookLM deep paper analysis")
    parser.add_argument("pdf", help="Paper PDF file")
    parser.add_argument("output_dir", nargs="?", default=".")
    parser.add_argument("--notebook-id", "-n", default=None,
                        help="Notebook ID to use. If not set, creates a new notebook.")
    parser.add_argument("--sections", nargs="*", default=None,
                        help="Sections: methodology, results, limitations, figures")
    parser.add_argument("--max-figures", type=int, default=4,
                        help="Max figures to analyze")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ── Step 1: Check auth (REQUIRED) ──
    if not check_auth():
        print("\n" + "="*60)
        print("❌  NotebookLM 未登录 — 这是必选步骤")
        print("="*60)
        print("  请先执行登录:")
        print("    notebooklm login")
        print("")
        print("  登录后验证:")
        print("    notebooklm auth check --test --json")
        print("="*60)
        sys.exit(1)

    # ── Step 2: Get or create notebook ──
    notebook_id = args.notebook_id
    if not notebook_id:
        # Create a NEW notebook for this paper (never reuse old ones)
        pdf_name = os.path.splitext(os.path.basename(args.pdf))[0][:50]
        title = f"精读 - {pdf_name}"
        print(f"[NotebookLM] Creating new notebook: {title}")
        notebook_id = create_notebook(title)
        if not notebook_id:
            print("\n" + "="*60)
            print("❌  无法创建 NotebookLM notebook — 必选步骤失败")
            print("="*60)
            print("  可能原因: 网络问题 / 服务不可用 / token过期")
            print("")
            print("  请手动创建:")
            print(f'    notebooklm create "{title}"')
            print("  然后用 --notebook-id <id> 指定")
            print("="*60)
            sys.exit(1)
        print(f"  ✓ Created: {notebook_id}")

    print(f"[NotebookLM] Notebook: {notebook_id[:20]}...")

    # ── Step 3: Upload PDF (ALWAYS, never skip) ──
    print(f"[NotebookLM] Uploading PDF: {os.path.basename(args.pdf)}")
    source_id = add_source(notebook_id, args.pdf)

    if not source_id:
        print("\n" + "="*60)
        print("❌  PDF 上传失败 — 必选步骤失败")
        print("="*60)
        print("  无法将当前论文上传到 NotebookLM。")
        print("  不继续提问（否则会查询错误的论文）。")
        print("")
        print("  请手动操作:")
        print(f"    notebooklm source add \"{args.pdf}\" --notebook {notebook_id}")
        print("="*60)
        sys.exit(1)

    # ── Step 4: Wait for processing ──
    print(f"[NotebookLM] Source ID: {source_id}")
    print(f"[NotebookLM] Waiting for PDF processing...")
    ready = wait_source(notebook_id, source_id, timeout=180)

    if not ready:
        print("\n" + "="*60)
        print("❌  PDF 处理超时 — 必选步骤失败")
        print("="*60)
        print("  NotebookLM 可能仍在处理，但已超过等待时间。")
        print("  不继续提问（否则可能查询未完成的源）。")
        print("="*60)
        sys.exit(1)

    print(f"  ✓ PDF processed and ready")

    # ── Step 5: Run analysis ──
    sections = args.sections or list(ANALYSIS_PROMPTS.keys())
    results = {}
    consecutive_failures = 0

    for section in sections:
        if section not in ANALYSIS_PROMPTS:
            print(f"[SKIP] Unknown section: {section}")
            continue

        print(f"\n[Analysis] {section}...")
        prompt = ANALYSIS_PROMPTS[section]
        answer = ask(prompt, notebook_id)

        if answer:
            consecutive_failures = 0
            results[section] = {
                "question": prompt,
                "answer": answer.strip()[:3000],
                "source": "notebooklm",
            }
            print(f"  ✓ {len(answer)} chars")
        else:
            consecutive_failures += 1
            print(f"  ✗ No response (streak: {consecutive_failures})")
            if consecutive_failures >= 3:
                print("\n⚠️  3 consecutive failures, stopping early.")
                break

        time.sleep(3)

    # ── Step 6: Save results ──
    json_path, md_path = save_results(args.output_dir, notebook_id, args.pdf, results)

    print(f"\n=== NotebookLM Analysis Complete ===")
    print(f"Sections: {len(results)}/{len(sections)}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
