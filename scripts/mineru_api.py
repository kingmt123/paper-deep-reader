#!/usr/bin/env python3
"""
mineru_api.py — MinerU Cloud API: PDF → Markdown + JSON

Supports both URL and LOCAL PDF via pre-signed upload.
Generates extraction_log.md with problem diagnosis on failure.

Flow (local PDF):
  1. POST /file-urls/batch → get pre-signed upload URL + batch_id
  2. PUT <upload_url> → upload PDF bytes (NO extra headers!)
  3. GET /extract-results/batch/<batch_id> → poll until done
  4. Download full_zip_url → extract paper.md + images/

Flow (URL):
  1. POST /extract/task → submit URL
  2. GET /extract/task/<task_id> → poll until done
  3. Download full_zip_url → extract paper.md + images/

Usage:
    python mineru_api.py <pdf_path_or_url> <output_dir> [--token TOKEN]

Output:
    - paper.md / full.md  — extracted Markdown
    - images/             — extracted figures
    - extraction_log.md   — diagnostics (always generated)
"""

import json
import os
import sys
import time
import zipfile
import argparse
import urllib.request
import urllib.parse
import subprocess

API_BASE = "https://mineru.net/api/v4"


def read_token(token_file=None):
    """Read MinerU API token from file."""
    if token_file and os.path.exists(token_file):
        with open(token_file, "r") as f:
            return f.read().strip()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "..", ".mineru_token"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes",
                     "skills", "research", "paper-deep-reader", ".mineru_token"),
        os.path.join(os.path.expanduser("~"), ".hermes", "skills",
                     "research", "paper-deep-reader", ".mineru_token"),
        os.path.join(os.path.expanduser("~"), ".mineru_token"),
    ]
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.exists(c):
            with open(c, "r") as f:
                return f.read().strip()
    return None


def _headers(token, content_type="application/json"):
    h = {"Authorization": f"Bearer {token}"}
    if content_type:
        h["Content-Type"] = content_type
    return h


# ── Local PDF upload flow ──────────────────────────────────────

def upload_step1_get_urls(token, filename, enable_formula=True, enable_table=True, language="en"):
    """POST /file-urls/batch → get pre-signed upload URL + batch_id."""
    body = json.dumps({
        "files": [{
            "name": filename,
            "is_ocr": False,
            "data_id": "doc_001",
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "language": language,
        }]
    }).encode()

    req = urllib.request.Request(
        f"{API_BASE}/file-urls/batch",
        headers=_headers(token),
        data=body, method="POST"
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())

    if resp.get("code") != 0:
        return None, None, resp.get("msg", "unknown error")

    batch_id = resp["data"]["batch_id"]
    upload_url = resp["data"]["file_urls"][0]
    return batch_id, upload_url, None


def upload_step2_put(upload_url, file_bytes, tmp_dir=None):
    """PUT PDF bytes to pre-signed URL via curl. CRITICAL: no Content-Type header!"""
    import tempfile
    # Write bytes to temp file (curl needs a file)
    fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=tmp_dir)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(file_bytes)
        # Use curl for reliable SSL (urllib fails with UNEXPECTED_EOF on some CDNs)
        result = subprocess.run(
            ["curl", "-X", "PUT", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", "120", "--ssl-no-revoke", "-T", tmp_path, upload_url],
            capture_output=True, timeout=150
        )
        status_code = result.stdout.decode("ascii", errors="replace").strip()
        return status_code in ("200", "201")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def upload_step3_poll(token, batch_id, max_wait=300, interval=5):
    """GET /extract-results/batch/<batch_id> → poll until done."""
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval

        try:
            req = urllib.request.Request(
                f"{API_BASE}/extract-results/batch/{batch_id}",
                headers=_headers(token, content_type=None)
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            yield {"state": "poll_error", "error": str(e), "elapsed": elapsed}
            continue

        results = resp.get("data", {}).get("extract_result", [])
        if not results:
            yield {"state": "waiting", "elapsed": elapsed}
            continue

        item = results[0]
        state = item.get("state", "unknown")

        if state == "done":
            yield {"state": "done", "data": item, "elapsed": elapsed}
            return
        elif state in ("failed", "error"):
            yield {"state": "failed", "error": json.dumps(item, ensure_ascii=False), "elapsed": elapsed}
            return
        else:
            yield {"state": state, "elapsed": elapsed}

    yield {"state": "timeout", "elapsed": elapsed}


# ── URL submission flow ────────────────────────────────────────

def url_submit(token, pdf_url, enable_formula=True, enable_table=True, language="en"):
    """POST /extract/task → submit URL for extraction."""
    body = json.dumps({
        "url": pdf_url,
        "enable_formula": enable_formula,
        "enable_table": enable_table,
        "language": language,
    }).encode()

    req = urllib.request.Request(
        f"{API_BASE}/extract/task",
        headers=_headers(token),
        data=body, method="POST"
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def url_poll(token, task_id, max_wait=300, interval=5):
    """GET /extract/task/<task_id> → poll until done."""
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval

        try:
            req = urllib.request.Request(
                f"{API_BASE}/extract/task/{task_id}",
                headers=_headers(token, content_type=None)
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            yield {"state": "poll_error", "error": str(e), "elapsed": elapsed}
            continue

        state = resp.get("data", {}).get("state", "unknown")

        if state == "done":
            yield {"state": "done", "data": resp["data"], "elapsed": elapsed}
            return
        elif state == "failed":
            yield {"state": "failed", "error": resp.get("data", {}).get("err_msg", "unknown"), "elapsed": elapsed}
            return
        else:
            yield {"state": state, "elapsed": elapsed}

    yield {"state": "timeout", "elapsed": elapsed}


# ── Download + Extract ─────────────────────────────────────────

def download_and_extract(zip_url, output_dir):
    """Download ZIP via curl and extract."""
    zip_path = os.path.join(output_dir, "mineru_result.zip")

    result = subprocess.run(
        ["curl", "-L", "-o", zip_path, zip_url, "--progress-bar", "--max-time", "120", "--ssl-no-revoke"],
        capture_output=True, text=True, timeout=150
    )
    if result.returncode != 0:
        return {"success": False, "error": f"curl failed: {result.stderr[:200]}"}

    if not os.path.exists(zip_path) or os.path.getsize(zip_path) < 100:
        size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
        return {"success": False, "error": f"Downloaded file too small ({size} bytes)"}

    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(output_dir)
    except zipfile.BadZipFile:
        return {"success": False, "error": "Not a valid ZIP file"}

    # Rename full.md → paper.md if needed
    full_md = os.path.join(output_dir, "full.md")
    paper_md = os.path.join(output_dir, "paper.md")
    if os.path.exists(full_md):
        if os.path.exists(paper_md):
            os.remove(paper_md)
        os.rename(full_md, paper_md)

    os.remove(zip_path)

    images_dir = os.path.join(output_dir, "images")
    n_images = len(os.listdir(images_dir)) if os.path.isdir(images_dir) else 0
    md_size = os.path.getsize(paper_md) if os.path.exists(paper_md) else 0

    return {"success": True, "n_images": n_images, "md_size": md_size}


# ── Diagnostics ────────────────────────────────────────────────

def generate_extraction_log(output_dir, input_info, steps, fallback_used=None):
    """Generate extraction_log.md with full diagnostics."""
    lines = [
        "# MinerU API 提取日志",
        "",
        f"- **时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **输入**: `{input_info}`",
        "",
    ]

    for step_name, step_data in steps:
        lines.append(f"## {step_name}")
        lines.append("")
        if isinstance(step_data, dict):
            for k, v in step_data.items():
                lines.append(f"- **{k}**: {v}")
        elif isinstance(step_data, str):
            lines.append(step_data)
        lines.append("")

    # Diagnosis for failures
    has_failure = any(d.get("success") == False for _, d in steps if isinstance(d, dict))
    if has_failure:
        lines.append("## 诊断与解决方案")
        lines.append("")

        for step_name, step_data in steps:
            if isinstance(step_data, dict) and step_data.get("error"):
                err = step_data["error"]
                if "403" in str(err) or "Forbidden" in str(err):
                    lines.append("### HTTP 403 — URL 被禁止访问")
                    lines.append("- **原因**: 目标服务器拒绝 MinerU Cloud 访问（反爬机制）")
                    lines.append("- **常见于**: MDPI、Springer、Elsevier 等出版商")
                    lines.append("- **解决**: PyMuPDF 本地提取（已自动兜底），或手动下载 PDF 后用本地路径")
                elif "corrupted" in str(err).lower():
                    lines.append("### PDF 文件无法解析")
                    lines.append("- **原因**: PDF 格式不标准或文件损坏")
                    lines.append("- **解决**: 重新下载 PDF，或使用 PyMuPDF 提取")
                elif "timeout" in str(err).lower():
                    lines.append("### 处理超时")
                    lines.append("- **原因**: PDF 过大或服务器繁忙")
                    lines.append("- **解决**: 稍后重试，或使用 PyMuPDF 提取")
                elif "SSL" in str(err) or "ssl" in str(err).lower():
                    lines.append("### SSL 连接失败")
                    lines.append("- **原因**: 网络 SSL 证书问题")
                    lines.append("- **解决**: 检查网络代理设置，或使用 PyMuPDF 提取")

    if fallback_used:
        lines.append(f"## 兜底方案: {fallback_used}")
        lines.append("")

    log_path = os.path.join(output_dir, "extraction_log.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return log_path


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MinerU Cloud API extraction")
    parser.add_argument("input", help="PDF URL or local file path")
    parser.add_argument("output_dir", nargs="?", default=".", help="Output directory")
    parser.add_argument("--token", default=None)
    parser.add_argument("--token-file", default=None)
    parser.add_argument("--language", default="en")
    parser.add_argument("--max-wait", type=int, default=300)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    token = args.token or read_token(args.token_file)
    if not token:
        print("[ERROR] No MinerU API token. Set --token or save to .mineru_token")
        sys.exit(1)

    is_url = args.input.startswith("http")
    steps = []
    final_result = None

    print(f"[MinerU Cloud] Input: {args.input} ({'URL' if is_url else 'Local PDF'})")

    # ── Read PDF content ──
    if is_url:
        # URL flow: check accessibility first
        print(f"[Step 0] Checking URL accessibility...")
        try:
            req = urllib.request.Request(args.input, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            steps.append(("URL 检查", {"状态": f"✓ HTTP {resp.status}", "类型": resp.headers.get("Content-Type", "?")}))
        except Exception as e:
            steps.append(("URL 检查", {"状态": "✗ 不可访问", "错误": str(e)}))
            print(f"  ✗ Not accessible: {e}")

        # Submit URL
        print(f"[Step 1] Submitting URL to MinerU API...")
        try:
            api_resp = url_submit(token, args.input, language=args.language)
            if api_resp.get("code") != 0:
                steps.append(("API 提交", {"状态": "✗", "错误": api_resp.get("msg", "?")}))
                log = generate_extraction_log(args.output_dir, args.input, steps)
                print(f"  ✗ {api_resp.get('msg', '?')}\n  Log: {log}")
                sys.exit(1)
            task_id = api_resp["data"]["task_id"]
            steps.append(("API 提交", {"状态": "✓", "Task ID": task_id}))
            print(f"  ✓ Task: {task_id}")
        except Exception as e:
            steps.append(("API 提交", {"状态": "✗", "错误": str(e)}))
            log = generate_extraction_log(args.output_dir, args.input, steps)
            print(f"  ✗ {e}\n  Log: {log}")
            sys.exit(1)

        # Poll
        print(f"[Step 2] Polling (max {args.max_wait}s)...")
        log_entries = []
        for status in url_poll(token, task_id, max_wait=args.max_wait):
            log_entries.append(status)
            if status["state"] == "done":
                print(f"  ✓ Done ({status['elapsed']}s)")
                zip_url = status["data"].get("full_zip_url")
                if zip_url:
                    print(f"[Step 3] Downloading...")
                    final_result = download_and_extract(zip_url, args.output_dir)
                break
            elif status["state"] == "failed":
                print(f"  ✗ Failed: {status.get('error', '?')}")
                steps.append(("轮询", {"状态": "✗", "错误": status.get("error", "?")}))
                break
            elif status["state"] == "timeout":
                steps.append(("轮询", {"状态": "⏰ 超时"}))
                break
            elif status["elapsed"] % 30 == 0:
                print(f"  ⏳ {status['elapsed']}s...")

    else:
        # ── Local PDF upload flow ──
        if not os.path.exists(args.input):
            print(f"[ERROR] File not found: {args.input}")
            sys.exit(1)

        filename = os.path.basename(args.input)
        with open(args.input, "rb") as f:
            file_bytes = f.read()
        print(f"[Step 0] Read local PDF: {len(file_bytes):,} bytes")
        steps.append(("读取文件", {"文件名": filename, "大小": f"{len(file_bytes):,} bytes"}))

        # Step 1: Get pre-signed upload URL
        print(f"[Step 1] Getting pre-signed upload URL...")
        batch_id, upload_url, err = upload_step1_get_urls(token, filename, language=args.language)
        if err:
            steps.append(("获取上传URL", {"状态": "✗", "错误": err}))
            log = generate_extraction_log(args.output_dir, args.input, steps)
            print(f"  ✗ {err}\n  Log: {log}")
            sys.exit(1)
        steps.append(("获取上传URL", {"状态": "✓", "Batch ID": batch_id}))
        print(f"  ✓ batch_id: {batch_id}")

        # Step 2: Upload PDF
        print(f"[Step 2] Uploading PDF to pre-signed URL...")
        try:
            ok = upload_step2_put(upload_url, file_bytes)
            if ok:
                steps.append(("上传PDF", {"状态": "✓"}))
                print(f"  ✓ Uploaded")
            else:
                steps.append(("上传PDF", {"状态": "✗"}))
                log = generate_extraction_log(args.output_dir, args.input, steps)
                print(f"  ✗ Upload failed\n  Log: {log}")
                sys.exit(1)
        except Exception as e:
            steps.append(("上传PDF", {"状态": "✗", "错误": str(e)}))
            log = generate_extraction_log(args.output_dir, args.input, steps)
            print(f"  ✗ {e}\n  Log: {log}")
            sys.exit(1)

        # Step 3: Poll
        print(f"[Step 3] Polling for results (max {args.max_wait}s)...")
        for status in upload_step3_poll(token, batch_id, max_wait=args.max_wait):
            if status["state"] == "done":
                print(f"  ✓ Done ({status['elapsed']}s)")
                zip_url = status["data"].get("full_zip_url")
                if zip_url:
                    print(f"[Step 4] Downloading and extracting...")
                    final_result = download_and_extract(zip_url, args.output_dir)
                else:
                    final_result = {"success": False, "error": "No full_zip_url in response"}
                break
            elif status["state"] == "failed":
                steps.append(("轮询", {"状态": "✗", "错误": status.get("error", "?")}))
                print(f"  ✗ Failed: {status.get('error', '?')}")
                break
            elif status["state"] == "timeout":
                steps.append(("轮询", {"状态": "⏰ 超时"}))
                break
            elif status["elapsed"] % 30 == 0:
                print(f"  ⏳ {status['elapsed']}s...")

    # ── Results ──
    if final_result and final_result.get("success"):
        steps.append(("提取结果", {"状态": "✓", "Markdown": f"{final_result['md_size']:,} bytes", "图片": f"{final_result['n_images']} 张"}))
        log = generate_extraction_log(args.output_dir, args.input, steps)
        print(f"\n=== Extraction Complete ===")
        print(f"Output: {args.output_dir}")
        print(f"Log: {log}")
    else:
        if final_result:
            steps.append(("提取结果", {"状态": "✗", "错误": final_result.get("error", "?")}))
        log = generate_extraction_log(args.output_dir, args.input, steps)
        print(f"\n=== Extraction Failed ===")
        print(f"See {log} for diagnosis.")
        sys.exit(1)


if __name__ == "__main__":
    main()
