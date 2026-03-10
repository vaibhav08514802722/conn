"""
─────────────────────────────────────────────────────────────────────────────
Phase 5 — FastAPI Application Entry Point
─────────────────────────────────────────────────────────────────────────────
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings

app = FastAPI(
    title="LexBot — Law Chatbot API",
    description="RAG-based legal assistant powered by Groq / Llama 3.3 + Qdrant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow Next.js dev server + production deployment ──────────────
allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup: verify all infrastructure connections ───────────────────────────
@app.on_event("startup")
async def startup():
    print("\n── LexBot API starting ──────────────────────────────────────")
    from backend.deps import get_qdrant_client, get_mongo_client, get_embeddings

    ok, fail = [], []

    for label, fn in [
        ("Qdrant", get_qdrant_client),
        ("MongoDB", get_mongo_client),
        ("Embeddings", get_embeddings),
    ]:
        try:
            fn()
            ok.append(label)
        except Exception as e:
            fail.append(f"{label}: {e}")

    for svc in ok:
        print(f"  ✓ {svc}")
    for err in fail:
        print(f"  ✗ {err}")

    if fail:
        print("  ⚠ Some services unavailable — check docker-compose is running.")
    else:
        print("  All services ready.")
    print("─────────────────────────────────────────────────────────────\n")


# ── Register all routers ──────────────────────────────────────────────────────
from backend.routes import auth, chat, documents, scraper  # noqa: E402

app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["Chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(scraper.router,   prefix="/api/scraper",   tags=["Scraper"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "lexbot-api", "version": "1.0.0"}


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
