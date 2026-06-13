#!/usr/bin/env python3
"""
figure_mapper.py — Map extracted images to their figure captions using MinerU layout.json.

Uses spatial proximity: finds text blocks near each image block that contain
"Figure N" or "Fig. N" patterns, then maps them to extracted image files.

Usage: python figure_mapper.py <output_dir> [--paper-md paper.md]

Output: figure_map.json mapping image filenames to:
  - page number
  - figure number (e.g., "Figure 1")
  - caption text
  - bbox coordinates
  - matched image filename from images/ directory
"""

import os
import re
import json
import argparse


def load_layout(layout_path):
    """Load MinerU layout.json."""
    with open(layout_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_image_blocks(layout):
    """Extract image blocks with page numbers and bounding boxes."""
    images = []
    for page in layout.get("pdf_info", []):
        page_idx = page.get("page_idx", 0)
        for block in page.get("preproc_blocks", []):
            if block.get("type") == "image":
                images.append({
                    "page": page_idx,
                    "bbox": block.get("bbox", []),
                    "score": block.get("score", 0),
                })
    return images


def find_caption_blocks(layout):
    """Extract text blocks that look like figure captions."""
    captions = []
    for page in layout.get("pdf_info", []):
        page_idx = page.get("page_idx", 0)
        for block in page.get("preproc_blocks", []):
            if block.get("type") != "text":
                continue
            # Combine all lines in the block
            text = " ".join(
                line.get("text", "") for line in block.get("lines", [])
            ).strip()
            # Check if it looks like a figure caption
            if re.search(r'(?i)^(fig\.?|figure)\s*\d+', text):
                fig_match = re.match(r'(?i)(fig\.?|figure)\s*(\d+[a-z]?)', text)
                fig_num = fig_match.group(2) if fig_match else "?"
                captions.append({
                    "page": page_idx,
                    "figure_num": fig_num,
                    "text": text[:300],
                    "bbox": block.get("bbox", []),
                })
    return captions


def find_captions_in_text(paper_md_path):
    """Parse paper.md for figure captions like 'Fig. 1 | ...' or 'Figure N: ...'."""
    if not os.path.exists(paper_md_path):
        return []
    
    with open(paper_md_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    
    captions = []
    # Pattern 1: "Fig. N | caption text"
    for match in re.finditer(r'(?i)(Fig\.?|Figure)\s*(\d+[a-z]?)\s*[|:–-]\s*(.+?)(?:\n|$)', text):
        fig_num = match.group(2)
        cap_text = match.group(3).strip()[:300]
        # Estimate page from character position
        char_pos = match.start()
        total_chars = len(text)
        # Rough page estimation (will be refined if layout.json available)
        captions.append({
            "figure_num": fig_num,
            "text": cap_text,
            "char_position": char_pos,
            "source": "paper_md",
        })
    
    # Pattern 2: "Figure N." at start of line
    for match in re.finditer(r'(?i)^((?:Fig\.?|Figure)\s*\d+[a-z]?)\.\s*(.+?)(?:\n|$)', text, re.MULTILINE):
        fig_num = re.search(r'\d+', match.group(1)).group()
        cap_text = match.group(2).strip()[:300]
        if not any(c["figure_num"] == fig_num for c in captions):
            captions.append({
                "figure_num": fig_num,
                "text": cap_text,
                "char_position": match.start(),
                "source": "paper_md",
            })
    
    return captions


def match_images_to_captions(image_blocks, caption_blocks, images_dir):
    """Match image blocks to their nearest caption by spatial proximity."""
    # Get list of actual image files
    if not os.path.isdir(images_dir):
        return {}
    
    exts = {".png", ".jpg", ".jpeg", ".gif"}
    image_files = sorted([
        f for f in os.listdir(images_dir)
        if os.path.splitext(f)[1].lower() in exts
    ])
    
    # Parse page numbers from filenames
    file_pages = {}
    for f in image_files:
        match = re.match(r'page(\d+)_img(\d+)', f)
        if match:
            page_num = int(match.group(1))
            img_idx = int(match.group(2))
            if page_num not in file_pages:
                file_pages[page_num] = []
            file_pages[page_num].append((f, img_idx))
    
    # For each image block, find the nearest caption
    result = {}
    used_captions = set()
    
    for img_block in image_blocks:
        page = img_block["page"]
        img_bbox = img_block["bbox"]
        img_center_y = (img_bbox[1] + img_bbox[3]) / 2 if len(img_bbox) >= 4 else 0
        
        # Find captions on the same page or adjacent pages
        best_caption = None
        best_dist = float("inf")
        
        for cap in caption_blocks:
            cap_key = f"{cap['page']}_{cap['figure_num']}"
            if cap_key in used_captions:
                continue
            
            # Prefer same page, allow adjacent pages
            page_dist = abs(cap["page"] - page)
            if page_dist > 1:
                continue
            
            cap_bbox = cap["bbox"]
            cap_center_y = (cap_bbox[1] + cap_bbox[3]) / 2 if len(cap_bbox) >= 4 else 0
            
            # Distance: page distance * 1000 + vertical distance
            dist = page_dist * 1000 + abs(cap_center_y - img_center_y)
            
            if dist < best_dist:
                best_dist = dist
                best_caption = cap
        
        # Match to an image file
        matched_file = None
        page_files = file_pages.get(page, [])
        if page_files:
            # Use the first unmatched image on this page
            for f, idx in page_files:
                if f not in result:
                    matched_file = f
                    break
            if not matched_file and page_files:
                matched_file = page_files[0][0]
        
        if matched_file:
            entry = {
                "filename": matched_file,
                "page": page,
                "figure_num": best_caption["figure_num"] if best_caption else "?",
                "caption": best_caption["text"] if best_caption else "",
                "image_bbox": [round(x) for x in img_bbox],
                "caption_bbox": [round(x) for x in best_caption["bbox"]] if best_caption else [],
                "confidence": "high" if best_caption and best_dist < 200 else "medium" if best_caption else "low",
            }
            result[matched_file] = entry
            if best_caption:
                used_captions.add(f"{best_caption['page']}_{best_caption['figure_num']}")
    
    return result


def cross_reference_with_text(figure_map, paper_md_path):
    """Cross-reference figure map with paper.md text for additional validation."""
    if not os.path.exists(paper_md_path):
        return figure_map
    
    with open(paper_md_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    
    # Find all "Figure N" references in text with surrounding context
    fig_refs = {}
    for match in re.finditer(r'(?i)(fig(?:ure)?\.?\s*(\d+[a-z]?))[^.]*\.?', text):
        fig_num = match.group(2)
        context = match.group(0)[:200]
        if fig_num not in fig_refs:
            fig_refs[fig_num] = context
    
    # Update figure map with text references
    for fname, entry in figure_map.items():
        fig_num = entry.get("figure_num", "")
        if fig_num in fig_refs:
            entry["text_reference"] = fig_refs[fig_num]
    
    return figure_map


def generate_markdown_summary(figure_map):
    """Generate a markdown summary of the figure map."""
    lines = ["# 图片-图注映射表", ""]
    lines.append("| 图片文件 | Figure # | 置信度 | 图注 |")
    lines.append("|----------|----------|--------|------|")
    
    for fname in sorted(figure_map.keys()):
        entry = figure_map[fname]
        cap = entry.get("caption", "")[:60]
        fig = entry.get("figure_num", "?")
        conf = entry.get("confidence", "?")
        lines.append(f"| {fname} | Figure {fig} | {conf} | {cap} |")
    
    lines.append("")
    lines.append("## 高置信度图片（可直接用于笔记）")
    for fname, entry in figure_map.items():
        if entry.get("confidence") == "high":
            lines.append(f"- `{fname}` → Figure {entry['figure_num']}: {entry.get('caption', '')[:80]}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Map images to figure captions")
    parser.add_argument("output_dir", help="Directory with images/ and paper.md")
    parser.add_argument("--paper-md", default=None, help="Paper markdown path")
    parser.add_argument("--images-dir", default=None, help="Images directory (default: output_dir/images, use images_hq for PyMuPDF HQ)")
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()
    
    layout_path = os.path.join(args.output_dir, "layout.json")
    images_dir = args.images_dir or os.path.join(args.output_dir, "images")
    paper_md = args.paper_md or os.path.join(args.output_dir, "paper.md")
    
    # Always parse paper.md for captions (works with both MinerU and PyMuPDF)
    text_captions = find_captions_in_text(paper_md)
    
    # If layout.json available, use spatial matching
    if os.path.exists(layout_path):
        try:
            layout = load_layout(layout_path)
            image_blocks = find_image_blocks(layout)
            caption_blocks = find_caption_blocks(layout)
            # Combine layout captions with text captions
            all_captions = caption_blocks + text_captions
            figure_map = match_images_to_captions(image_blocks, all_captions, images_dir)
            method = "layout+text"
        except Exception as e:
            # MinerU Cloud layout.json has different format — fall back to text-only
            print(f"[figure_mapper] Layout parsing failed ({e}), using text-only mode")
            figure_map = match_by_page_number(text_captions, images_dir)
            method = "text_only"
    else:
        # No layout.json (PyMuPDF): match by page number from filenames
        figure_map = match_by_page_number(text_captions, images_dir)
        method = "text_only"
    
    figure_map = cross_reference_with_text(figure_map, paper_md)
    
    # Save JSON
    json_path = os.path.join(args.output_dir, "figure_map.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "status": "ok",
            "method": method,
            "total_images": len(figure_map),
            "high_confidence": sum(1 for v in figure_map.values() if v.get("confidence") == "high"),
            "figures": figure_map,
        }, f, ensure_ascii=False, indent=2)
    
    # Save markdown summary
    md_path = os.path.join(args.output_dir, "figure_map.md")
    md_content = generate_markdown_summary(figure_map)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    if not args.quiet:
        print(f"=== Figure Mapping Complete ===")
        print(f"Method: {method}")
        print(f"Text captions found: {len(text_captions)}")
        print(f"Matched: {len(figure_map)}")
        print(f"High confidence: {sum(1 for v in figure_map.values() if v.get('confidence') == 'high')}")
        print(f"JSON: {json_path}")
        print(f"Markdown: {md_path}")


def match_by_page_number(text_captions, images_dir):
    """Match captions to images by page number (for PyMuPDF output without layout.json)."""
    if not os.path.isdir(images_dir):
        return {}
    
    exts = {".png", ".jpg", ".jpeg", ".gif"}
    image_files = sorted([
        f for f in os.listdir(images_dir)
        if os.path.splitext(f)[1].lower() in exts
    ])
    
    # Parse page numbers from filenames
    file_pages = {}
    for f in image_files:
        match = re.match(r'page(\d+)_img(\d+)', f)
        if match:
            page_num = int(match.group(1))
            img_idx = int(match.group(2))
            if page_num not in file_pages:
                file_pages[page_num] = []
            file_pages[page_num].append((f, img_idx))
    
    # Estimate page for each caption based on character position
    if not text_captions:
        return {}
    
    total_chars = max(c.get("char_position", 0) for c in text_captions) + 1
    max_page = max(file_pages.keys()) if file_pages else 1
    
    result = {}
    used_files = set()
    
    for cap in text_captions:
        fig_num = cap.get("figure_num", "?")
        char_pos = cap.get("char_position", 0)
        # Estimate page from character position
        est_page = max(1, int((char_pos / total_chars) * max_page) + 1)
        
        # Find closest image file
        best_file = None
        best_dist = 999
        for page_num, files in file_pages.items():
            dist = abs(page_num - est_page)
            if dist < best_dist:
                for f, idx in files:
                    if f not in used_files:
                        best_dist = dist
                        best_file = f
                        break
        
        if best_file:
            result[best_file] = {
                "filename": best_file,
                "estimated_page": est_page,
                "figure_num": fig_num,
                "caption": cap.get("text", ""),
                "confidence": "medium" if best_dist <= 2 else "low",
                "source": "text_matching",
            }
            used_files.add(best_file)
    
    return result


if __name__ == "__main__":
    main()
