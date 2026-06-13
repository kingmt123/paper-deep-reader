# Metadata Verification Workflow

## Problem

LLMs hallucinate metadata — fabricating author affiliations, paraphrasing abstracts, inventing missing fields.

## Verified Sources (Priority Order)

1. **CrossRef API** (most reliable for published papers)
   ```
   curl -s "https://api.crossref.org/works/{DOI}" -H "User-Agent: paper-deep-reader/1.0"
   ```
   Returns: title, authors with affiliations, journal, volume, issue, pages, year, DOI, license, PDF links.

2. **arXiv API** (for preprints)
   ```
   http://export.arxiv.org/api/query?id_list={arXiv_ID}
   ```
   Returns: title, authors, abstract, categories, journal_ref, DOI.

3. **Semantic Scholar API** (citations)
   ```
   https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}?fields=citationCount,title,year
   ```

4. **PDF metadata** (PyMuPDF) — fallback, often incomplete.

5. **web_search** — supplementary verification for affiliations, impact factor.

## Rules

- CrossRef/arXiv API data = **verified**
- PDF-extracted data = **semi-verified**, mark as "（PDF提取）"
- Missing fields = **"未提供"**, never "(other)" or "N/A"
- Abstract: use actual API text, never paraphrase
- Affiliations: use CrossRef `author[].affiliation[].name`

## CrossRef Response Structure

```json
{
  "message": {
    "title": ["Paper Title"],
    "author": [
      {
        "given": "Yun-Peng",
        "family": "Su",
        "affiliation": [{"name": "University of Canterbury, NZ"}]
      }
    ],
    "container-title": ["Applied Sciences"],
    "volume": "11",
    "issue": "23",
    "page": "11280",
    "published": {"date-parts": [[2021, 12, 1]]},
    "DOI": "10.3390/app112311280",
    "link": [{"content-type": "application/pdf", "URL": "https://..."}],
    "license": [{"URL": "https://creativecommons.org/licenses/by/4.0"}]
  }
}
```

## Unpaywall Fallback

When CrossRef has no PDF link:
```
https://api.unpaywall.org/v2/{DOI}?email=test@example.com
```
Returns `best_oa_location.url_for_pdf` for open-access papers.
