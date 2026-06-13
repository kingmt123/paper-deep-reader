#!/usr/bin/env python3
"""
generate_index.py — Build a hierarchical section index for long papers.

Parses extracted paper.md into structured sections with:
- L0: paper metadata (title, authors, abstract) — always in context
- L1: per-section summary + structure + position info — always in context
- L2: full section text — loaded on demand by line range

Usage: python generate_index.py <paper.md> [index.json]

Output: JSON index file (default: paper_index.json in current directory)

The index enables efficient analysis of long documents (50+ pages):
- Short papers (<20 pages): may not need the index
- Long papers (20-50 pages): use L0 + L1 for overview, load L2 selectively
- Very long papers (50+ pages): mandatory — load sections on demand
"""

import sys
import os
import re
import json
import argparse


def parse_sections(text: str) -> list:
    """Parse markdown text into a tree of sections based on heading levels.
    
    Returns a flat list of section dicts, each with:
    - heading, level, line_start, line_end, content (full text of section)
    """
    lines = text.split("\n")
    sections = []
    current = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)

        if heading_match:
            # Save previous section
            if current:
                current["line_end"] = i - 1
                current["content"] = "\n".join(lines[current["line_start"]:i])
                sections.append(current)

            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            current = {
                "heading": heading_text,
                "level": level,
                "line_start": i,
                "line_end": None,
                "content": "",
            }

    # Save last section
    if current:
        current["line_end"] = len(lines) - 1
        current["content"] = "\n".join(lines[current["line_start"]:])
        sections.append(current)

    # If no headings found, treat entire text as one section
    if not sections:
        sections = [{
            "heading": "(Full Document)",
            "level": 1,
            "line_start": 0,
            "line_end": len(lines) - 1,
            "content": text,
        }]

    return sections


def extract_metadata(text: str) -> dict:
    """Extract paper metadata from the markdown text (L0 layer)."""
    meta = {}

    # Title: first H1
    match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    if match:
        meta["title"] = match.group(1).strip()

    # Authors: look for common patterns
    # Pattern 1: table row "| 作者 | ... |"
    author_match = re.search(r'\|\s*(?:作者|Authors?)\s*\|\s*(.+?)\s*\|', text)
    if author_match:
        meta["authors"] = author_match.group(1).strip()
    else:
        # Pattern 2: line after title that looks like author list (contains commas, capital letters)
        lines = text.split("\n")
        for line in lines[1:15]:  # check first 15 lines
            line = line.strip()
            if line and "," in line and any(c.isupper() for c in line):
                # Heuristic: looks like an author list
                if len(line) < 300 and not line.startswith("|") and not line.startswith("#"):
                    meta["authors"] = line
                    break

    # Abstract
    abs_match = re.search(
        r'(?i)(?:摘要|abstract)[:\s]*\n?(.*?)(?=\n\s*\n|\n\s*#|\n\s*\d+[\.\s])',
        text, re.DOTALL
    )
    if abs_match:
        meta["abstract"] = abs_match.group(1).strip()[:1000]

    # DOI
    doi_match = re.search(r'(10\.\d{4,}/[^\s\)\]&,]+)', text)
    if doi_match:
        meta["doi"] = doi_match.group(1).rstrip('.,;')

    # Journal/Conference
    journal_match = re.search(r'\|\s*(?:期刊|Journal|Conference)\s*\|\s*(.+?)\s*\|', text)
    if journal_match:
        meta["journal"] = journal_match.group(1).strip()

    # Year
    year_match = re.search(r'\|\s*(?:年份|Year)\s*\|\s*(\d{4})\s*\|', text)
    if year_match:
        meta["year"] = year_match.group(1)

    return meta


def analyze_section(section: dict) -> dict:
    """Analyze a section's content for special features (formulas, figures, algorithms, tables)."""
    content = section["content"]

    # Detect features
    has_formulas = bool(re.search(r'\$\$|\\\(|\\\[|\\begin\{equation', content))
    has_algorithms = bool(re.search(r'algorithm\s*\d|pseudocode|procedure\s+\w+', content, re.IGNORECASE))
    has_figures = bool(re.search(r'!\[.*?\]\(|figure\s+\d|fig\.\s*\d', content, re.IGNORECASE))
    has_tables = bool(re.search(r'\|.*\|.*\|', content))
    has_references = bool(re.search(r'^#+\s*(references|bibliography|参考文献)', content, re.IGNORECASE | re.MULTILINE))

    # Count special items
    formula_count = len(re.findall(r'\$\$.*?\$\$', content, re.DOTALL))
    formula_count += len(re.findall(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', content))
    figure_count = len(re.findall(r'!\[.*?\]\(|figure\s+\d|fig\.\s*\d', content, re.IGNORECASE))
    table_count = content.count("\n|") // 3  # rough estimate

    return {
        "char_count": len(content),
        "line_count": content.count("\n") + 1,
        "has_formulas": has_formulas,
        "has_algorithms": has_algorithms,
        "has_figures": has_figures,
        "has_tables": has_tables,
        "has_references": has_references,
        "formula_count": formula_count,
        "figure_count": figure_count,
        "table_count": table_count,
    }


def generate_summary(section: dict) -> str:
    """Generate a brief summary hint for the section based on content analysis.
    
    This is a heuristic summary (no LLM call). For production use,
    the LLM should generate proper summaries using this as context.
    """
    content = section["content"]
    heading = section["heading"]

    # Take first meaningful paragraph as summary hint
    lines = content.split("\n")
    summary_lines = []
    skip_heading = True
    for line in lines:
        stripped = line.strip()
        if skip_heading:
            if stripped.startswith("#"):
                continue
            skip_heading = False
        if not stripped:
            if summary_lines:
                break
            continue
        if stripped.startswith("|") or stripped.startswith("!") or stripped.startswith("```"):
            break
        if stripped.startswith(">"):
            stripped = stripped[1:].strip()
        summary_lines.append(stripped)

    summary = " ".join(summary_lines)[:200]

    # If summary is empty, use heading-based description
    if not summary:
        summary = f"[Section: {heading}]"

    return summary


def build_index(text: str, metadata: dict = None) -> dict:
    """Build the complete hierarchical index (L0 + L1 + L2 info)."""
    sections = parse_sections(text)

    if not metadata:
        metadata = extract_metadata(text)

    # Build section index
    section_index = []
    for i, sec in enumerate(sections):
        analysis = analyze_section(sec)
        summary = generate_summary(sec)

        entry = {
            "id": str(i),
            "heading": sec["heading"],
            "level": sec["level"],
            "summary": summary,
            "line_start": sec["line_start"],
            "line_end": sec["line_end"],
            **analysis,
        }
        section_index.append(entry)

    # Compute totals
    total_chars = sum(s["char_count"] for s in section_index)
    total_formulas = sum(s["formula_count"] for s in section_index)
    total_figures = sum(s["figure_count"] for s in section_index)
    total_tables = sum(s["table_count"] for s in section_index)

    # Determine paper scale
    estimated_pages = total_chars / 3000  # rough: ~3000 chars per page
    if estimated_pages > 50:
        scale = "very_long"
    elif estimated_pages > 20:
        scale = "long"
    else:
        scale = "short"

    # Build final index
    index = {
        "version": "1.0",
        "scale": scale,
        "estimated_pages": round(estimated_pages),
        "total_chars": total_chars,
        "total_lines": text.count("\n") + 1,
        "total_sections": len(section_index),
        "total_formulas": total_formulas,
        "total_figures": total_figures,
        "total_tables": total_tables,
        "paper_meta": metadata,
        "sections": section_index,
    }

    return index


def print_summary(index: dict):
    """Print a human-readable summary of the index."""
    meta = index.get("paper_meta", {})
    print(f"=== Paper Index Summary ===")
    print(f"  Title: {meta.get('title', 'N/A')[:70]}")
    print(f"  Scale: {index['scale']} (~{index['estimated_pages']} pages)")
    print(f"  Sections: {index['total_sections']}")
    print(f"  Characters: {index['total_chars']:,}")
    print(f"  Formulas: {index['total_formulas']}")
    print(f"  Figures: {index['total_figures']}")
    print(f"  Tables: {index['total_tables']}")
    print()
    print(f"  Section Map:")
    for sec in index["sections"]:
        indent = "  " * (sec["level"] - 1)
        flags = []
        if sec["has_formulas"]:
            flags.append(f"📐{sec['formula_count']}")
        if sec["has_figures"]:
            flags.append(f"🖼️{sec['figure_count']}")
        if sec["has_algorithms"]:
            flags.append("📝algo")
        if sec["has_tables"]:
            flags.append("📊")
        flag_str = " " + " ".join(flags) if flags else ""
        print(f"    {indent}{sec['heading']} [{sec['char_count']} chars]{flag_str}")


def main():
    parser = argparse.ArgumentParser(description="Build hierarchical section index for long papers")
    parser.add_argument("input", help="Extracted paper Markdown file (paper.md)")
    parser.add_argument("output", nargs="?", default="paper_index.json",
                       help="Output JSON index file (default: paper_index.json)")
    parser.add_argument("--metadata", "-m", help="External metadata JSON file to merge")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress summary output")
    args = parser.parse_args()

    # Read input
    if not os.path.exists(args.input):
        print(f"[ERROR] File not found: {args.input}")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    # Load external metadata if provided
    ext_meta = None
    if args.metadata and os.path.exists(args.metadata):
        with open(args.metadata, "r", encoding="utf-8") as f:
            ext_meta = json.load(f)

    # Build index
    index = build_index(text, metadata=ext_meta)

    # Save
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    if not args.quiet:
        print_summary(index)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"\n  Index saved: {args.output} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
