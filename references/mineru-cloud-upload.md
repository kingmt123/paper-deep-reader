# MinerU Cloud API — Local PDF Upload Flow

## Problem
MinerU API (`/api/v4/extract/task`) only accepts URLs. For local PDFs, we need the pre-signed upload flow.

## Solution (from github.com/linliu0210/mineru-cloud-api)

### Flow
```
Step 1: POST /api/v4/file-urls/batch
  → Get pre-signed upload URL + batch_id

Step 2: PUT <upload_url> with PDF bytes
  → CRITICAL: No Content-Type header (pre-signed URL signature doesn't include it)
  → Use curl -T (not urllib, SSL fails)

Step 3: GET /api/v4/extract-results/batch/<batch_id>
  → Poll until state == "done"

Step 4: Download full_zip_url → extract
```

### API Details

**Step 1 request:**
```json
POST https://mineru.net/api/v4/file-urls/batch
Headers: Authorization: Bearer <token>, Content-Type: application/json
Body: {
  "files": [{
    "name": "paper.pdf",
    "is_ocr": false,
    "data_id": "doc_001",
    "enable_formula": true,
    "enable_table": true,
    "language": "en"
  }]
}
```

**Step 1 response:**
```json
{
  "code": 0,
  "data": {
    "batch_id": "xxx-xxx",
    "file_urls": ["https://mineru.oss-cn-shanghai.aliyuncs.com/...?Expires=...&Signature=..."]
  }
}
```

**Step 2:** PUT PDF bytes to pre-signed URL
```bash
curl -X PUT -o /dev/null -w "%{http_code}" --max-time 120 --ssl-no-revoke -T paper.pdf "<upload_url>"
# Expected: 200
```

**Step 3:** Poll results
```json
GET https://mineru.net/api/v4/extract-results/batch/<batch_id>
Headers: Authorization: Bearer <token>

Response: {
  "data": {
    "extract_result": [{
      "state": "done",
      "full_zip_url": "https://..."
    }]
  }
}
```

### Windows SSL Fix
Both PUT upload and ZIP download fail with `SSL: UNEXPECTED_EOF_WHILE_READING` or curl exit code 35 without `--ssl-no-revoke`. This flag disables Windows certificate revocation checking which fails against Aliyun's CDN.

### Error Codes
- `-60023`: "this URL is restricted by regional regulations" — URL not accessible from MinerU servers (MDPI 403)
- `code != 0` on file-urls/batch: token invalid or API changed

### Reference
- Source: https://github.com/linliu0210/mineru-cloud-api
- Script: `scripts/mineru_api.py` implements this flow
