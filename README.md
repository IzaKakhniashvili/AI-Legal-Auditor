# AI Legal Repository Auditor

Automated compliance-checking platform that audits legal contracts against
company policy documents using **MCP tools + RAG + Claude**.

The user uploads policies (company rules) and contracts (incoming agreements).
A hand-written agent reads each contract via the official MCP filesystem
server, searches policies via a RAG pipeline, and produces a structured
compliance report. A chat panel lets the user request specific clause rewrites
grounded in policy.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + SQLAlchemy + SQLite |
| Auth | JWT (python-jose), bcrypt password hashing (passlib) |
| RAG | ChromaDB + **fastembed (ONNX)** `all-MiniLM-L6-v2` (local, no API cost, no PyTorch/transformers dependency) |
| PDF + chunking | `pypdf` + inline recursive character splitter (avoids `langchain_text_splitters` → `transformers` import chain) |
| Agent runtime | Anthropic Claude (`claude-opus-4-7`), `temperature=0` |
| MCP server | Official `@modelcontextprotocol/server-filesystem` (npx, stdio) |
| Frontend | React + Vite |

---

## Project structure

```
ai-legal-auditor/
├── backend/
│   ├── main.py                ← FastAPI app, registers routers
│   ├── config.py              ← Settings (loads .env via pydantic-settings)
│   ├── database.py            ← SQLAlchemy SQLite setup + get_db dependency
│   ├── mcp_config.py          ← MCP filesystem server launch parameters
│   ├── auth/                  ← JWT auth (register / login / me)
│   ├── documents/             ← Folder listing, upload, PDF→txt conversion, preview
│   ├── rag/                   ← Indexing + semantic search of policies
│   └── agent/                 ← Hand-written agent (orchestrator.py)
│       ├── orchestrator.py    ← audit_contract + critique_report + chat_about_audit (Task 2)
│       ├── system_prompts.py  ← AUDIT_ / CRITIC_ / CHAT_SYSTEM_PROMPT
│       ├── verifier.py        ← Programmatic verification of audit findings
│       └── routes.py          ← /audit/run + /audit/chat endpoints
├── documents/
│   ├── policies/              ← company rules (indexed into RAG)
│   └── contracts/             ← contracts under review
├── frontend/                  ← React UI
│   └── src/
│       ├── pages/             ← Login, Register, Dashboard
│       ├── components/        ← FileExplorer, ReportDisplay, ChatPanel, DocumentPreview
│       ├── api.js
│       └── AuthContext.jsx
├── .claude/skills/            ← Project Skills (committed for Claude Code)
├── CLAUDE.md                  ← Project context for Claude Code sessions
└── README.md                  ← this file
```

---

## Prerequisites

- **Python 3.10+** (3.11 used in development) — MCP package requires `>=3.10`
- **Node 18+** + npm (for the frontend)
- **`npx`** in PATH (the MCP filesystem server is run via npx)
- **Anthropic API key** with credits 

---

## Setup

### 1. Clone and create the Python virtual environment

```bash
git clone <repo-url> ai-legal-auditor
cd ai-legal-auditor

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   
```

If there's no `requirements.txt`, install directly:

```bash
pip install fastapi uvicorn sqlalchemy "python-jose[cryptography]" \
  "passlib[bcrypt]" python-multipart pydantic-settings \
  chromadb langchain-core langchain-community \
  fastembed pypdf anthropic "mcp[cli]"
```

> Note: `fastembed` (ONNX runtime) replaces `sentence-transformers` + `transformers` + `torch`.
> This dramatically shortens cold start and avoids transformers' multi-minute
> model-registry scan on memory-pressured machines. We also no longer use
> `langchain_text_splitters` or `PyPDFLoader` — chunking is a tiny inline
> recursive splitter and PDF parsing is direct `pypdf` — both to keep the
> `transformers` import chain entirely out of the indexing path.

### 2. Configure environment variables

Create `backend/.env`:

```
SECRET_KEY=<long-random-string-for-jwt-signing>
ANTHROPIC_API_KEY=sk-ant-api03-...your-key...
```

> ⚠️ **macOS / Claude Desktop note:** if you launch the terminal from
> Claude Desktop, an empty `ANTHROPIC_API_KEY=""` may be inherited and
> override your `.env`. Either start uvicorn from a fresh Terminal app,
> or prefix the run command with `unset ANTHROPIC_API_KEY &&`.

### 3. Add the test data

Drop policy PDFs into `documents/policies/` and contract PDFs into
`documents/contracts/`. The PDFs supplied with the assignment work as-is.

The system auto-converts PDFs to `.txt` on upload (needed because the official
MCP filesystem server reads files as text/binary — it doesn't parse PDF
format). To convert files placed manually, run:

```bash
PYTHONPATH=. python -m backend.documents.converter
```

### 4. Index the policies (RAG)

This loads policy PDFs into ChromaDB. Run once initially and any time
policies change:

```bash
PYTHONPATH=. python -c "from backend.rag.pipeline import index_policies; print(index_policies())"
```

Or after the server is running, hit `POST /rag/index` with a logged-in user
(also exposed in the UI as **"Re-index policies"**).

### 5. Run the backend

```bash
cd ai-legal-auditor
source venv/bin/activate
PYTHONPATH=. uvicorn backend.main:app --reload --reload-dir backend --port 8000
```

> ⚠️ `--reload-dir backend` is required. Without it, uvicorn watches the entire
> project root including `venv/`. When `fastembed` / `chromadb` first load and
> touch `.pyc` files inside `venv/`, the watcher detects "code changed" and
> kills the in-flight request mid-audit. Scoping the watcher to `backend/`
> only avoids that.

Interactive API docs: http://localhost:8000/docs

### 6. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

---

## Using the app

1. **Register** an account, then log in.
2. The **left panel** lists policies and contracts. Upload more via **+ Upload**
   if needed.
3. Click any file to **preview** its text in the center panel.
4. Select a **contract** and click **Run Compliance Audit**. The agent reads
   the contract via MCP, semantically searches policies via RAG, compares
   each clause to the relevant rules, and produces a structured report
   (findings grouped by severity, each with a citation and a concrete
   suggested fix). Takes ~30–90 seconds.
5. Use the **chat panel** to ask for specific changes:
   *"Rewrite clause 4.3 to comply with the payment policy."* The agent
   responds with the new clause text, cited to the policy file.

---

## Architecture highlights

### MCP infrastructure (Task 1)

- The official `@modelcontextprotocol/server-filesystem` runs as a stdio
  subprocess, sandboxed to the `documents/` folder.
- Launch parameters live in `backend/mcp_config.py`.
- The Task 2 client spawns it on every audit/chat call.

### PDF handling

The official filesystem MCP server cannot parse PDF format — it returns raw
binary. So every PDF is converted to a sibling `.txt` once at upload time
(`backend/documents/converter.py`). The MCP server then serves clean text
to the agent. Original PDFs are kept.

### RAG pipeline

- Only **policies** are indexed in the vector store. Contracts are read
  per-audit via MCP, never embedded.
- Embeddings: **fastembed** `all-MiniLM-L6-v2` (384 dims) running on ONNX
  runtime, loaded locally, cached as a module-level singleton. No PyTorch,
  no `transformers`, no model-registry scan at startup.
- PDFs are parsed with `pypdf` directly and split into ~1000-char chunks with
  a tiny inline recursive splitter (`backend/rag/pipeline.py::_split_text`).
- Retrieval returns `k=12` chunks per query — tuned upward from the default
  5 because more candidate clauses gave the auditor agent measurably better
  recall on the assignment's sample contracts.
- ChromaDB persists to `chroma_db/` in the project root. Wipe the directory
  whenever the embedder changes — vectors from different embedders are not
  comparable.

### Agent orchestration (Task 2 — hand-written)

The agent loop lives in `backend/agent/orchestrator.py` and was written by
hand per the assignment's explicit rule. It:

1. Spawns the MCP server (`stdio_client` + `ClientSession`).
2. Lists MCP tools and translates each to Anthropic's `tools` format
   (notably the `inputSchema` → `input_schema` rename).
3. Adds a custom `search_policies` tool wrapping the RAG search.
4. Runs a bounded `for` loop, calling `client.messages.create` and handling
   `stop_reason == "tool_use"` until Claude returns `end_turn`.
5. Routes each `tool_use` block to either `search_policies` (local Python
   function) or the MCP `session.call_tool(...)` (file operations).
6. Returns parsed JSON (audit) or plain text (chat).

`temperature=0` is used for consistent reruns of the same contract.

### Two-pass audit (junior + critic)

A single LLM pass tends to miss 2–4 findings on the assignment's sample
contracts even at `temperature=0`. To improve recall:

1. The **junior auditor** (`audit_contract`) runs the full agent loop and
   produces the initial structured report.
2. The **critic** (`critique_report`, using `CRITIC_SYSTEM_PROMPT`) then runs
   a second short agent loop with: the contract path, the list of policy
   files on disk, and the junior's report (as "do not duplicate these").
   The critic re-reads the contract via MCP, searches policies via RAG, and
   returns only **additional** findings.
3. Extras are appended to `report["findings"]` and the count is stored in
   `report["critic_added"]` for transparency.

### Programmatic verifier

`backend/agent/verifier.py` runs after the audit returns and flags findings
whose cited policy file doesn't exist on disk or whose quoted clause text
can't be located in the contract. Catches the cheapest classes of
hallucination at zero LLM cost. Both the clause and the contract text are
passed through the same `_normalize` function (lowercase, punctuation →
spaces, collapse whitespace) so trivial formatting differences (smart
quotes, line breaks inside a quoted clause) don't produce false
"unverified" warnings.

### Auth

- JWT bearer tokens, 24-hour expiry.
- Passwords hashed with bcrypt via passlib.
- Protected routes use FastAPI's `Depends(get_current_user)` dependency.

---

## API surface (selected)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | no | Create account |
| POST | `/auth/login` | no | Get JWT |
| GET | `/auth/me` | yes | Current user |
| GET | `/documents/policies` | yes | List policies |
| GET | `/documents/contracts` | yes | List contracts |
| POST | `/documents/policies/upload` | yes | Upload policy PDF |
| POST | `/documents/contracts/upload` | yes | Upload contract PDF |
| GET | `/documents/preview` | yes | Get a doc's text content (for UI preview) |
| POST | `/rag/index` | yes | Re-index policies into ChromaDB |
| GET | `/rag/search` | yes | Semantic search over policies |
| POST | `/audit/run` | yes | Run a compliance audit on a contract |
| POST | `/audit/chat` | yes | Continue conversation about an audit |

---

## Claude Code Skills

Project Skills live in `.claude/skills/` and are committed, so they auto-load
for anyone opening the repo in Claude Code:

| Skill | Purpose |
|---|---|
| `run-backend` | Start uvicorn with the correct env + run integration tests |
| `add-endpoint` | Scaffold a new FastAPI endpoint per project conventions |
| `index-documents` | Index policy PDFs into ChromaDB |
| `compliance-report` | Standard format for compliance reports |

See `CLAUDE.md` for the full project context.

---

## Task assignment compliance

> Claude Code is mandatory only in the first and third tasks.

- **Task 1** — auth, RAG infrastructure, MCP server setup: Claude Code used.
- **Task 2** — agent orchestration (`backend/agent/orchestrator.py`):
  hand-written, no AI assistance, per the explicit rule.
- **Task 3** — React frontend: Claude Code used.

---

## Known limitations

- The chat agent **rewrites** clauses but does **not** modify the contract
  files on disk. The user applies changes manually.
- Audit time is ~60–180 seconds end-to-end — the two-pass design (junior +
  critic) roughly doubles the LLM cost and time vs a single pass, in
  exchange for better recall. Most of the wall time is Claude API latency
  over many tool iterations, not local processing.
- `anthropic.messages.create()` is a sync call inside an `async` request
  handler. While Claude is thinking, that single Uvicorn worker can't serve
  other requests (e.g. `/health`). Acceptable for a single-user demo; would
  need `asyncio.to_thread` (or the async Anthropic client) before going
  multi-user.
- Embedding model is English-tuned (`all-MiniLM-L6-v2`). Non-English queries
  work because Claude reformulates them into English for retrieval; for
  better multilingual recall, swap to `paraphrase-multilingual-MiniLM-L12-v2`
  in `backend/rag/pipeline.py::_get_embeddings` and wipe `chroma_db/`.
