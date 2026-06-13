# Composite Figure Handling

## Note (v3.0.0)
`images_hq/` directory is no longer generated. All images come from MinerU Cloud's `images/` directory. PyMuPDF HQ image extraction was removed in v3.0.0.

The detection and rendering techniques below still apply but should target `images/` instead of `images_hq/`.

## Problem

Both MinerU and PyMuPDF split composite/multi-panel figures into fragments:

1. **MinerU layout detection** treats each visible sub-image as a separate `type=image` block. A Figure 7 with sub-figures (a)(b)(c) arranged in a grid becomes 24+ individual tiny image files.
2. **PyMuPDF `page.get_images()`** extracts each embedded image object independently — same splitting behavior.
3. **Cross-page figures** get duplicated: the same image extracted from both pages (identical content, identical MD5).

## Detection

Check `layout.json` for clustered image blocks on a single page:

```python
import json
with open('layout.json') as f:
    data = json.load(f)

for i, page in enumerate(data['pdf_info']):
    img_blocks = [b for b in page.get('preproc_blocks', []) if b.get('type') == 'image']
    if len(img_blocks) > 4:
        print(f"Page {i}: {len(img_blocks)} image blocks — likely composite figure")
```

Also check `images_hq/` for duplicate files:
```python
import hashlib, os
seen = {}
for f in os.listdir('images_hq'):
    h = hashlib.md5(open(f'images_hq/{f}','rb').read()).hexdigest()
    if h in seen:
        print(f"DUPLICATE: {f} == {seen[h]}")
    seen[h] = f
```

## Solution: Region-based Rendering

For composite figures, render the full figure region as one pixmap:

```python
import pymupdf, json, os

def render_composite_figures(pdf_path, layout_path, output_dir, caption_keywords=None):
    """Merge split image blocks and render composite figures as single images.
    
    Args:
        caption_keywords: list of strings like ["Figure 7", "Fig. 8"] to match captions.
                         If None, auto-detect by counting clustered image blocks.
    """
    doc = pymupdf.open(pdf_path)
    with open(layout_path) as f:
        layout = json.load(f)
    
    os.makedirs(output_dir, exist_ok=True)
    
    for page_idx, page_info in enumerate(layout['pdf_info']):
        blocks = page_info.get('preproc_blocks', [])
        img_blocks = [b for b in blocks if b.get('type') == 'image']
        
        # Skip pages with few images (not composite)
        if len(img_blocks) < 3:
            continue
        
        # Find nearby caption blocks
        caption_blocks = [b for b in blocks if 'text' in b.get('type', '').lower()]
        
        # Group image blocks by proximity (cluster detection)
        # Simple approach: if >3 image blocks on same page, treat as composite
        all_bboxes = [b.get('bbox', b.get('layout_bbox', [])) for b in img_blocks]
        if not all_bboxes:
            continue
        
        # Compute merged bounding box (with padding)
        x0 = min(b[0] for b in all_bboxes) - 10
        y0 = min(b[1] for b in all_bboxes) - 10
        x1 = max(b[2] for b in all_bboxes) + 10
        y1 = max(b[3] for b in all_bboxes) + 10
        
        # Include caption text below if present
        for cb in caption_blocks:
            cbbox = cb.get('bbox', cb.get('layout_bbox', []))
            if cbbox and abs(cbbox[0] - x0) < 50 and cbbox[1] > y1 - 20:
                y1 = max(y1, cbbox[3] + 5)
        
        # Render the merged region
        page = doc[page_idx]
        clip = pymupdf.Rect(x0, y0, x1, y1)
        pix = page.get_pixmap(clip=clip, dpi=200)
        
        out_path = os.path.join(output_dir, f"page{page_idx+1}_composite.png")
        pix.save(out_path)
        print(f"Rendered composite figure: {out_path} ({x1-x0:.0f}x{y1-y0:.0f})")
    
    doc.close()
```

## Integration Points

- Run after `extract_paper.py` and before `figure_mapper.py`
- Output goes to `images_hq/` with `pageN_composite.png` naming
- `figure_mapper.py` should prefer composite renders over split fragments for figures with many sub-images
- For PPT `content.json`, use composite renders for multi-panel figures

## Limitations

- Grid detection is heuristic (count >3 blocks on same page)
- Very complex layouts may need manual bbox adjustment
- DPI 200 balances quality vs file size; increase to 300 for print-quality PPT
