import os
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from backend.auth.jwt import get_current_user
from backend.auth.models import User
from backend.config import settings
from backend.documents.converter import extract_pdf_to_txt

router = APIRouter(prefix="/documents", tags=["documents"])


def _list_files(folder: str) -> list[dict]:
    if not os.path.exists(folder):
        return []
    return [
        {"name": f}
        for f in sorted(os.listdir(folder))
        if f.endswith(".pdf")
    ]


@router.get("/policies")
def list_policies(current_user: User = Depends(get_current_user)):
    return _list_files(settings.policies_dir)


@router.get("/contracts")
def list_contracts(current_user: User = Depends(get_current_user)):
    return _list_files(settings.contracts_dir)


@router.post("/policies/upload")
def upload_policy(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    return _save_file(file, settings.policies_dir)


@router.post("/contracts/upload")
def upload_contract(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    return _save_file(file, settings.contracts_dir)


@router.get("/preview")
def preview_document(
    kind: str,
    name: str,
    current_user: User = Depends(get_current_user),
):
    """Return the .txt content of a policy or contract for in-app preview."""
    if kind == "policy":
        folder = settings.policies_dir
    elif kind == "contract":
        folder = settings.contracts_dir
    else:
        raise HTTPException(status_code=400, detail="kind must be 'policy' or 'contract'")

    # Security: no path traversal — only allow basenames
    if os.path.basename(name) != name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    txt_name = name[:-4] + ".txt" if name.lower().endswith(".pdf") else name
    path = os.path.join(folder, txt_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found (no .txt extracted?)")
    with open(path, "r", encoding="utf-8") as f:
        return {"name": name, "content": f.read()}


def _save_file(file: UploadFile, folder: str) -> dict:
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Convert to .txt so the MCP filesystem server can serve readable text.
    extract_pdf_to_txt(dest)
    return {"message": "Uploaded successfully", "filename": file.filename}
