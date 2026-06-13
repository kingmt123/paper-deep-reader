#!/usr/bin/env python3
"""
generate_metadata.py — Extract paper metadata from PDF + external APIs.
Usage: python generate_metadata.py <pdf_path> [--arxiv-id ID] [--doi DOI]
"""

import json
import re
import argparse
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET


def extract_pymupdf_metadata(pdf_path: str) -> dict:
    """Extract metadata using PyMuPDF."""
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
        meta = doc.metadata
        # Also extract first page text for affiliation detection
        first_page_text = ""
        if len(doc) > 0:
            first_page_text = doc[0].get_text()[:2000]
        abstract = ""
        if len(doc) > 0:
            # Try to find abstract in first 2 pages
            for i in range(min(2, len(doc))):
                text = doc[i].get_text()
                lower = text.lower()
                abs_start = lower.find("abstract")
                if abs_start >= 0:
                    # Find the end of abstract (next section heading or double newline)
                    abs_text = text[abs_start:]
                    # Simple heuristic: take until next heading-like line
                    lines = abs_text.split("\n")
                    abstract_lines = []
                    for line in lines[1:]:  # skip "Abstract" line
                        if line.strip() == "":
                            if abstract_lines:
                                break
                            continue
                        # Stop at section-like headings
                        if line.strip() and line.strip()[0].isdigit() and len(line.strip()) < 20:
                            break
                        if line.strip().lower() in ["introduction", "1 introduction", "1. introduction"]:
                            break
                        abstract_lines.append(line.strip())
                    abstract = " ".join(abstract_lines)[:1000]
                    break
        doc.close()
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "abstract": abstract,
            "first_page_text": first_page_text,
            "source": "pymupdf"
        }
    except Exception as e:
        return {"error": str(e), "source": "pymupdf"}


def fetch_arxiv_metadata(arxiv_id: str) -> dict:
    """Fetch metadata from arXiv API."""
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "paper-deep-reader/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
        
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(data)
        entry = root.find("atom:entry", ns)
        if entry is None:
            return {"error": "No entry found", "source": "arxiv"}
        
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        abstract = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
        authors = []
        affiliations = []
        for author in entry.findall("atom:author", ns):
            name = author.find("atom:name", ns).text.strip()
            authors.append(name)
        
        # Get categories
        categories = []
        for cat in entry.findall("atom:category", ns):
            categories.append(cat.get("term", ""))
        
        # Get DOI if available
        doi = ""
        for link in entry.findall("atom:link", ns):
            pass  # arXiv API doesn't always include DOI
        
        # Check for journal_ref
        journal_ref = ""
        journal_elem = entry.find("atom:journal_ref", ns)
        if journal_elem is not None:
            journal_ref = journal_elem.text.strip()
        
        doi_elem = entry.find("atom:doi", ns)
        if doi_elem is not None:
            doi = doi_elem.text.strip()
        
        return {
            "title": title,
            "authors": ", ".join(authors),
            "abstract": abstract,
            "categories": ", ".join(categories),
            "doi": doi,
            "journal_ref": journal_ref,
            "arxiv_id": arxiv_id,
            "source": "arxiv"
        }
    except Exception as e:
        return {"error": str(e), "source": "arxiv"}


def fetch_crossref_metadata(doi: str) -> dict:
    """Fetch metadata from CrossRef API."""
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "paper-deep-reader/0.1 (mailto:user@example.com)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        work = data.get("message", {})
        
        # Extract authors
        authors = []
        affiliations = []
        for author in work.get("author", []):
            name_parts = []
            if "given" in author:
                name_parts.append(author["given"])
            if "family" in author:
                name_parts.append(author["family"])
            name = " ".join(name_parts)
            authors.append(name)
            if "affiliation" in author:
                for aff in author["affiliation"]:
                    affiliations.append(aff.get("name", ""))
        
        # Extract journal info
        journal = work.get("container-title", [""])[0] if work.get("container-title") else ""
        volume = work.get("volume", "")
        issue = work.get("issue", "")
        
        # Extract year
        year = ""
        if "published" in work and "date-parts" in work["published"]:
            parts = work["published"]["date-parts"][0]
            if parts:
                year = str(parts[0])
        
        title = work.get("title", [""])[0] if work.get("title") else ""
        
        return {
            "title": title,
            "authors": ", ".join(authors),
            "affiliations": ", ".join(set(affiliations)) if affiliations else "",
            "journal": journal,
            "volume": volume,
            "issue": issue,
            "year": year,
            "doi": doi,
            "source": "crossref"
        }
    except Exception as e:
        return {"error": str(e), "source": "crossref"}


def fetch_semantic_scholar(doi: str = None, arxiv_id: str = None, title: str = None) -> dict:
    """Fetch citation count from Semantic Scholar API."""
    if doi:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=citationCount,influentialCitationCount,title,year"
    elif arxiv_id:
        url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}?fields=citationCount,influentialCitationCount,title,year"
    elif title:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(title)}&limit=1&fields=citationCount,influentialCitationCount,title,year"
    else:
        return {"error": "No identifier provided", "source": "semantic_scholar"}
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "paper-deep-reader/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        if "data" in data:  # search result
            data = data["data"][0] if data["data"] else {}
        
        return {
            "citation_count": data.get("citationCount", "N/A"),
            "influential_citations": data.get("influentialCitationCount", "N/A"),
            "source": "semantic_scholar"
        }
    except Exception as e:
        return {"error": str(e), "source": "semantic_scholar"}


def merge_metadata(*sources) -> dict:
    """Merge metadata from multiple sources, prioritizing by reliability."""
    merged = {}
    # Priority: crossref > arxiv > pymupdf
    for source in sources:
        if "error" in source and source.get("error"):
            continue
        for key, value in source.items():
            if key in ("source", "first_page_text", "error"):
                continue
            if value and value != "N/A" and key not in merged:
                merged[key] = value
    return merged


def main():
    parser = argparse.ArgumentParser(description="Extract paper metadata")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--arxiv-id", help="arXiv paper ID")
    parser.add_argument("--doi", help="Paper DOI")
    parser.add_argument("--output", "-o", default="metadata.json", help="Output JSON file")
    args = parser.parse_args()
    
    print("=== Paper Metadata Extraction ===\n")
    
    # Step 1: PyMuPDF
    print("[1/4] Extracting from PDF (PyMuPDF)...")
    pymupdf_meta = extract_pymupdf_metadata(args.pdf_path)
    print(f"  Title: {pymupdf_meta.get('title', 'N/A')[:60]}")
    print(f"  Author: {pymupdf_meta.get('author', 'N/A')[:60]}")
    
    # Step 2: arXiv or CrossRef
    arxiv_meta = {}
    crossref_meta = {}
    
    if args.arxiv_id:
        print(f"\n[2/4] Fetching from arXiv ({args.arxiv_id})...")
        arxiv_meta = fetch_arxiv_metadata(args.arxiv_id)
        print(f"  Title: {arxiv_meta.get('title', 'N/A')[:60]}")
        print(f"  Authors: {arxiv_meta.get('authors', 'N/A')[:60]}")
    elif args.doi:
        print(f"\n[2/4] Fetching from CrossRef ({args.doi})...")
        crossref_meta = fetch_crossref_metadata(args.doi)
        print(f"  Title: {crossref_meta.get('title', 'N/A')[:60]}")
        print(f"  Journal: {crossref_meta.get('journal', 'N/A')}")
    else:
        # Try to find DOI from PyMuPDF metadata (subject field often contains DOI)
        doi_raw = pymupdf_meta.get("subject", "")
        doi_match = re.search(r'(10\.\d{4,}/[^\s,]+)', doi_raw)
        if doi_match:
            doi_from_pdf = doi_match.group(1).rstrip('.')
        elif doi_raw.startswith("10."):
            doi_from_pdf = doi_raw
        else:
            doi_from_pdf = ""
        if doi_from_pdf:
            print(f"\n[2/4] Found DOI in PDF: {doi_from_pdf}")
            crossref_meta = fetch_crossref_metadata(doi_from_pdf)
        else:
            print("\n[2/4] No DOI or arXiv ID provided, skipping external APIs")
    
    # Step 3: Semantic Scholar
    print("\n[3/4] Fetching citation count (Semantic Scholar)...")
    ss_meta = fetch_semantic_scholar(
        doi=args.doi or crossref_meta.get("doi"),
        arxiv_id=args.arxiv_id,
        title=pymupdf_meta.get("title")
    )
    print(f"  Citations: {ss_meta.get('citation_count', 'N/A')}")
    
    # Step 4: Merge
    print("\n[4/4] Merging metadata...")
    final = merge_metadata(crossref_meta, arxiv_meta, pymupdf_meta)
    final["citation_count"] = ss_meta.get("citation_count", "N/A")
    final["influential_citations"] = ss_meta.get("influential_citations", "N/A")
    
    # Remove internal fields
    final.pop("first_page_text", None)
    final.pop("abstract_text", None)
    
    # Add abstract if available
    if arxiv_meta.get("abstract"):
        final["abstract"] = arxiv_meta["abstract"]
    elif pymupdf_meta.get("abstract"):
        final["abstract"] = pymupdf_meta["abstract"]
    
    # Save
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== Saved to {output_path} ===")
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
