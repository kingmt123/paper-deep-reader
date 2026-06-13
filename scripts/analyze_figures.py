#!/usr/bin/env python3
"""
analyze_figures.py — Analyze paper figures using NotebookLM.

Uses existing NotebookLM notebooks (does NOT create new ones).
If NotebookLM is unavailable, outputs empty results for LLM/vision fallback.

Usage: python analyze_figures.py <paper.pdf> [output_dir] [--images-dir DIR] [--notebook-id ID]

Output:
  - figure_analysis.json — structured data
  - figure_snippets.md — Markdown snippets ready for embedding
"""

import sys
import os
import json
import argparse
import subprocess
import time


def get_env():
    """Build subprocess env with proper PATH propagation."""
    env = os.environ.copy()
    # Ensure common CLI tool locations are in PATH
    extra_paths = []
    home = os.path.expanduser("~")
    for p in [
        os.path.join(home, "AppData", "Roaming", "npm"),
        os.path.join(home, ".local", "bin"),
        "/usr/local/bin",
    ]:
        if os.path.isdir(p) and p not in env.get("PATH", ""):
            extra_paths.append(p)
    if extra_paths:
        env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")
    return env


def run_nb(*args, timeout=60, retries=2):
    """Run a notebooklm command with retry. Returns stdout or None."""
    cmd = ["notebooklm"] + list(args)
    env = get_env()

    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                shell=(os.name == "nt"),  # Windows needs shell=True for npm-installed CLI
            )
            if result.returncode == 0:
                return result.stdout.strip()

            # Log failure for debugging
            stderr = (result.stderr or "").strip()
            if attempt < retries:
                wait = 2 ** attempt
                print(f"  [retry {attempt+1}/{retries}] notebooklm {' '.join(args[:2])} failed "
                      f"(rc={result.returncode}): {stderr[:120]}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [FAIL] notebooklm {' '.join(args[:2])} after {retries+1} attempts: "
                      f"{stderr[:200]}")
                return None

        except subprocess.TimeoutExpired:
            if attempt < retries:
                print(f"  [retry {attempt+1}/{retries}] timeout ({timeout}s). Retrying...")
                time.sleep(2)
            else:
                print(f"  [FAIL] timeout after {retries+1} attempts")
                return None
        except FileNotFoundError:
            print("  [FAIL] 'notebooklm' command not found. Is notebooklm-py installed?")
            return None
        except Exception as e:
            print(f"  [FAIL] unexpected error: {e}")
            return None

    return None


def check_auth():
    """Check if NotebookLM is authenticated."""
    out = run_nb("auth", "check", "--test", "--json", timeout=30, retries=1)
    if out:
        try:
            data = json.loads(out)
            return data.get("status") == "ok" and data.get("checks", {}).get("token_fetch", False)
        except json.JSONDecodeError:
            pass
    return False


def list_notebooks():
    """List existing notebooks."""
    out = run_nb("list", "--json", timeout=30, retries=1)
    if out:
        try:
            data = json.loads(out)
            return data.get("notebooks", [])
        except json.JSONDecodeError:
            pass
    return []


def add_source(notebook_id, pdf_path):
    """Add PDF as source to an existing notebook."""
    out = run_nb("source", "add", pdf_path, "--notebook", notebook_id, "--json", timeout=120)
    if out:
        try:
            data = json.loads(out)
            return data.get("source_id") or data.get("id")
        except json.JSONDecodeError:
            pass
    return None


def wait_source(notebook_id, source_id, timeout=180):
    """Wait for source processing."""
    out = run_nb("source", "wait", source_id, "--timeout", str(timeout), timeout=timeout + 30)
    return out is not None


def ask(question, notebook_id):
    """Ask a question to a notebook."""
    out = run_nb("ask", question, "--notebook", notebook_id, "--json", timeout=120)
    if out:
        try:
            data = json.loads(out)
            return data.get("answer", "") or data.get("response", "")
        except json.JSONDecodeError:
            pass
    # Fallback: try without --json
    out = run_nb("ask", question, "--notebook", notebook_id, timeout=120)
    return out


def get_image_files(images_dir):
    """Get image files sorted by page number."""
    if not images_dir or not os.path.isdir(images_dir):
        return []
    exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
    images = [f for f in sorted(os.listdir(images_dir)) if os.path.splitext(f)[1].lower() in exts]
    def sort_key(name):
        parts = name.replace("page", "").split("_")
        try:
            return int(parts[0])
        except (ValueError, IndexError):
            return 999
    images.sort(key=sort_key)
    return images


def save_empty_results(output_dir, status="no_notebook"):
    """Save empty results for downstream fallback."""
    with open(os.path.join(output_dir, "figure_analysis.json"), "w") as f:
        json.dump({"status": status, "figures": {}}, f, indent=2)
    with open(os.path.join(output_dir, "figure_snippets.md"), "w") as f:
        f.write(f"<!-- NotebookLM figure analysis: {status} -->\n")
    print(f"  Saved empty results (status={status}). LLM/vision fallback available.")


def main():
    parser = argparse.ArgumentParser(description="Analyze paper figures using NotebookLM")
    parser.add_argument("pdf", help="Paper PDF file")
    parser.add_argument("output_dir", nargs="?", default=".")
    parser.add_argument("--images-dir", "-img", default=None)
    parser.add_argument("--notebook-id", "-n", default=None, help="Notebook ID to use. If not set, creates a new notebook.")
    parser.add_argument("--max-figures", type=int, default=5)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Check auth (REQUIRED)
    if not check_auth():
        print("\n" + "="*60)
        print("❌  NotebookLM 未登录 — 这是必选步骤")
        print("="*60)
        print("  请先执行登录:")
        print("    notebooklm login")
        print("="*60)
        sys.exit(1)

    # Find or use notebook
    notebook_id = args.notebook_id
    if not notebook_id:
        notebooks = list_notebooks()
        if not notebooks:
            print("\n" + "="*60)
            print("❌  NotebookLM 中没有可用的 notebook — 必选步骤失败")
            print("="*60)
            print("  请创建: notebooklm create \"Paper Analysis\"")
            print("  然后用 --notebook-id <id> 指定")
            print("="*60)
            sys.exit(1)

        notebook = notebooks[-1]
        notebook_id = notebook["id"]
        print(f"[NotebookLM] Using: {notebook.get('title', 'N/A')} ({notebook_id[:12]}...)")

    # ALWAYS upload PDF to ensure notebook has the correct paper
    print(f"[NotebookLM] Adding source: {args.pdf}")
    source_id = add_source(notebook_id, args.pdf)
    if source_id:
        print(f"[NotebookLM] Waiting for processing...")
        wait_source(notebook_id, source_id)
    else:
        print("[WARNING] Failed to add source — notebook may have wrong paper content")

    # Get images (auto-detect images_hq/ first)
    images_dir = args.images_dir
    if not images_dir:
        hq_dir = os.path.join(args.output_dir, "images_hq")
        if os.path.isdir(hq_dir) and len(os.listdir(hq_dir)) > 0:
            images_dir = hq_dir
        else:
            images_dir = os.path.join(args.output_dir, "images")
    args.images_dir = images_dir
    images = get_image_files(args.images_dir)
    print(f"[Images] Found {len(images)} images")

    if not images:
        print("[WARNING] No images found. Skipping figure analysis.")
        save_empty_results(args.output_dir, "no_images")
        return

    # Select top figures by size (skip logos/pages 1-2)
    figures_to_analyze = []
    for img_name in images:
        page_str = img_name.replace("page", "").split("_")[0]
        try:
            page_num = int(page_str)
        except ValueError:
            page_num = 99
        if page_num <= 2:  # Skip title/logos
            continue
        img_path = os.path.join(args.images_dir, img_name) if args.images_dir else ""
        img_size = os.path.getsize(img_path) if os.path.exists(img_path) else 0
        figures_to_analyze.append((img_name, page_num, img_size))

    figures_to_analyze.sort(key=lambda x: x[2], reverse=True)
    figures_to_analyze = figures_to_analyze[:args.max_figures]
    figures_to_analyze.sort(key=lambda x: x[1])

    if not figures_to_analyze:
        print("[WARNING] No figures to analyze (all were logos/title images).")
        save_empty_results(args.output_dir, "no_figures")
        return

    print(f"[Analysis] Analyzing {len(figures_to_analyze)} figures")

    # Analyze each figure
    figure_results = {}
    consecutive_failures = 0

    for i, (img_name, page_num, _) in enumerate(figures_to_analyze):
        print(f"\n[{i+1}/{len(figures_to_analyze)}] {img_name} (page {page_num})...")

        desc = ask(
            f"Describe the figure on page {page_num} in detail. "
            f"What does it show? Key components, labels, data points?",
            notebook_id
        )

        if not desc:
            consecutive_failures += 1
            print(f"  ✗ No response (failure streak: {consecutive_failures})")
            if consecutive_failures >= 3:
                print("\n[WARNING] 3 consecutive failures. NotebookLM may be unstable.")
                print("  Stopping early. Partial results saved.")
                break
            continue

        consecutive_failures = 0  # Reset on success

        takeaway = ask(
            f"What is the single most important insight from the figure on page {page_num}? One sentence.",
            notebook_id
        )

        figure_results[img_name] = {
            "filename": img_name,
            "page": page_num,
            "description": (desc or "").strip()[:600],
            "key_takeaway": (takeaway or "").strip()[:200],
            "source": "notebooklm",
        }
        print(f"  ✓ {(takeaway or desc)[:80]}...")
        time.sleep(3)

    # Generate outputs
    json_path = os.path.join(args.output_dir, "figure_analysis.json")
    md_path = os.path.join(args.output_dir, "figure_snippets.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "notebook_id": notebook_id,
            "pdf": args.pdf,
            "analyzed_figures": len(figure_results),
            "total_images": len(images),
            "figures": figure_results,
        }, f, ensure_ascii=False, indent=2)

    # Generate markdown snippets
    lines = ["<!-- NotebookLM 图片分析结果 -->", ""]
    for img_name, fig in figure_results.items():
        lines.append(f"![{fig.get('key_takeaway', '')}](images/{img_name})")
        lines.append(f"> **描述**: {fig.get('description', '无描述')[:300]}")
        if fig.get("key_takeaway"):
            lines.append(f"> **关键信息**: {fig['key_takeaway']}")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n=== Figure Analysis Complete ===")
    print(f"Notebook: {notebook_id}")
    print(f"Analyzed: {len(figure_results)}/{len(figures_to_analyze)} figures")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")

    if len(figure_results) < len(figures_to_analyze):
        print(f"\nNote: {len(figures_to_analyze) - len(figure_results)} figures failed.")
        print("  The LLM can use vision_analyze on remaining images as fallback.")


if __name__ == "__main__":
    main()
