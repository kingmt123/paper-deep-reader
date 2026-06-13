# GitHub Deployment for paper-deep-reader

## Prerequisites

- `gh` CLI: `winget install --id GitHub.cli -e`
- GitHub account authenticated: `gh auth login`
- SSH key configured for GitHub (check: `ssh -T git@github.com`)

## Upload Workflow

```bash
# 1. Create clean copy (exclude .mineru_token, __pycache__, node_modules)
UPLOAD_DIR="/tmp/paper-deep-reader-upload"
mkdir -p "$UPLOAD_DIR"
rs -av --exclude='.mineru_token' --exclude='__pycache__' --exclude='node_modules' \
  <skill_dir>/ "$UPLOAD_DIR/"

# 2. Create README.md and .gitignore
# .gitignore should include: .mineru_token, __pycache__/, node_modules/

# 3. Init and push
cd "$UPLOAD_DIR"
git init && git add -A && git commit -m "Initial release v3.0.0"
gh repo create paper-deep-reader --public \
  --description "Hermes Agent skill for deep reading academic papers." \
  --source . --remote origin --push
```

## Privacy Checklist

Before uploading, verify these are excluded:
- [ ] `.mineru_token` (API key)
- [ ] `__pycache__/` (compiled Python)
- [ ] `node_modules/` (npm dependencies)
- [ ] No personal paths in scripts (grep for username)
- [ ] No hardcoded API keys or tokens in any file

## Windows Notes

- `gh.exe` installed via winget: `C:\Program Files\GitHub CLI\gh.exe`
- If `gh` not in PATH, use full path: `"/c/Program Files/GitHub CLI/gh.exe"`
- SSH auth works if `ssh -T git@github.com` returns "Hi username!"
- Git CRLF warnings are normal on Windows, can be ignored
