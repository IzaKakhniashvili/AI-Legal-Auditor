from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.auth.jwt import get_current_user
from backend.auth.models import User
from backend.agent.orchestrator import audit_contract, chat_about_audit
from backend.agent.verifier import verify_report


router = APIRouter(prefix="/audit", tags=["audit"])

class AuditRequest(BaseModel):
    contract_name: str


@router.post("/run")
async def run_audit(
    payload: AuditRequest,
    current_user: User = Depends(get_current_user),
):
    """Run a compliance audit on the given contract file."""
    result = await audit_contract(payload.contract_name)
    # Programmatic verification — catches the cheapest classes of hallucination
    result = verify_report(result)
    return result


class ChatRequest(BaseModel):
    contract_name: str
    audit_report: dict
    history: list
    message: str


@router.post("/chat")
async def run_chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Continue a conversation about an audited contract."""
    reply = await chat_about_audit(
        payload.contract_name,
        payload.audit_report,
        payload.history,
        payload.message,
    )
    return {"reply": reply}