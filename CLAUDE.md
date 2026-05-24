# AI Legal Repository Auditor — Claude Code Context

## Project Overview
Automated compliance-checking platform that audits legal contracts against
company policies using **MCP tools + RAG + Claude**.

A user uploads policies (company rules) and contracts. A hand-written agent
reads each contract via the official MCP filesystem server, semantically
searches policies via a RAG pipeline, and produces a structured JSON audit
report. A chat panel lets the user request specific clause rewrites grounded
in policy.

## Architecture

```
ai-legal-auditor/
├── backend/                       ← FastAPI Python backend
│   ├── main.py                    ← App entry, registers routers + CORS
│   ├── config.py                  ← Pydantic Settings (loads backend/.env)
│   ├── database.py                ← SQLAlchemy SQLite + get_db dependency
│   ├── mcp_config.py              ← MCP filesystem server launch parameters
│   ├── auth/
│   │   ├── models.py              ← User table
│   │   ├── schemas.py             ← UserRegister, UserLogin, Token
│   │   ├── jwt.py                 ← create_access_token, get_current_user
│   │   └── routes.py              ← /auth/register, /auth/login, /auth/me
│   ├── documents/
│   │   ├── routes.py              ← list/upload/preview policies & contracts
│   │   └── converter.py           ← PDF → .txt extraction (MCP-readable)
│   ├── rag/
│   │   ├── pipeline.py            ← index_policies, search_policies
│   │   └── routes.py              ← /rag/index, /rag/search
│   └── agent/                     ← MCP client orchestration (Task 2 — hand-written)
│       ├── orchestrator.py        ← audit_contract, critique_report, chat_about_audit,
│       │                           build_claude_tools, run_tool, parse_final_report,
│       │                           parse_additional_findings, list_policy_files
│       ├── system_prompts.py      ← AUDIT_SYSTEM_PROMPT, CRITIC_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT
│       ├── verifier.py            ← Programmatic verification of audit findings
│       └── routes.py              ← /audit/run, /audit/chat
├── documents/
│   ├── policies/                  ← Company policy PDFs (indexed into RAG)
│   └── contracts/                 ← Contracts under review (read via MCP per audit)
├── frontend/                      ← React + Vite UI (Task 3)
│   └── src/
│       ├── pages/                 ← Login, Register, Dashboard
│       ├── components/            ← FileExplorer, ReportDisplay, ChatPanel, DocumentPreview
│       ├── api.js                 ← Single fetch helper, tolerates non-JSON errors
│       └── AuthContext.jsx
├── .claude/skills/                ← Project Skills (committed)
├── chroma_db/                     ← Vector DB on disk (gitignored)
├── CLAUDE.md                      ← this file
├── README.md
└── .env  (in backend/, gitignored)
```

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Auth**: JWT via python-jose, bcrypt via passlib
- **RAG**: ChromaDB + `fastembed` (ONNX) `all-MiniLM-L6-v2` (local, no API cost,
  no PyTorch / `transformers` dependency)
- **PDF + chunking**: `pypdf` directly + inline recursive character splitter in
  `backend/rag/pipeline.py::_split_text` (deliberately avoids
  `langchain_text_splitters` and `PyPDFLoader`, both of which import
  `transformers` at module load and made cold-start unbearably slow)
- **Agent runtime**: Anthropic Claude — `claude-opus-4-7`, `temperature=0`,
  `max_iterations=20` for the auditor, `10` for the critic
- **MCP server**: Official `@modelcontextprotocol/server-filesystem` (npx, stdio)
- **Frontend**: React + Vite

## Key Design Decisions
- Python 3.11 required — `mcp` package needs `>=3.10`
- All paths anchored to `PROJECT_ROOT` (computed in `config.py`)
- ChromaDB persists to `chroma_db/` in the project root
- **Policies are indexed** into RAG (knowledge base, queried many times)
- **Contracts are NOT indexed** — read fresh via MCP per audit
- `get_current_user()` is a FastAPI dependency injected into every protected route
- **PDF → `.txt` conversion at upload time**: the official MCP filesystem server
  reads files as text/binary; it does not parse PDF. So each PDF is converted
  once to a sibling `.txt` (`converter.py`). MCP serves clean text, and the
  hand-written Task 2 client stays pure orchestration. Original PDFs are kept.
- **`temperature=0`** for audit + chat — as deterministic as Claude gets;
  some run-to-run variance in finding count is still expected (LLMs are not
  fully deterministic even at 0).
- **Two-pass audit (junior + critic)** — `audit_contract` runs the full
  agent loop, then `critique_report` runs a short second pass with
  `CRITIC_SYSTEM_PROMPT`, telling the model "here is the junior's report,
  re-read the contract, find what was missed, return only the extras".
  Extras are appended to `report["findings"]` and counted in
  `report["critic_added"]`. Roughly doubles cost; measurably improves recall.
- **`k=12`** in `search_policies` — tuned up from 5; the auditor model uses
  the wider context to catch more borderline violations.
- **Programmatic verification** runs after every audit (`verifier.py`) — flags
  findings whose cited policy file doesn't exist or whose quoted clause text
  can't be located in the contract. Catches the cheapest classes of hallucination
  at zero LLM cost. Both clause and contract are passed through the same
  `_normalize` (lowercase, punctuation → spaces, collapse whitespace) so
  smart quotes / line breaks inside quoted clauses don't trigger false
  "unverified" warnings.
- **`--reload-dir backend`** is mandatory when running uvicorn with
  `--reload`. The default watches the whole project root including `venv/`;
  when `fastembed` / `chromadb` first load they touch `.pyc` files in `venv/`
  and uvicorn kills the in-flight request mid-audit.

## MCP Infrastructure (Task 1)
- Server: `@modelcontextprotocol/server-filesystem` (official, run via npx)
- Transport: stdio — the client spawns it as a subprocess
- Sandboxed to the `documents/` folder (can reach `policies/` and `contracts/` only)
- Launch parameters live in `backend/mcp_config.py` (`MCP_FILESYSTEM_SERVER`)
- Task 2 client imports that config to spawn and connect to the server

## Agent Orchestration (Task 2 — hand-written)
The agent loop lives in `backend/agent/orchestrator.py` and was written
entirely by hand per the assignment rule. Three entry points:

- **`audit_contract(contract_name)`** — runs the junior auditor loop,
  parses the JSON report, then invokes `critique_report` in the same MCP
  session and merges any additional findings before returning.
- **`critique_report(report, contract_path, session, claude_tools)`** —
  second-pass loop with `CRITIC_SYSTEM_PROMPT`, given the junior's report
  and the list of policy filenames; returns only the *new* findings.
- **`chat_about_audit(contract_name, audit_report, history, user_message)`** —
  continues a conversation about an audit, returns plain text. `CHAT_SYSTEM_PROMPT`
  is tightened so "rewrite clause 3" produces the rewritten clause directly,
  not commentary.

All three reuse:
- `build_claude_tools(session)` — list MCP tools, translate to Anthropic schema, append custom `search_policies`
- `run_tool(block, session)` — route a `tool_use` block to either RAG or MCP
- The same loop pattern: `for _ in range(max_iterations): create → if end_turn break → if tool_use run+continue`

Helpers:
- `parse_final_report(message)` — extract JSON from junior's final text
- `parse_additional_findings(message)` — extract JSON from critic's final text
- `list_policy_files()` — names of `.pdf` files in `documents/policies/`,
  passed into the critic's context so it knows what to sweep

## Running the Backend
```bash
# from project root
source venv/bin/activate
unset ANTHROPIC_API_KEY    # see note below
PYTHONPATH=. uvicorn backend.main:app --reload --reload-dir backend --port 8000
```

`--reload-dir backend` is **required** — see Key Design Decisions above.

> ⚠️ **macOS / Claude Desktop note**: if your terminal was launched from
> Claude Desktop, it inherits an empty `ANTHROPIC_API_KEY=""` env var that
> overrides your `.env`. Always prefix the run command with
> `unset ANTHROPIC_API_KEY &&` or use a native Terminal session.

## Running the Frontend
```bash
cd frontend
npm install      # first time only
npm run dev
```
Open http://localhost:5173.

## API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | No | Create account |
| POST | /auth/login | No | Get JWT token |
| GET | /auth/me | Yes | Current user |
| GET | /documents/policies | Yes | List policy PDFs |
| GET | /documents/contracts | Yes | List contract PDFs |
| POST | /documents/policies/upload | Yes | Upload policy PDF (auto-converts to .txt) |
| POST | /documents/contracts/upload | Yes | Upload contract PDF (auto-converts to .txt) |
| GET | /documents/preview | Yes | Return a doc's `.txt` for UI preview |
| POST | /rag/index | Yes | Re-index policies into ChromaDB |
| GET | /rag/search | Yes | Semantic search over policies |
| POST | /audit/run | Yes | Run a compliance audit on a contract |
| POST | /audit/chat | Yes | Continue conversation about an audit |
| GET | /health | No | Health check |

## Task Rules (from the assignment, verbatim)

> While working on the project, Claude Code is mandatory only in the first and third tasks.
> You must have the appropriate Skills configured in Claude Code. All important project
> context, configurations, conventions, and architectural decisions must be reflected in the
> CLAUDE.md file or README, so that Claude Code has full context in any session. If
> necessary, additional instructions and plugins must also be written down in these files.

Applied here:
- **Task 1** (auth + infra + RAG + MCP setup): Claude Code used ✓
- **Task 2** (`backend/agent/orchestrator.py`): Hand-written, no AI assistance
- **Task 3** (React frontend): Claude Code used ✓
- This `CLAUDE.md` carries the full project context, conventions, and decisions
- Project Skills live in `.claude/skills/` and are committed so they load automatically

## Claude Code Skills
Project skills live in `.claude/skills/` and are committed to the repo, so anyone
who clones it and opens Claude Code gets them automatically.

| Skill | Purpose |
|-------|---------|
| `run-backend` | Start the FastAPI server with correct venv / PYTHONPATH / unset, and run integration tests |
| `add-endpoint` | Scaffold a new FastAPI endpoint following project conventions |
| `index-documents` | Index policy PDFs into ChromaDB and verify with a test search |
| `add-policy` | End-to-end workflow for adding a new policy PDF (place → convert → re-index → verify) |

All skills are deliberately scoped to **Task 1 (infra/RAG) and Task 3 (frontend)**
territory. 

## Environment Variables (backend/.env)
```
SECRET_KEY=<long random string for JWT signing>
ANTHROPIC_API_KEY=sk-ant-api03-...
```

The `DATABASE_URL` is computed in `config.py` (SQLite file in project root)
and does not need to be set in `.env`.
