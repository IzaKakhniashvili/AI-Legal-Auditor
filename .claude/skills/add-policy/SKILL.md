---
name: add-policy
description: End-to-end workflow for adding a new company policy PDF to the AI Legal Auditor so the agent can actually find and cite it. Use when the user wants to "add a new policy", "upload a policy file", or has dropped a PDF into the policies folder and wants it to be searchable.
---

# Add Policy

Adding a policy isn't a single step — three things must all happen, or RAG
silently won't see the new file and future audits will ignore it.

## The three required steps

1. **Place the PDF** in `documents/policies/`
2. **Extract a `.txt` sibling** (the MCP filesystem server can't parse PDFs)
3. **Re-index ChromaDB** (so RAG knows the new chunks exist)

If you skip step 3 the file is on disk but invisible to the agent.

## Where the policy comes from

| Source | Steps already done | Steps to run |
|---|---|---|
| Uploaded via UI (`POST /documents/policies/upload`) | 1 + 2 (auto) | only 3 |
| Dragged into `documents/policies/` manually | only 1 | 2 + 3 |
| Added by you via this skill | none | all 3 |

## Procedure

### 1. Place the file
```bash
cp /path/to/new_policy.pdf "$(git rev-parse --show-toplevel)/documents/policies/"
```

If the user uploaded via the UI, skip this step.

### 2. Extract `.txt`

If the file came in via the UI upload endpoint, the converter ran automatically
and a `.txt` already exists. Otherwise, run:

```bash
cd "$(git rev-parse --show-toplevel)"
source venv/bin/activate
PYTHONPATH=. python -m backend.documents.converter
```

This converts every PDF in both `policies/` and `contracts/` to a sibling
`.txt`. It's idempotent — re-running on already-converted files is safe.

Verify a `.txt` now exists next to the new PDF:
```bash
ls documents/policies/ | grep "$(basename new_policy.pdf .pdf)"
```

### 3. Re-index ChromaDB

Two ways:

**Via the running server (preferred):**
```bash
TOKEN=<jwt>
curl -X POST http://localhost:8000/rag/index \
  -H "Authorization: Bearer $TOKEN"
```

**Direct (no server needed):**
```bash
cd "$(git rev-parse --show-toplevel)"
source venv/bin/activate
PYTHONPATH=. python -c "from backend.rag.pipeline import index_policies; print(index_policies())"
```

Expected response: `{"indexed": <N>, "files": [..., "new_policy.pdf"]}`.

### 4. Verify the policy is searchable

Run a search whose ideal result is in the new policy:

```bash
curl -s "http://localhost:8000/rag/search?query=<topic-from-new-policy>&k=5" \
  -H "Authorization: Bearer $TOKEN"
```

At least one returned chunk's `source` should be `new_policy.pdf`. If not,
either the query doesn't match the policy's wording (re-phrase and retry)
or indexing didn't actually pick up the file (re-run step 3 and confirm
the response lists `new_policy.pdf`).

## Common mistakes

- **Forgetting step 3.** The file is in the folder, the `.txt` is there, but
  ChromaDB still has the old vectors. Audits won't reference the new rules.
- **Editing the `.txt` directly instead of the PDF.** The PDF is the source
  of truth — re-running the converter will overwrite manual `.txt` edits.
- **Re-indexing without restarting after `.env` changes.** Indexing reads
  paths from `settings`, which is loaded once at import time.

## Rebuilding from scratch

If the index is corrupted or you want a clean slate:

```bash
rm -rf "$(git rev-parse --show-toplevel)/chroma_db"
# then re-run step 3
```
