"""
─────────────────────────────────────────────────────────────────────────────
Law Chatbot — Document Schemas
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class DocumentMeta(BaseModel):
    id: str
    title: str
    source_type: str         # "pdf" | "scraped"
    source_url: Optional[str] = None
    act_name: Optional[str] = None
    chunk_count: int = 0
    status: str = "pending"  # pending | processing | complete | failed
    uploaded_at: str


class IngestPDFRequest(BaseModel):
    title: str = Field(..., min_length=1)
    act_name: Optional[str] = None


class ScrapeRequest(BaseModel):
    url: str = Field(..., description="Public legal page URL to scrape")
    act_name: str = Field(..., description="Human-readable name for this act/document")
    title: Optional[str] = None
