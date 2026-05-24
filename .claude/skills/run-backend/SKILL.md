---
name: run-backend
description: Start the AI Legal Auditor FastAPI backend and run the integration test suite. Use when the user wants to launch the server, restart it, or verify the backend endpoints work.
---

# Run Backend

Starts the FastAPI backend correctly and verifies it with integration tests.

## Important project quirks
- The backend uses absolute imports (`from backend.config import ...`), so `PYTHONPATH`
  must point at the project root.
- Python 3.11 is required (the `mcp` package needs Python >= 3.10).
- The virtual environment lives at `venv/` in the project root.
- `--reload-dir backend` is **mandatory**. Default uvicorn `--reload` watches
  the whole project root, including `venv/`. When `fastembed` / `chromadb`
  first load and touch `.pyc` files inside `venv/`, the watcher fires
  "code changed" and kills the in-flight audit request. Scoping the watch
  to `backend/` only avoids that.
- If the terminal was launched from Claude Desktop it inherits an empty
  `ANTHROPIC_API_KEY=""` that overrides `backend/.env`. Always
  `unset ANTHROPIC_API_KEY` first, or run from a fresh Terminal.

## Starting the server

```bash
cd "$(git rev-parse --show-toplevel)"
source venv/bin/activate
unset ANTHROPIC_API_KEY
PYTHONPATH=. uvicorn backend.main:app --reload --reload-dir backend --port 8000
```

If port 8000 is already in use, free it first:

```bash
lsof -ti:8000 | xargs kill -9 2>/dev/null
```

First boot warms the `fastembed` ONNX model — expect a few seconds of CPU
while it downloads/loads the model on the very first request. Subsequent
requests reuse the cached module-level singleton.

## Verifying it works

After the server is up, run these checks:

```bash
# 1. Health check
curl -s http://localhost:8000/health

# 2. Register a test user
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser","password":"secret123"}'

# 3. Login and capture the JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 4. Call a protected endpoint
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
```

Expected: health returns `{"status":"ok"}`, register returns a user object,
login returns an `access_token`, and `/auth/me` returns the user.

## Interactive API docs
FastAPI auto-generates docs at http://localhost:8000/docs once the server runs.
