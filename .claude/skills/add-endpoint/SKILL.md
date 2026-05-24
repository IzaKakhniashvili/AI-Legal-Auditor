---
name: add-endpoint
description: Scaffold a new FastAPI endpoint in the AI Legal Auditor backend following project conventions (APIRouter, Pydantic schemas, JWT auth dependency). Use when the user wants to add a new API route or feature module.
---

# Add Endpoint

Adds a new FastAPI endpoint that follows this project's conventions.

## Project conventions

1. **Each feature is a package** under `backend/` (e.g. `backend/auth/`, `backend/rag/`).
2. **Routes live in `routes.py`** and expose a module-level `router = APIRouter(prefix=..., tags=...)`.
3. **Request/response shapes are Pydantic models** in `schemas.py`.
4. **Protected routes** take `current_user: User = Depends(get_current_user)`.
5. **DB access** uses `db: Session = Depends(get_db)`.
6. The router must be registered in `backend/main.py` with `app.include_router(...)`.

## Steps to add a new endpoint

### 1. Define the schema (if it takes/returns structured data)
In the feature's `schemas.py`:

```python
from pydantic import BaseModel

class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    result: str
```

### 2. Add the route in `routes.py`

```python
from fastapi import APIRouter, Depends
from backend.auth.jwt import get_current_user
from backend.auth.models import User
from backend.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/myfeature", tags=["myfeature"])


@router.post("/action", response_model=MyResponse)
def do_action(
    payload: MyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ...
    return MyResponse(result="done")
```

### 3. Register the router in `backend/main.py`

```python
from backend.myfeature.routes import router as myfeature_router
app.include_router(myfeature_router)
```

### 4. Verify
Restart the server and confirm the endpoint appears in
http://localhost:8000/docs and in `GET /openapi.json`.

## Rules
- Always add `Depends(get_current_user)` unless the endpoint is intentionally public
  (only `/auth/register`, `/auth/login`, and `/health` are public).
- Never return absolute filesystem paths in responses — leak risk.
- Raise `HTTPException` with a clear `detail` message for error cases.
