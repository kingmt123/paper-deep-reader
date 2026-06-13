# Patent Identification & Summarization Workflow

When a folder contains patent PDFs alongside papers, or the user asks to summarize patents.

## Detecting Patent PDFs

1. **Filename patterns**: Look for "US" + number (e.g., US20250229427A1), "CN" + number, "EP" + number, or "专利"
2. **Scanned PDF check**: PyMuPDF `get_text()` returns empty, each page has exactly 1 image
3. **IPC codes**: B25J (manipulators), B23K (welding), B25J9/16 (program-controlled), etc.

## Patent Number Patterns

| Pattern | Example | Meaning |
|---------|---------|---------|
| US{digits}A1 | US20250229427A1 | US patent application publication |
| US{digits}B2 | US11931907B2 | US granted patent |
| CN{digits}A | CN112345678A | Chinese patent application |
| WO{digits}A1 | WO2024123456A1 | PCT international application |

## Lookup Strategy (in order of reliability)

### 1. Google Patents Browser Lookup (preferred)

```
https://patents.google.com/patent/<NUMBER>/en
```

Returns in the page snapshot:
- Title, abstract, full description
- Inventors, assignee, dates (priority/filed/published/granted)
- IPC classifications, citations
- Status (Pending/Active/Expired)

**Note**: Google Patents is a client-side JS app. The `browser_navigate` snapshot captures all metadata from the initial render. No need to wait for additional loads.

### 2. Google Patents Search (when patent number unknown)

```
https://patents.google.com/?q=<key+title+words>
```

Results page shows: patent number, title, assignee, dates. Click through for full details.

### 3. USPTO Patent Public Search (PPUBS)

```
https://ppubs.uspto.gov/
```

API available at `ppubs.uspto.gov/api/` — search by publication number.

**Note**: The old `api.patentsview.org` has migrated to `data.uspto.gov`. Direct API queries may redirect. Prefer Google Patents.

## Patent Summary Structure

For folder summaries, use this structure per patent:

```
### US{N}. {Chinese title}

| 字段 | 内容 |
|------|------|
| 专利号 | US2025XXXXXXA1 |
| 标题 | English title |
| 申请人 | Assignee (Chinese name if applicable) |
| 发明人 | Inventor list |
| 申请日 | YYYY-MM-DD |
| 公布日 | YYYY-MM-DD |
| 状态 | 申请中/Active |
| IPC分类 | B25J9/16XX |

**核心技术：**
- Bullet points of key technical features

**与本课题的关联：** How it relates to the user's research topic
```

## Pitfalls

1. **Scanned patents have NO text layer.** Do NOT attempt MinerU/PyMuPDF text extraction. Go directly to browser lookup.
2. **Subagent patent search is unreliable.** Subagents may fabricate details. Always verify via browser.
3. **Ambiguous filenames.** "USDistributed training..." → "US" is country code, not patent number. Search by title keywords.
4. **Chinese patents from CNIPA** may not be on Google Patents. Try: `https://pss-system.cponline.cnipa.gov.cn/` or search by Chinese title.
5. **vision_analyze on patent pages** can work but is slow and error-prone for dense text. Browser lookup is faster and more reliable.

## Folder Summary with Mixed Documents

When generating a consolidated summary (`文献总结_<topic>.md`):

1. Classify each PDF as paper or patent
2. Papers: use speed-read template (modules 1/2/5)
3. Patents: use patent summary structure above
4. Generate a comparison table across ALL documents
5. Add "综合启示" section connecting findings to user's research
