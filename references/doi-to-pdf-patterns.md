# DOI → PDF URL Resolution Patterns

> Practical patterns for resolving DOIs to downloadable PDF URLs.

## Resolution Chain (in order)

### 1. CrossRef API

```bash
curl -s "https://api.crossref.org/works/10.xxxx/yyyy" -H "User-Agent: paper-deep-reader/1.3"
```

Check `message.link[]` for:
- `content-type: application/pdf` → direct PDF URL
- `content-type: unspecified` + URL ending in `/pdf` → likely PDF (e.g., MDPI)

### 2. Unpaywall API

```bash
curl -s "https://api.unpaywall.org/v2/10.xxxx/yyyy?email=test@example.com"
```

Check `best_oa_location.url_for_pdf`. May return 422 for some DOIs.

### 3. Semantic Scholar

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/DOI:10.xxxx/yyyy?fields=openAccessPdf,externalIds"
```

Check `openAccessPdf.url` and `externalIds.PubMedCentral`.

### 4. PMC (via PMCID)

```
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={PMCID}&rettype=pdf
```

- Returns 200 with PDF content (content-type: text/xml, but actual PDF)
- MinerU API may reject this as "unsupported file type"
- Works for direct download but not for MinerU API submission

### 5. MDPI Direct Pattern (for 10.3390/... DOIs)

```
https://mdpi-res.com/d_attachment/{journal}/{article_id}/article_deploy/{article_id}.pdf
```

- Journal name from DOI: `10.3390/sensors-25-03349` → journal=`sensors`, id=`s25113349`
- May return 404 for some papers
- mdpi.com main site returns 403 to automated access

## Publisher-Specific Notes

| Publisher | CrossRef PDF? | Direct Access | Notes |
|-----------|--------------|---------------|-------|
| MDPI | URL exists but 403 | mdpi-res.com sometimes works | Use PyMuPDF fallback |
| Nature/Springer | Usually yes | Yes | Works well |
| IEEE | Paywalled | No | Needs institutional access |
| Elsevier | Paywalled | No | Needs institutional access |
| Open Access journals | Usually yes | Yes | Best case |

## Python Code Pattern

```python
# In extract_paper.py local_to_api method:
# 1. PyMuPDF → get DOI from metadata/subject/text
# 2. resolve_doi(doi) → CrossRef (with /pdf URL fallback)
# 3. Unpaywall API
# 4. Semantic Scholar → PMC
# 5. Publisher-specific patterns (MDPI)
# 6. MinerU API with resolved URL
# 7. PyMuPDF fallback if all fail
```
