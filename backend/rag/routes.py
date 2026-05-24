from fastapi import APIRouter, Depends
from backend.auth.jwt import get_current_user
from backend.auth.models import User
from backend.rag.pipeline import index_policies, search_policies

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/index")
def run_indexing(current_user: User = Depends(get_current_user)):
    result = index_policies()
    return result


@router.get("/search")
def search(query: str, k: int = 5, current_user: User = Depends(get_current_user)):
    results = search_policies(query, k=k)
    return {"query": query, "results": results}
