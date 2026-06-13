#!/usr/bin/env python3
"""
generate_html.py — Convert deep-read Markdown note to a beautiful HTML page.
Features: KaTeX math rendering, Mermaid diagrams, responsive design, TOC.

Usage: python generate_html.py <input.md> <output.html> [--title TITLE] [--theme light|dark]
"""

import os
import re
import argparse


# ─── HTML Template ───────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>

<!-- KaTeX for math rendering -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body, {{
    delimiters: [
      {{left: '$$', right: '$$', display: true}},
      {{left: '$', right: '$', display: false}},
      {{left: '\\(', right: '\\)', display: false}},
      {{left: '\\[', right: '\\]', display: true}}
    ],
    throwOnError: false
  }});"></script>

<!-- Mermaid for diagrams -->
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>

<style>
:root {{
  --bg: {bg_color};
  --fg: {fg_color};
  --accent: {accent_color};
  --accent-light: {accent_light};
  --border: {border_color};
  --code-bg: {code_bg};
  --quote-bg: {quote_bg};
  --card-bg: {card_bg};
  --shadow: {shadow_color};
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.8;
  font-size: 16px;
}}

.container {{
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}}

/* ─── Typography ─── */
h1 {{ font-size: 1.8rem; margin: 2rem 0 1rem; color: var(--accent); border-bottom: 2px solid var(--accent); padding-bottom: 0.5rem; }}
h2 {{ font-size: 1.4rem; margin: 1.8rem 0 0.8rem; color: var(--accent); }}
h3 {{ font-size: 1.15rem; margin: 1.2rem 0 0.5rem; }}
h4 {{ font-size: 1.05rem; margin: 1rem 0 0.4rem; }}

p {{ margin: 0.6rem 0; }}

a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* ─── Table of Contents ─── */
.toc {{
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.2rem 1.5rem;
  margin: 1.5rem 0;
}}
.toc summary {{
  font-weight: 600;
  font-size: 1.1rem;
  color: var(--accent);
  cursor: pointer;
}}
.toc ul {{ list-style: none; padding-left: 1.2rem; margin-top: 0.5rem; }}
.toc li {{ margin: 0.3rem 0; }}
.toc a {{ font-size: 0.95rem; }}

/* ─── Blockquote (original quotes) ─── */
blockquote {{
  background: var(--quote-bg);
  border-left: 4px solid var(--accent);
  padding: 0.8rem 1.2rem;
  margin: 1rem 0;
  border-radius: 0 6px 6px 0;
  font-style: italic;
  font-size: 0.95rem;
}}
blockquote p {{ margin: 0.3rem 0; }}

/* ─── Code blocks ─── */
pre {{
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem;
  overflow-x: auto;
  margin: 1rem 0;
  font-size: 0.9rem;
}}
code {{
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 0.9em;
}}
p code, li code {{
  background: var(--code-bg);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-size: 0.88em;
}}

/* ─── Tables ─── */
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.95rem;
}}
th {{
  background: var(--accent);
  color: white;
  padding: 0.6rem 0.8rem;
  text-align: left;
  font-weight: 600;
}}
td {{
  padding: 0.5rem 0.8rem;
  border-bottom: 1px solid var(--border);
}}
tr:nth-child(even) {{ background: var(--card-bg); }}
tr:hover {{ background: var(--accent-light); }}

/* ─── Images ─── */
img {{
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 0.5rem 0;
  box-shadow: 0 2px 8px var(--shadow);
}}
figure {{
  text-align: center;
  margin: 1.5rem 0;
}}
figcaption {{
  font-size: 0.9rem;
  color: #666;
  margin-top: 0.4rem;
  font-style: italic;
}}

/* ─── Collapsible sections ─── */
details {{
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 1rem 0;
  padding: 0.5rem 1rem;
  background: var(--card-bg);
}}
details summary {{
  font-weight: 600;
  cursor: pointer;
  padding: 0.5rem 0;
  color: var(--accent);
}}
details[open] summary {{
  margin-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.5rem;
}}

/* ─── Emoji headers styling ─── */
h2 {{ display: flex; align-items: center; gap: 0.4rem; }}

/* ─── Print ─── */
@media print {{
  .container {{ max-width: 100%; padding: 0; }}
  details {{ border: none; }}
  details[open] {{ display: block; }}
  .no-print {{ display: none; }}
}}

/* ─── Scroll to top ─── */
.scroll-top {{
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 50%;
  width: 44px;
  height: 44px;
  font-size: 1.3rem;
  cursor: pointer;
  box-shadow: 0 2px 8px var(--shadow);
  display: none;
  z-index: 100;
}}
.scroll-top:hover {{ opacity: 0.85; }}
</style>
</head>
<body>

<div class="container">
{content}
</div>

<button class="scroll-top no-print" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" id="scrollTop">↑</button>

<script>
// Mermaid init
mermaid.initialize({{ startOnLoad: true, theme: '{mermaid_theme}' }});

// Scroll to top button
window.addEventListener('scroll', () => {{
  const btn = document.getElementById('scrollTop');
  btn.style.display = window.scrollY > 400 ? 'block' : 'none';
}});
</script>

</body>
</html>"""


# ─── Theme definitions ──────────────────────────────────────────────────────

THEMES = {
    "light": {
        "bg_color": "#fafafa",
        "fg_color": "#1a1a2e",
        "accent_color": "#2563eb",
        "accent_light": "#eff6ff",
        "border_color": "#e2e8f0",
        "code_bg": "#f1f5f9",
        "quote_bg": "#f8fafc",
        "card_bg": "#ffffff",
        "shadow_color": "rgba(0,0,0,0.08)",
        "mermaid_theme": "default",
    },
    "dark": {
        "bg_color": "#0f172a",
        "fg_color": "#e2e8f0",
        "accent_color": "#60a5fa",
        "accent_light": "#1e293b",
        "border_color": "#334155",
        "code_bg": "#1e293b",
        "quote_bg": "#1e293b",
        "card_bg": "#1e293b",
        "shadow_color": "rgba(0,0,0,0.3)",
        "mermaid_theme": "dark",
    },
}


# ─── Markdown → HTML converter ──────────────────────────────────────────────

def md_to_html(md_text: str) -> str:
    """Convert Markdown to HTML. Handles headings, tables, blockquotes, code,
    lists, images, bold/italic, links, horizontal rules.
    Mermaid code blocks are converted to <div class="mermaid">.
    """
    lines = md_text.split("\n")
    html_parts = []
    in_code_block = False
    code_lang = ""
    code_lines = []
    in_table = False
    table_rows = []
    in_list = False
    list_type = None  # 'ul' or 'ol'
    list_items = []

    def flush_list():
        nonlocal in_list, list_items, list_type
        if in_list and list_items:
            tag = list_type or "ul"
            html_parts.append(f"<{tag}>")
            for item in list_items:
                html_parts.append(f"<li>{inline_format(item)}</li>")
            html_parts.append(f"</{tag}>")
            list_items = []
            in_list = False
            list_type = None

    def flush_table():
        nonlocal in_table, table_rows
        if not in_table or not table_rows:
            return
        html_parts.append('<table>')
        for i, row in enumerate(table_rows):
            cells = [c.strip() for c in row.strip('|').split('|')]
            if i == 0:
                html_parts.append('<thead><tr>')
                for c in cells:
                    html_parts.append(f'<th>{inline_format(c)}</th>')
                html_parts.append('</tr></thead><tbody>')
            elif not all(set(c.strip()) <= set('-| ') for c in cells):
                html_parts.append('<tr>')
                for c in cells:
                    html_parts.append(f'<td>{inline_format(c)}</td>')
                html_parts.append('</tr>')
        html_parts.append('</tbody></table>')
        table_rows = []
        in_table = False

    def inline_format(text: str) -> str:
        """Apply inline formatting: bold, italic, code, links, images, math."""
        # Protect inline code
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        # Images: ![alt](src)
        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<figure><img src="\2" alt="\1"><figcaption>\1</figcaption></figure>', text)
        # Links: [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        # Italic: *text* or _text_
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', text)
        # Strikethrough: ~~text~~
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
        return text

    for line in lines:
        # Code block
        if line.strip().startswith("```"):
            if in_code_block:
                code_content = "\n".join(code_lines)
                if code_lang == "mermaid":
                    html_parts.append(f'<div class="mermaid">{code_content}</div>')
                else:
                    html_parts.append(f'<pre><code class="language-{code_lang}">{code_content}</code></pre>')
                code_lines = []
                in_code_block = False
                code_lang = ""
            else:
                flush_list()
                flush_table()
                in_code_block = True
                code_lang = line.strip()[3:].strip()
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        stripped = line.strip()

        # Empty line
        if not stripped:
            flush_list()
            flush_table()
            continue

        # Table row
        if '|' in stripped and stripped.startswith('|'):
            flush_list()
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(stripped)
            continue
        else:
            flush_table()

        # Horizontal rule
        if re.match(r'^[-*_]{3,}\s*$', stripped):
            flush_list()
            html_parts.append('<hr>')
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            flush_list()
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            # Generate id for TOC
            anchor = re.sub(r'[^\w\u4e00-\u9fff-]', '', text.replace(' ', '-').lower())[:60]
            html_parts.append(f'<h{level} id="{anchor}">{inline_format(text)}</h{level}>')
            continue

        # Blockquote
        if stripped.startswith('>'):
            flush_list()
            quote_text = stripped[1:].strip()
            html_parts.append(f'<blockquote><p>{inline_format(quote_text)}</p></blockquote>')
            continue

        # Unordered list
        list_match = re.match(r'^[-*+]\s+(.+)$', stripped)
        if list_match:
            if not in_list or list_type != 'ul':
                flush_list()
                in_list = True
                list_type = 'ul'
            list_items.append(list_match.group(1))
            continue

        # Ordered list
        ol_match = re.match(r'^\d+\.\s+(.+)$', stripped)
        if ol_match:
            if not in_list or list_type != 'ol':
                flush_list()
                in_list = True
                list_type = 'ol'
            list_items.append(ol_match.group(1))
            continue

        # Regular paragraph
        flush_list()
        html_parts.append(f'<p>{inline_format(stripped)}</p>')

    flush_list()
    flush_table()

    return "\n".join(html_parts)


# ─── Generate TOC ────────────────────────────────────────────────────────────

def generate_toc(md_text: str) -> str:
    """Generate a table of contents from Markdown headings."""
    toc_items = []
    for line in md_text.split("\n"):
        match = re.match(r'^(#{2,4})\s+(.+)$', line.strip())
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            anchor = re.sub(r'[^\w\u4e00-\u9fff-]', '', text.replace(' ', '-').lower())[:60]
            indent = "  " * (level - 2)
            toc_items.append(f'{indent}<li><a href="#{anchor}">{text}</a></li>')
    
    if not toc_items:
        return ""
    
    return f"""<details class="toc" open>
<summary>📑 目录 / Table of Contents</summary>
<ul>
{"".join(toc_items)}
</ul>
</details>"""


# ─── Image embedding ─────────────────────────────────────────────────────────

def embed_images_as_base64(html_content: str, images_dir: str) -> str:
    """Replace image src references with base64 data URIs."""
    if not images_dir or not os.path.isdir(images_dir):
        return html_content

    import base64
    import mimetypes

    def replace_img_src(match):
        src = match.group(1)
        # Try to find the image file
        img_path = os.path.join(images_dir, os.path.basename(src))
        if not os.path.exists(img_path):
            # Try the src as-is
            img_path = os.path.join(images_dir, src)
        if not os.path.exists(img_path):
            return match.group(0)  # Keep original if not found

        # Get MIME type
        mime, _ = mimetypes.guess_type(img_path)
        if not mime:
            mime = "image/png"

        # Encode as base64
        with open(img_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")

        return f'src="data:{mime};base64,{data}"'

    # Replace src="images/..." or src="path/to/img"
    html_content = re.sub(r'src="([^"]+\.(?:png|jpg|jpeg|gif|svg|webp))"', replace_img_src, html_content, flags=re.IGNORECASE)
    return html_content


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Convert deep-read Markdown to HTML")
    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument("output", nargs="?", default=None, help="Output HTML file (default: <input>.html)")
    parser.add_argument("--title", help="Page title (default: from first heading)")
    parser.add_argument("--theme", choices=["light", "dark"], default="light", help="Color theme")
    parser.add_argument("--images-dir", "-img", default=None, help="Directory containing paper images (for embedding)")
    parser.add_argument("--pdf", action="store_true", help="Also generate PDF from HTML")
    parser.add_argument("--standalone", action="store_true", default=True, help="Standalone HTML (default)")
    args = parser.parse_args()

    # Default output: <input_basename>.html in current directory
    if not args.output:
        base = os.path.splitext(os.path.basename(args.input))[0]
        args.output = base + ".html"

    # Read input
    with open(args.input, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Extract title
    title = args.title
    if not title:
        # Try first heading
        match = re.match(r'^#\s+(.+)$', md_text, re.MULTILINE)
        if match:
            title = match.group(1).strip()
        else:
            title = os.path.splitext(os.path.basename(args.input))[0]

    # Generate TOC
    toc = generate_toc(md_text)

    # Convert MD → HTML
    body_html = md_to_html(md_text)

    # Combine: TOC + content
    content = f"{toc}\n{body_html}"

    # Apply template
    theme = THEMES[args.theme]
    html = HTML_TEMPLATE.format(
        title=title,
        content=content,
        **theme,
    )

    # Embed images as base64 if images-dir provided
    if args.images_dir:
        html = embed_images_as_base64(html, args.images_dir)
        print(f"Images embedded from: {args.images_dir}")

    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"=== HTML Generated ===")
    print(f"Output: {args.output} ({size_kb:.1f} KB)")
    print(f"Theme: {args.theme}")
    print(f"Title: {title}")

    # Generate PDF if requested
    if args.pdf:
        try:
            from weasyprint import HTML as WeasyprintHTML
            pdf_path = os.path.splitext(args.output)[0] + ".pdf"
            WeasyprintHTML(filename=args.output).write_pdf(pdf_path)
            pdf_kb = os.path.getsize(pdf_path) / 1024
            print(f"PDF: {pdf_path} ({pdf_kb:.1f} KB)")
        except ImportError:
            print("[WARNING] weasyprint not installed. Run: pip install weasyprint")
        except Exception as e:
            print(f"[WARNING] PDF generation failed: {e}")


if __name__ == "__main__":
    main()
