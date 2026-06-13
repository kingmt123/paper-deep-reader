"""
extract_paper.py - Unified paper extraction using MinerU API + PyMuPDF fallback
Usage: python extract_paper.py <input> <output_dir> [--token TOKEN_FILE]

Input can be:
- arXiv URL: https://arxiv.org/abs/XXXX.XXXXX
- DOI: 10.xxxx/xxxx
- Local PDF path: /path/to/paper.pdf
- PDF URL: https://example.com/paper.pdf

Output:
- output_dir/full.md (or paper.md for PyMuPDF)
- output_dir/images/
- output_dir/metadata.json
"""

import urllib.request
import urllib.parse
import json
import time
import zipfile
import os
import sys
import re


def read_token(token_file=None):
    """Read MinerU API token from file."""
    if token_file and os.path.exists(token_file):
        with open(token_file) as f:
            return f.read().strip()
    
    # Try default locations
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_paths = [
        os.path.join(script_dir, "..", ".mineru_token"),  # relative to skill scripts/
        os.path.expanduser(r"~\AppData\Local\hermes\skills\research\paper-deep-reader\.mineru_token"),
        os.path.expanduser(r"~\.hermes\skills\research\paper-deep-reader\.mineru_token"),
        os.path.expanduser(r"~\.mineru_token"),
    ]
    for p in default_paths:
        if os.path.exists(p):
            with open(p) as f:
                return f.read().strip()
    return None


def is_url(text):
    """Check if text is a URL."""
    return text.startswith("http://") or text.startswith("https://")


def is_arxiv_url(text):
    """Check if text is an arXiv URL."""
    return "arxiv.org" in text


def is_doi(text):
    """Check if text looks like a DOI (10.xxxx/yyyy)."""
    return bool(re.match(r'^10\.\d{4,}/\S+', text.strip()))


def extract_arxiv_id(text):
    """Extract arXiv ID from URL or text."""
    match = re.search(r'(\d{4}\.\d{4,5})', text)
    return match.group(1) if match else None


def resolve_doi(doi):
    """Resolve DOI via CrossRef API. Returns (pdf_url, metadata_dict).
    
    Uses CrossRef /works endpoint to get:
    - Direct PDF URL from link[] with content-type=application/pdf
    - Metadata: title, authors, journal, year, volume, issue, license
    """
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "paper-deep-reader/0.4 (mailto:user@example.com)"
        })
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode("utf-8"))
        work = data.get("message", {})
        
        # Extract PDF URL from links
        pdf_url = None
        for link in work.get("link", []):
            ct = link.get("content-type", "")
            url = link.get("URL", "")
            if "pdf" in ct:
                pdf_url = url
                break
            # Also check if URL ends with /pdf (some publishers use 'unspecified' content-type)
            if not pdf_url and url.rstrip("/").endswith("/pdf"):
                pdf_url = url
        
        # Extract metadata
        authors = []
        affiliations = []
        for author in work.get("author", []):
            parts = []
            if "given" in author:
                parts.append(author["given"])
            if "family" in author:
                parts.append(author["family"])
            name = " ".join(parts)
            if name:
                authors.append(name)
            if "affiliation" in author:
                for aff in author["affiliation"]:
                    a = aff.get("name", "")
                    if a:
                        affiliations.append(a)
        
        journal = ""
        ct = work.get("container-title", [])
        if ct:
            journal = ct[0]
        
        year = ""
        if "published" in work and "date-parts" in work["published"]:
            parts = work["published"]["date-parts"][0]
            if parts:
                year = str(parts[0])
        
        title = ""
        t = work.get("title", [])
        if t:
            title = t[0]
        
        license_url = ""
        licenses = work.get("license", [])
        if licenses:
            license_url = licenses[0].get("URL", "")
        
        metadata = {
            "title": title,
            "authors": ", ".join(authors),
            "affiliations": ", ".join(sorted(set(affiliations))) if affiliations else "",
            "journal": journal,
            "volume": work.get("volume", ""),
            "issue": work.get("issue", ""),
            "year": year,
            "doi": doi,
            "license": license_url,
            "source": "crossref"
        }
        
        return pdf_url, metadata
    
    except Exception as e:
        print(f"[CrossRef] Error resolving DOI {doi}: {e}")
        return None, {"error": str(e), "doi": doi, "source": "crossref"}


def get_pdf_url(input_path):
    """Convert input to a PDF URL for MinerU API."""
    if is_url(input_path):
        if input_path.endswith(".pdf"):
            return input_path
        elif is_arxiv_url(input_path):
            arxiv_id = extract_arxiv_id(input_path)
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        else:
            return input_path
    
    # DOI is handled separately in main() via resolve_doi()
    # This fallback should not normally be reached for DOI inputs
    if is_doi(input_path):
        return f"https://doi.org/{input_path}"
    
    return None


def extract_with_mineru_api(pdf_url, token, output_dir, language="en"):
    """Extract paper using MinerU API."""
    API = "https://mineru.net/api/v4"
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
    }
    
    print(f"[MinerU API] Submitting: {pdf_url}")
    body = json.dumps({
        "url": pdf_url,
        "enable_formula": True,
        "enable_table": True,
        "language": language,
    }).encode()
    
    try:
        req = urllib.request.Request(API + "/extract/task", headers=headers, data=body, method="POST")
        result = json.loads(urllib.request.urlopen(req, timeout=60).read())
        
        if result.get("code") != 0:
            print(f"[MinerU API] Error: {result.get('msg')}")
            return None
        
        task_id = result["data"]["task_id"]
        print(f"[MinerU API] Task ID: {task_id}")
        
        # Poll for result
        for i in range(60):
            time.sleep(5)
            req = urllib.request.Request(API + f"/extract/task/{task_id}", headers=headers)
            status = json.loads(urllib.request.urlopen(req, timeout=30).read())
            state = status.get("data", {}).get("state", "unknown")
            
            if state == "done":
                zip_url = status["data"]["full_zip_url"]
                print(f"[MinerU API] Extraction complete, downloading...")
                
                # Download zip using curl (more reliable than urllib for SSL)
                zip_path = os.path.join(output_dir, "mineru_result.zip")
                import subprocess
                result = subprocess.run(
                    ["curl", "-L", "-o", zip_path, zip_url, "--progress-bar", "--ssl-no-revoke"],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    print(f"[MinerU API] Download failed: {result.stderr}")
                    return None
                
                # Extract
                with zipfile.ZipFile(zip_path) as z:
                    z.extractall(output_dir)
                
                # Rename full.md to paper.md for consistency
                full_md = os.path.join(output_dir, "full.md")
                paper_md = os.path.join(output_dir, "paper.md")
                if os.path.exists(full_md):
                    if os.path.exists(paper_md):
                        os.remove(paper_md)  # Remove existing file before rename
                    os.rename(full_md, paper_md)
                
                # Clean up zip
                os.remove(zip_path)
                
                print(f"[MinerU API] Extracted to: {output_dir}")
                return output_dir
            
            elif state == "failed":
                print(f"[MinerU API] Failed: {status.get('data', {}).get('err_msg', 'unknown')}")
                return None
            
            if i % 5 == 0:
                print(f"[MinerU API] Waiting... ({i*5}s)")
    
    except Exception as e:
        print(f"[MinerU API] Error: {e}")
        return None


def extract_with_mineru_local(pdf_path, output_dir, language="en"):
    """Extract paper using MinerU local client (mineru CLI)."""
    import subprocess
    
    print(f"[MinerU Local] Extracting: {pdf_path}")
    
    # Check if mineru is available
    try:
        result = subprocess.run(["mineru", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("[MinerU Local] mineru command not available")
            return None
        print(f"[MinerU Local] Version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("[MinerU Local] mineru not found in PATH")
        return None
    
    # Run mineru extraction
    try:
        cmd = [
            "mineru",
            "-p", pdf_path,
            "-o", output_dir,
            "-m", "auto",
            "-b", "pipeline",  # pipeline is faster on CPU than hybrid-engine
            "--effort", "medium",  # medium is sufficient for most papers
        ]
        if language == "zh":
            cmd.extend(["-l", "ch"])
        
        print(f"[MinerU Local] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            print(f"[MinerU Local] Error: {result.stderr[:500]}")
            return None
        
        # MinerU outputs to output_dir/<filename>/auto/<filename>.md
        # Find the generated markdown file
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                if f.endswith(".md") and f != "paper.md":
                    src = os.path.join(root, f)
                    dst = os.path.join(output_dir, "paper.md")
                    if src != dst:
                        os.rename(src, dst)
                    print(f"[MinerU Local] Extracted: {dst}")
                    return output_dir
        
        # Check if paper.md already exists
        if os.path.exists(os.path.join(output_dir, "paper.md")):
            print(f"[MinerU Local] Extracted to: {output_dir}")
            return output_dir
        
        print("[MinerU Local] No output file found")
        return None
        
    except subprocess.TimeoutExpired:
        print("[MinerU Local] Extraction timed out (600s)")
        return None
    except Exception as e:
        print(f"[MinerU Local] Error: {e}")
        return None



def extract_with_pymupdf(pdf_path, output_dir):
    """Extract paper using PyMuPDF (fallback)."""
    try:
        import pymupdf
    except ImportError:
        print("[PyMuPDF] Not installed. Install with: pip install pymupdf")
        return None
    
    print(f"[PyMuPDF] Extracting: {pdf_path}")
    
    doc = pymupdf.open(pdf_path)
    
    # Extract metadata
    meta = doc.metadata
    metadata = {
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "subject": meta.get("subject", ""),
        "keywords": meta.get("keywords", ""),
        "source": "pymupdf"
    }
    
    # Extract text
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    
    # Save as markdown
    paper_md = os.path.join(output_dir, "paper.md")
    with open(paper_md, "w", encoding="utf-8") as f:
        f.write(f"# {metadata.get('title', 'Unknown')}\n\n")
        f.write(full_text)
    
    # Extract images
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    img_count = 0
    for page_num, page in enumerate(doc):
        for img_idx, img in enumerate(page.get_images(full=True)):
            try:
                base = doc.extract_image(img[0])
                img_path = os.path.join(images_dir, f"page{page_num+1}_img{img_idx+1}.{base['ext']}")
                with open(img_path, "wb") as f:
                    f.write(base["image"])
                img_count += 1
            except:
                pass
    
    doc.close()
    
    # Save metadata
    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"[PyMuPDF] Extracted: {len(full_text)} chars, {img_count} images")
    return output_dir



def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract paper content")
    parser.add_argument("input", help="PDF path, arXiv URL, DOI, or PDF URL")
    parser.add_argument("output_dir", nargs="?", default=".", help="Output directory (default: current directory)")
    parser.add_argument("--token", help="MinerU API token file")
    parser.add_argument("--language", default="en", help="Language (en/zh)")
    parser.add_argument("--method", choices=["auto", "mineru", "local_to_api", "pymupdf"], default="auto",
                       help="Extraction method")
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Read token
    token = read_token(args.token)
    
    # Detect input type and resolve DOI if needed
    doi_metadata = None
    if is_doi(args.input):
        doi = args.input.strip().rstrip('.')
        print(f"[DOI] Detected DOI: {doi}")
        print(f"[DOI] Resolving via CrossRef API...")
        pdf_url, doi_metadata = resolve_doi(doi)
        
        if pdf_url:
            print(f"[DOI] Found PDF URL: {pdf_url}")
        else:
            print(f"[DOI] No direct PDF URL found from CrossRef")
            # Try Unpaywall as fallback for open-access PDF
            try:
                unpaywall_url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='')}?email=test@example.com"
                req = urllib.request.Request(unpaywall_url, headers={"User-Agent": "paper-deep-reader/0.4"})
                resp = urllib.request.urlopen(req, timeout=15)
                unpaywall = json.loads(resp.read().decode("utf-8"))
                oa_url = unpaywall.get("best_oa_location", {})
                if oa_url:
                    pdf_url = oa_url.get("url_for_pdf") or oa_url.get("url")
                    if pdf_url:
                        print(f"[DOI] Found via Unpaywall: {pdf_url}")
            except Exception as e:
                print(f"[DOI] Unpaywall lookup failed: {e}")
            
            # Try Semantic Scholar for PMC/openAccess PDF
            if not pdf_url:
                try:
                    ss_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi, safe='')}?fields=openAccessPdf,externalIds"
                    req = urllib.request.Request(ss_url, headers={"User-Agent": "paper-deep-reader/1.3"})
                    resp = urllib.request.urlopen(req, timeout=15)
                    ss = json.loads(resp.read().decode("utf-8"))
                    oa = ss.get("openAccessPdf", {})
                    if oa and oa.get("url"):
                        pdf_url = oa["url"]
                        print(f"[DOI] Found via Semantic Scholar OA: {pdf_url}")
                    
                    # Try PMC if PMCID available
                    if not pdf_url:
                        ext_ids = ss.get("externalIds", {})
                        pmcid = ext_ids.get("PubMedCentral", "")
                        if pmcid:
                            pdf_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid}&rettype=pdf"
                            print(f"[DOI] Found via PMC: PMCID={pmcid}")
                except Exception as e:
                    print(f"[DOI] Semantic Scholar lookup failed: {e}")
            
            # Try MDPI direct pattern (for MDPI DOIs: 10.3390/...)
            if not pdf_url and doi.startswith("10.3390/"):
                try:
                    # MDPI pattern: https://mdpi-res.com/d_attachment/<journal>/<article>/article_deploy/<article>.pdf
                    article_id = doi.split("/")[-1]  # e.g., "s25113349"
                    journal_code = article_id.rstrip("0123456789")  # e.g., "s"
                    volume_issue = article_id[len(journal_code):]  # e.g., "25113349"
                    mdpi_url = f"https://mdpi-res.com/d_attachment/sensors/{article_id}/article_deploy/{article_id}.pdf"
                    req = urllib.request.Request(mdpi_url, headers={"User-Agent": "Mozilla/5.0"})
                    resp = urllib.request.urlopen(req, timeout=15, method="HEAD")
                    if resp.status == 200:
                        pdf_url = mdpi_url
                        print(f"[DOI] Found via MDPI direct: {pdf_url}")
                except Exception as e:
                    print(f"[DOI] MDPI direct lookup failed: {e}")
        
        # Save metadata from CrossRef regardless
        if doi_metadata and "error" not in doi_metadata:
            meta_path = os.path.join(args.output_dir, "metadata.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(doi_metadata, f, ensure_ascii=False, indent=2)
            print(f"[DOI] Metadata saved: {doi_metadata.get('title', 'N/A')[:60]}")
    
    # Determine extraction method
    if args.method == "auto":
        if is_doi(args.input):
            # DOI: use mineru API if we found a PDF URL
            if pdf_url and token:
                args.method = "mineru"
            else:
                print("[ERROR] DOI resolved but no PDF URL found and no MinerU token.")
                print("        Download the PDF manually and provide the local path.")
                if doi_metadata and "error" not in doi_metadata:
                    print(f"        Title: {doi_metadata.get('title', 'N/A')}")
                sys.exit(1)
        elif is_url(args.input) and token:
            args.method = "mineru"
        elif os.path.exists(args.input):
            # Local PDF: extract DOI from metadata → resolve URL → MinerU API
            args.method = "local_to_api"
        else:
            args.method = "pymupdf"
    
    # Extract
    if args.method == "mineru":
        if not token:
            print("[ERROR] MinerU API token not found. Use --token or set up token file.")
            sys.exit(1)
        
        if not is_doi(args.input):
            pdf_url = get_pdf_url(args.input)
        
        if not pdf_url:
            print(f"[ERROR] Cannot convert input to URL: {args.input}")
            sys.exit(1)
        
        result = extract_with_mineru_api(pdf_url, token, args.output_dir, args.language)
        if not result:
            print("[MinerU API] Failed, falling back to PyMuPDF...")
            if os.path.exists(args.input):
                result = extract_with_pymupdf(args.input, args.output_dir)
    
    elif args.method == "local_to_api":
        # Local PDF: upload directly to MinerU Cloud + extract DOI metadata
        if not os.path.exists(args.input):
            print(f"[ERROR] File not found: {args.input}")
            sys.exit(1)

        result = None

        # Step 1: Try MinerU Cloud direct upload (new flow)
        if token:
            print("[Local→Cloud] Uploading PDF to MinerU Cloud...")
            import subprocess as _sp
            script_dir = os.path.dirname(os.path.abspath(__file__))
            mineru_script = os.path.join(script_dir, "mineru_api.py")
            try:
                _r = _sp.run(
                    ["python", mineru_script, args.input, args.output_dir,
                     "--token", token, "--language", args.language, "--max-wait", "300"],
                    capture_output=True, text=True, timeout=360
                )
                if _r.returncode == 0:
                    print("[Local→Cloud] MinerU Cloud extraction succeeded")
                    result = args.output_dir
                else:
                    print(f"[Local→Cloud] MinerU Cloud failed (rc={_r.returncode})")
                    print(f"  {_r.stderr[:200] if _r.stderr else _r.stdout[-200:]}")
            except Exception as e:
                print(f"[Local→Cloud] Error: {e}")

        # Step 2: Extract DOI metadata (always, for metadata enrichment)
        doi = None
        doi_metadata = {}

        # Try PyMuPDF for DOI extraction (lightweight, no full extraction)
        try:
            import pymupdf
            doc = pymupdf.open(args.input)
            meta = doc.metadata or {}
            doc.close()
            # Check for DOI in metadata
            doi = meta.get("doi", "")
            if not doi:
                subject = meta.get("subject", "")
                doi_match = re.search(r'(10\.\d{4,}/\S+)', subject)
                if doi_match:
                    doi = doi_match.group(1).rstrip('.,;')
        except Exception:
            pass

        # Also check existing paper.md from MinerU extraction
        if not doi:
            paper_md = os.path.join(args.output_dir, "paper.md")
            if os.path.exists(paper_md):
                with open(paper_md, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()[:5000]
                doi_match = re.search(r'(10\.\d{4,}/[^\s\)\]&,]+)', text)
                if doi_match:
                    doi = doi_match.group(1).rstrip('.,;')

        if doi:
            print(f"[Local→API] Found DOI: {doi}")
            try:
                _, doi_metadata = resolve_doi(doi)
                if doi_metadata and "error" not in doi_metadata:
                    meta_path = os.path.join(args.output_dir, "metadata.json")
                    # Merge with existing metadata if MinerU extraction succeeded
                    existing = {}
                    if os.path.exists(meta_path):
                        with open(meta_path, "r") as f:
                            existing = json.load(f)
                    existing.update({k: v for k, v in doi_metadata.items() if v})
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(existing, f, ensure_ascii=False, indent=2)
                    print(f"[Local→API] Metadata enriched from CrossRef: {doi_metadata.get('title', 'N/A')[:60]}")
            except Exception as e:
                print(f"[Local→API] CrossRef metadata lookup failed: {e}")

        # Step 3: Fallback to PyMuPDF if MinerU Cloud failed
        if not result:
            print("[Local→API] Falling back to PyMuPDF extraction...")
            result = extract_with_pymupdf(args.input, args.output_dir)
    
    elif args.method == "pymupdf":
        if not os.path.exists(args.input):
            print(f"[ERROR] File not found: {args.input}")
            sys.exit(1)
        result = extract_with_pymupdf(args.input, args.output_dir)
    
    if result:
        print(f"\n=== Extraction Complete ===")
        print(f"Output: {result}")
        print(f"Files:")
        for f in os.listdir(result):
            fpath = os.path.join(result, f)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                print(f"  {f} ({size:,} bytes)")
            elif os.path.isdir(fpath):
                count = len(os.listdir(fpath))
                print(f"  {f}/ ({count} files)")
    else:
        print("[ERROR] Extraction failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
