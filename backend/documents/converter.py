"""
PDF -> text conversion utility (Task 1 — infrastructure).

Why this exists:
The official MCP filesystem server reads files as text/binary; it does NOT
parse PDF format. So for the Task 2 agent to read a document's actual text
via MCP, each PDF is converted once to a .txt file alongside it.

Design choice: convert at write-time (when a file is added/uploaded), not at
read-time. The text is extracted once and reused — the MCP server then serves
clean .txt, and the Task 2 client stays pure orchestration. Original PDFs are
always kept.

Run directly to convert every document already in the folders:
    PYTHONPATH=. python -m backend.documents.converter
"""

import os
from pypdf import PdfReader
from backend.config import settings


def extract_pdf_to_txt(pdf_path: str) -> str:
    """Extract text from one PDF and write a .txt next to it.

    Returns the path of the created .txt file.
    """
    reader = PdfReader(pdf_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    txt_path = os.path.splitext(pdf_path)[0] + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    return txt_path


def convert_folder(folder: str) -> list[str]:
    """Convert every PDF in a folder to .txt. Returns the created .txt paths."""
    if not os.path.exists(folder):
        return []
    created = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".pdf"):
            created.append(extract_pdf_to_txt(os.path.join(folder, name)))
    return created


def convert_all() -> dict:
    """Convert every PDF in both the policies and contracts folders."""
    policies = convert_folder(settings.policies_dir)
    contracts = convert_folder(settings.contracts_dir)
    return {"policies": policies, "contracts": contracts}


if __name__ == "__main__":
    result = convert_all()
    total = len(result["policies"]) + len(result["contracts"])
    print(f"Converted {total} PDF(s) to .txt")
    for path in result["policies"] + result["contracts"]:
        print(f"  {os.path.basename(path)}")
