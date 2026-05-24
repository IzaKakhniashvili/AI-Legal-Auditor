from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
from backend.auth.routes import router as auth_router
from backend.documents.routes import router as documents_router
from backend.rag.routes import router as rag_router
from backend.agent.routes import router as audit_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Legal Auditor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(audit_router)


@app.get("/health")
def health():
    return {"status": "ok"}
