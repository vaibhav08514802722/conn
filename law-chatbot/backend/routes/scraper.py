"""
─────────────────────────────────────────────────────────────────────────────
Phase 2 — Scraper Routes
POST /api/scraper/scrape — scrape a legal URL and ingest it
─────────────────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from backend.schemas.document import ScrapeRequest
from backend.services import scraper_service, auth_service
from backend.routes.auth import _extract_token

router = APIRouter()


@router.post("/scrape")
def scrape(body: ScrapeRequest, authorization: Optional[str] = Header(None)):
    """
    Scrape a public legal URL (e.g. IndiaCode, LII) and ingest it into Qdrant.
    Requires authentication.
    """
    _require_auth(authorization)
    try:
        result = scraper_service.ingest_from_url(
            url=body.url,
            act_name=body.act_name,
            title=body.title,
        )
        return {"message": "Page scraped and ingested successfully.", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Auth helper ───────────────────────────────────────────────────────────────
def _require_auth(authorization: Optional[str]) -> dict:
    token = _extract_token(authorization)
    try:
        return auth_service.get_current_user(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

