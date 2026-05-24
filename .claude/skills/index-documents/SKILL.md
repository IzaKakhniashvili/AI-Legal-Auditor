---
name: index-documents
description: Index company policy PDFs into the ChromaDB vector store for the AI Legal Auditor RAG pipeline, and verify the index works with a test search. Use when new policy documents are added or the vector store needs rebuilding.
---

# Index Documents

Processes policy PDFs into the RAG vector store so the agent can search them
semantically.

## How the RAG pipeline works
1. Policy PDFs in `documents/policies/` are loaded page by page with `pypdf`
   directly (no `PyPDFLoader` — avoids pulling in `transformers`).
2. Each page is split into overlapping ~1000-character chunks by the inline
   recursive splitter `backend/rag/pipeline.py::_split_text` (no
   `langchain_text_splitters` for the same reason).
3. Each chunk is embedded with **`fastembed`** running `all-MiniLM-L6-v2`
   on the ONNX runtime — local, no API cost, no PyTorch.
4. Vectors are stored in ChromaDB, persisted to `chroma_db/` in the project root.
5. At query time, `search_policies` embeds the query and returns the top
   `k=12` chunks (tuned up from the default 5 for better auditor recall).

Only **policies** are indexed. Contracts are read fresh per audit, not indexed.

> ⚠️ **Embedder changes require wiping `chroma_db/`.** Vectors from different
> embedders are not comparable — silently bad retrieval otherwise. See
> "Rebuilding from scratch" below.

## Steps

### 1. Make sure policy PDFs exist
```bash
ls "$(git rev-parse --show-toplevel)/documents/policies/"
```
If empty, the assignment's sample PDFs must be copied in first.

### 2. Run indexing
With the backend running, call the endpoint (needs a JWT token):

```bash
curl -s -X POST http://localhost:8000/rag/index \
  -H "Authorization: Bearer $TOKEN"
```

Expected response: `{"indexed": <chunk count>, "files": [...]}`.

Or run it directly without the server:
```bash
cd "$(git rev-parse --show-toplevel)"
source venv/bin/activate
PYTHONPATH=. python -c "from backend.rag.pipeline import index_policies; print(index_policies())"
```

### 3. Verify with a test search
```bash
curl -s "http://localhost:8000/rag/search?query=payment%20terms&k=3" \
  -H "Authorization: Bearer $TOKEN"
```

A good result returns chunks whose `content` is topically relevant to the query,
each with a `source` file and `relevance_score`. Note: the audit agent itself
calls `search_policies` with `k=12` (set in `backend/rag/pipeline.py`); the
HTTP endpoint `k` is just for ad-hoc inspection.

## Rebuilding from scratch
If the index is stale, corrupted, or the embedding model has changed,
delete the store and re-index:
```bash
rm -rf "$(git rev-parse --show-toplevel)/chroma_db"
```
Then run step 2 again. **Always do this after switching embedders** — for
example, the project was migrated from HuggingFace `sentence-transformers`
to `fastembed`, and the old vectors had to be wiped before the new ones
worked correctly.
