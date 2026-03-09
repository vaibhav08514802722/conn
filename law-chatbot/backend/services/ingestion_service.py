"""
─────────────────────────────────────────────────────────────────────────────
Phase 2 — Ingestion Service
Handles PDF loading → chunking → embedding → storing in Qdrant.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import uuid
import tempfile
from datetime import datetime

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore

from backend.config import settings
from backend.deps import get_embeddings, get_qdrant_client, get_db


# ── Text splitter (shared config) ─────────────────────────────────────────────
def get_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


# ── Ingest a PDF file from a local path ───────────────────────────────────────
def ingest_pdf(file_path: str, metadata: dict) -> dict:
    """
    Load a PDF, split into chunks, embed, and store in Qdrant.
    Returns a summary: { doc_id, chunk_count, status }
    """
    doc_id = metadata.get("doc_id") or str(uuid.uuid4())

    # 1. Load all pages from the PDF
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    # 2. Enrich each page with our custom metadata
    for page in pages:
        page.metadata.update({
            "doc_id":       doc_id,
            "document_title": metadata.get("title", "Unknown"),
            "act_name":     metadata.get("act_name", ""),
            "source_type":  "pdf",
            "source":       metadata.get("title", os.path.basename(file_path)),
        })

    # 3. Split into smaller chunks
    splitter = get_splitter()
    chunks = splitter.split_documents(pages)

    # 4. Store all chunks in Qdrant
    QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
    )

    return {"doc_id": doc_id, "chunk_count": len(chunks), "status": "complete"}


# ── Handle an uploaded PDF (UploadFile from FastAPI) ──────────────────────────
async def ingest_uploaded_file(upload_file, title: str, act_name: str = "") -> dict:
    """
    Save the uploaded PDF to a temp file, run ingestion,
    and record the document in MongoDB.
    """
    db = get_db()
    doc_id = str(uuid.uuid4())

    # Track as 'processing' in MongoDB immediately
    db.documents.insert_one({
        "_id":         doc_id,
        "title":       title,
        "act_name":    act_name,
        "source_type": "pdf",
        "status":      "processing",
        "chunk_count": 0,
        "uploaded_at": datetime.utcnow().isoformat(),
    })

    try:
        # Write upload to a temp file so PyPDFLoader can read it
        suffix = os.path.splitext(upload_file.filename)[1] or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await upload_file.read())
            tmp_path = tmp.name

        result = ingest_pdf(
            tmp_path,
            {"doc_id": doc_id, "title": title, "act_name": act_name},
        )
        os.unlink(tmp_path)  # clean up temp file

        # Update MongoDB record with success
        db.documents.update_one(
            {"_id": doc_id},
            {"$set": {"status": "complete", "chunk_count": result["chunk_count"]}},
        )
        return {**result, "title": title}

    except Exception as e:
        db.documents.update_one(
            {"_id": doc_id}, {"$set": {"status": "failed", "error": str(e)}}
        )
        raise
