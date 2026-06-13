# PDF Output — Chrome Headless Print-to-PDF

## Problem

Multiple HTML→PDF approaches were tested. Only Chrome headless works reliably on Windows.

## Tested Approaches

| Approach | Result | Issue |
|----------|--------|-------|
| **Chrome headless** | ✅ Works | Requires Chrome/Edge installed |
| weasyprint | ❌ Fails | Needs GTK libraries (`libgobject-2.0-0`), not on Windows |
| xhtml2pdf | ❌ Fails | Can't handle CSS variables (`var(--border)`) |
| pymupdf.open(html) | ❌ Fails | Can't convert HTML to PDF directly |
| reportlab | ❌ N/A | For programmatic PDF creation, not HTML conversion |

## Working Command

```bash
# Chrome (Windows)
"C:/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless --disable-gpu \
  --print-to-pdf="output.pdf" \
  --no-margins \
  "file:///C:/path/to/output.html"

# Edge (Windows, fallback)
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --headless --disable-gpu \
  --print-to-pdf="output.pdf" \
  --no-margins \
  "file:///C:/path/to/output.html"
```

## Integration in generate_html.py

```bash
python scripts/generate_html.py note.md output.html --theme light --images-dir images/ --pdf
```

The `--pdf` flag triggers Chrome headless after HTML generation.

## File Sizes (with embedded images)

- HTML with base64 images: ~800 KB for 5 images
- PDF via Chrome headless: ~1.9 MB for 5 images
- Both contain all images inline (no external dependencies)

## Pitfalls

1. **File lock**: If the PDF is open in a viewer, Chrome can't write to it. Use a different filename or close the viewer.
2. **--headless vs --headless=new**: Use `--headless=new` for newer Chrome versions if `--headless` doesn't work.
3. **CDN scripts**: KaTeX and Mermaid CDN scripts load fine in Chrome headless (has network access). xhtml2pdf can't handle them.
4. **Chinese text**: Chrome handles CJK text natively. No font issues on Windows.
