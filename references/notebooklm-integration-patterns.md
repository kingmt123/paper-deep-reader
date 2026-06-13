# NotebookLM Integration Patterns (v1.5.0)

## Available Commands
- `notebooklm list --json` — list existing notebooks
- `notebooklm source add <file> --notebook <id> --json` — add source
- `notebooklm source wait <id> --timeout N` — wait for processing
- `notebooklm ask "question" --notebook <id> --json` — ask with citations
- `notebooklm generate audio/video/quiz` — generate content

## NOT Available
- `notebooklm generate mindmap` — does NOT exist (tested 2026-06-12)

## Reliability Issues
- `notebooklm create` via Python subprocess is unreliable (works from CLI, fails in subprocess)
- Root cause: unknown — possibly PATH, environment, or timing differences
- **Solution**: Use existing notebooks only (via `notebooklm list`), don't create new ones in scripts
- If no notebook exists, output guidance for manual setup

## Unicode Filename Issues
- Filenames with Unicode dashes (U+2011 NON-BREAKING HYPHEN vs U+002D HYPHEN) cause `notebooklm create` to fail silently
- Fix: sanitize with `unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")`
- Example: "Virtual‑Augmented" → "Virtual-Augmented" (U+2011 → U+002D)

## Recommended Usage Pattern
```bash
# Check existing notebooks
notebooklm list --json

# Use an existing notebook
notebooklm source add paper.pdf --notebook <existing_id> --json
notebooklm source wait <source_id> --timeout 180

# Ask about figures
notebooklm ask "Describe Figure 1 in detail" --notebook <id> --json

# Generate audio overview
notebooklm generate audio "focus on methodology" --notebook <id>
```

## When to Use NotebookLM vs figure_mapper.py
- **figure_mapper.py**: Fast, deterministic, works offline, uses layout.json + paper.md text
- **NotebookLM**: Better for complex figures, can explain visual content, requires auth + network
- **Recommended**: Use figure_mapper.py first, supplement with NotebookLM for unclear cases
