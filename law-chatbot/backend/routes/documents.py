"""
─────────────────────────────────────────────────────────────────────────────
Phase 2 — Document Management Routes
POST   /api/documents/upload   — upload a PDF
GET    /api/documents          — list all documents
DELETE /api/documents/{id}     — remove a document + its vectors
GET    /api/documents/stats    — Qdrant collection stats
─────────────────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header
from typing import Optional

from backend.deps import get_db
from backend.services import ingestion_service, vector_service, auth_service
from backend.routes.auth import _extract_token

router = APIRouter()


# ── Upload PDF ────────────────────────────────────────────────────────────────
@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = Form(...),
    act_name: str = Form(""),
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        result = await ingestion_service.ingest_uploaded_file(file, title, act_name)
        return {"message": "PDF ingested successfully.", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── List documents ────────────────────────────────────────────────────────────
@router.get("")
def list_documents(authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    db = get_db()
    docs = list(db.documents.find({}, sort=[("uploaded_at", -1)]))
    return [
        {
            "id":          str(d["_id"]),
            "title":       d.get("title", ""),
            "act_name":    d.get("act_name", ""),
            "source_type": d.get("source_type", ""),
            "source_url":  d.get("source_url", ""),
            "status":      d.get("status", ""),
            "chunk_count": d.get("chunk_count", 0),
            "uploaded_at": d.get("uploaded_at", ""),
        }
        for d in docs
    ]


# ── Delete a document ─────────────────────────────────────────────────────────
@router.delete("/{doc_id}")
def delete_document(doc_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    db = get_db()
    # Support both string IDs (PDF uploads) and ObjectId (seeded docs)
    from bson import ObjectId as BsonObjectId
    try:
        oid = BsonObjectId(doc_id)
        doc = db.documents.find_one({"$or": [{"_id": doc_id}, {"_id": oid}]})
    except Exception:
        doc = db.documents.find_one({"_id": doc_id})
        oid = None
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    actual_id = doc["_id"]
    vector_service.delete_document(str(actual_id))
    db.documents.delete_one({"_id": actual_id})
    return {"message": f"Document '{doc.get('title')}' deleted."}


# ── Collection stats ──────────────────────────────────────────────────────────
@router.get("/stats")
def stats(authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    return vector_service.collection_info()


# ── Auth helper ───────────────────────────────────────────────────────────────
def _require_auth(authorization: Optional[str]) -> dict:
    token = _extract_token(authorization)
    try:
        return auth_service.get_current_user(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

