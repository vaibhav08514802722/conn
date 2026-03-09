"""
─────────────────────────────────────────────────────────────────────────────
Phase 2 — Scraper Service
Fetches text from public legal pages, chunks it, and stores in Qdrant.
─────────────────────────────────────────────────────────────────────────────
"""

import uuid
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from langchain.schema import Document

from backend.config import settings
from backend.deps import get_db
from backend.services.vector_service import add_documents
from backend.services.ingestion_service import get_splitter


# ── Generic web scraper ────────────────────────────────────────────────────────
def scrape_url(url: str) -> str:
    """
    Fetch a URL and return clean plain text (strips nav/header/footer).
    """
    headers = {"User-Agent": "Mozilla/5.0 (LawBot research crawler)"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove boilerplate tags
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # Prefer <main> or <article> content; fall back to <body>
    content = soup.find("main") or soup.find("article") or soup.find("body")
    return content.get_text(separator="\n", strip=True) if content else ""


# ── Core ingest-from-URL function ─────────────────────────────────────────────
def ingest_from_url(url: str, act_name: str, title: str = None) -> dict:
    """
    Scrape a legal page, split into chunks, embed, and store in Qdrant.
    Also records the document in MongoDB.
    Returns { doc_id, chunk_count, status }.
    """
    db = get_db()
    doc_id = str(uuid.uuid4())
    title = title or act_name

    # Record as 'processing' in MongoDB
    db.documents.insert_one({
        "_id":         doc_id,
        "title":       title,
        "act_name":    act_name,
        "source_type": "scraped",
        "source_url":  url,
        "status":      "processing",
        "chunk_count": 0,
        "uploaded_at": datetime.utcnow().isoformat(),
    })

    try:
        raw_text = scrape_url(url)
        if not raw_text.strip():
            raise ValueError("No readable text found at the URL.")

        # Wrap in a LangChain Document with metadata
        doc = Document(
            page_content=raw_text,
            metadata={
                "doc_id":         doc_id,
                "document_title": title,
                "act_name":       act_name,
                "source_type":    "scraped",
                "source":         url,
                "source_url":     url,
            },
        )

        # Split and store
        splitter = get_splitter()
        chunks = splitter.split_documents([doc])

        # Propagate metadata to every chunk
        for chunk in chunks:
            chunk.metadata.update(doc.metadata)

        add_documents(chunks)

        db.documents.update_one(
            {"_id": doc_id},
            {"$set": {"status": "complete", "chunk_count": len(chunks)}},
        )
        return {"doc_id": doc_id, "chunk_count": len(chunks), "status": "complete", "title": title}

    except Exception as e:
        db.documents.update_one(
            {"_id": doc_id}, {"$set": {"status": "failed", "error": str(e)}}
        )
        raise

