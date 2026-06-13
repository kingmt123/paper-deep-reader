# Extraction Quality Comparison: PyMuPDF vs MinerU API URL vs MinerU Cloud

Test paper: "Coordinating Obstacle Avoidance of a Redundant Dual-Arm Nursing-Care Robot"
DOI: 10.3390/bioengineering11060550 (MDPI, 10MB PDF, 16 pages)

## Results

| Metric | PyMuPDF | MinerU API URL | MinerU Cloud Upload |
|--------|---------|----------------|---------------------|
| Success | ✓ | ✗ (403) | ✓ |
| paper.md size | 63 KB | N/A | 64 KB |
| Images extracted | 1458 | N/A | 65 |
| Image quality | Icons+logos+figures | N/A | Figures only |
| Formula format | Plain text | N/A | LaTeX |
| Layout info | None | N/A | layout.json (1.7MB) |
| Duplicate text | Yes (dual-column) | N/A | No |
| Hash filenames | No (pageN_imgM) | N/A | Yes |
| Processing time | ~5s | N/A | ~15s |
| deep-read.md | 13.5 KB | N/A | 13.4 KB |
| deep-read.html | 25.3 KB | N/A | 25.0 KB |
| slides.pptx (images/) | 3.9 MB | N/A | 304 KB (compressed) |
| slides.pptx (images_hq/) | 3.9 MB | N/A | 971 KB (HQ, recommended) |

## Key Differences

1. **Image count:** PyMuPDF extracts ALL embedded images (1458 for a 16-page paper). MinerU Cloud extracts only meaningful figures (65). The difference is icons, logos, equation fragments, and decorative elements.

2. **Formula quality:** PyMuPDF renders formulas as plain text (lossy). MinerU Cloud converts to LaTeX (preserves structure).

3. **Duplicate content:** PyMuPDF extracts dual-column text twice. MinerU Cloud deduplicates.

4. **Image filenames:** PyMuPDF uses `pageN_imgM.png`. MinerU Cloud uses SHA256 hashes. Figure matching requires different strategies.

5. **PPT image embedding:** With PyMuPDF images (100-1800KB each), PPT → 3.9MB. With MinerU Cloud images (30-64KB each), PPT → 304KB. Both have images embedded; size difference is due to image resolution.

## Recommendation
- **Always prefer MinerU Cloud** when token is available
- **PyMuPDF** as fallback for: no token, offline, MinerU service down
- For MDPI papers: MUST use MinerU Cloud direct upload (URL submission returns 403)
- **PPT images:** Use `images_hq/` (PyMuPDF HQ, `pageN_imgM` naming) not `images/` (MinerU compressed, hash naming). `extract_paper.py` auto-extracts HQ images after MinerU Cloud success.
