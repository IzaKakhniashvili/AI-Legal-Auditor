"""
RAG (Retrieval-Augmented Generation) pipeline.

How RAG works:
1. INDEXING (done once): Read PDFs → split into chunks → convert chunks to
   vectors (numbers that capture meaning) → store in ChromaDB
2. RETRIEVAL (done per query): Convert query to vector → find most similar
   chunks in DB → return them as context
3. GENERATION: Feed retrieved context + question to the LLM

This means the AI can "search" through your policy documents semantically —
e.g. searching "payment terms" will find chunks about invoices, deadlines,
net-30 clauses even if exact phrase isn't there.

Performance note:
  The heavy langchain / chromadb / huggingface imports happen LAZILY, inside
  the functions that need them. This lets `uvicorn` start the API in <2s
  instead of 30-60s — the cost of warming chromadb is paid on the first RAG
  call, not at import time.
"""

import os
from functools import lru_cache
from backend.config import settings


@lru_cache(maxsize=1)
def _get_embeddings():
    """Embedding model singleton — loaded once per process, then cached.

    Uses fastembed (ONNX runtime) instead of HuggingFaceEmbeddings to skip
    the ~200-file transformers/torch import chain. Same MiniLM-L6-v2 model,
    same 384-dim vectors (so the existing ChromaDB index stays compatible),
    but loads in ~1s instead of minutes on memory-pressured machines.
    """
    # Lazy import so server startup isn't blocked.
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    return FastEmbedEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def _get_vectorstore(collection_name: str):
    # Lazy import for the same reason.
    from langchain_community.vectorstores import Chroma
    return Chroma(
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
        persist_directory=settings.chroma_db_path,
    )


def _split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """Recursive character splitter — pure Python, no transformers dependency.

    Tries to split on the most natural boundaries first (paragraph → line →
    space → char). Equivalent semantics to langchain's RecursiveCharacterTextSplitter
    for our use case, without pulling in `transformers` via langchain_text_splitters.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    for separator in ("\n\n", "\n", " ", ""):
        if separator and separator not in text:
            continue
        parts = text.split(separator) if separator else list(text)
        chunks: list[str] = []
        current = ""
        for part in parts:
            piece = (separator + part) if (current and separator) else part
            if len(current) + len(piece) <= chunk_size:
                current += piece
            else:
                if current:
                    chunks.append(current)
                if len(part) > chunk_size:
                    # Sub-part still too big — recurse with next-finer separator
                    chunks.extend(_split_text(part, chunk_size, chunk_overlap))
                    current = ""
                else:
                    current = part
        if current:
            chunks.append(current)

        # Apply overlap by prepending tail of previous chunk to next
        if chunk_overlap > 0 and len(chunks) > 1:
            overlapped = [chunks[0]]
            for prev, nxt in zip(chunks, chunks[1:]):
                tail = prev[-chunk_overlap:] if len(prev) > chunk_overlap else prev
                overlapped.append(tail + nxt)
            chunks = overlapped
        return chunks
    return [text]


def index_policies() -> dict:
    """Load all policy PDFs and store them in the vector DB."""
    # Lazy imports — only paid the first time indexing actually runs.
    # pypdf is used directly (not via langchain) so we don't drag in the
    # langchain_text_splitters → transformers import chain.
    from pypdf import PdfReader

    policies_path = settings.policies_dir
    pdf_files = [f for f in os.listdir(policies_path) if f.endswith(".pdf")]

    if not pdf_files:
        return {"indexed": 0, "message": "No PDFs found in policies folder"}

    from langchain_core.documents import Document
    all_chunks: list = []

    for pdf_file in pdf_files:
        reader = PdfReader(os.path.join(policies_path, pdf_file))
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            for chunk_text in _split_text(page_text, chunk_size=1000, chunk_overlap=200):
                all_chunks.append(
                    Document(
                        page_content=chunk_text,
                        metadata={"source_file": pdf_file, "page": page_idx},
                    )
                )

    vectorstore = _get_vectorstore("policies")
    vectorstore.add_documents(all_chunks)

    return {"indexed": len(all_chunks), "files": pdf_files}


def search_policies(query: str, k: int = 12) -> list[dict]:
    """Semantically search policy documents. Returns top-k relevant chunks.

    k=12 — gives the agent a wider window of candidate chunks per query so
    that relevant rules sitting at rank 6–12 still reach Claude's context.
    Cost per search is small (a few thousand extra input tokens), recall
    improves noticeably. Diminishing returns kick in around k≈15.
    """
    vectorstore = _get_vectorstore("policies")
    results = vectorstore.similarity_search_with_score(query, k=k)

    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source_file", "unknown"),
            "page": doc.metadata.get("page", 0),
            "relevance_score": float(score),
        }
        for doc, score in results
    ]
