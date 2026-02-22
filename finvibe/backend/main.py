"""
FinVibe Backend — FastAPI Application Entrypoint.

Start with: cd finvibe && python -m backend.main
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.agent import router as agent_router
from backend.routes.market import router as market_router
from backend.routes.portfolio import router as portfolio_router
from backend.routes.webhook import router as webhook_router
from backend.routes.auth import router as auth_router
from backend.routes.user_portfolio import router as user_portfolio_router
from backend.routes.ai_brain import router as brain_router

# ─────────────────────── App Factory ────────────────────────────────────────

app = FastAPI(
    title="FinVibe API",
    description="Vibe-Check Portfolio Advisor — Agentic AI for Wealth Management",
    version="0.3.0",
)

# CORS — allow Next.js frontend (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────── Register Routers ───────────────────────────────────

app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(market_router)
app.include_router(portfolio_router)
app.include_router(user_portfolio_router)
app.include_router(brain_router)
app.include_router(webhook_router)


# ─────────────────────── Root Health Check ──────────────────────────────────

@app.get("/")
def root():
    from backend.jobs.scheduler import get_scheduler_status
    return {
        "app": "FinVibe",
        "version": "0.3.0",
        "status": "running",
        "docs": "/docs",
        "scheduler": get_scheduler_status(),
    }


# ─────────────────────── Startup Events ─────────────────────────────────────

@app.on_event("startup")
def on_startup():
    """Initialize infrastructure on server boot."""
    print("\n" + "=" * 60)
    print("  🚀 FinVibe Backend Starting...")
    print("=" * 60)

    # 1. Ensure Qdrant collections exist
    try:
        from backend.deps import ensure_qdrant_collections
        ensure_qdrant_collections()
        print("  ✅ Qdrant collections ready")
    except Exception as e:
        print(f"  ⚠️  Qdrant init skipped (will retry on first use): {e}")

    # 2. Start APScheduler (evaluator every 4h)
    try:
        from backend.jobs.scheduler import start_scheduler
        start_scheduler()
        print("  ✅ Scheduler started (evaluator every 4h)")
    except Exception as e:
        print(f"  ⚠️  Scheduler start skipped: {e}")

    print("  ✅ FastAPI ready at http://localhost:8000")
    print("  📄 Swagger docs at http://localhost:8000/docs")
    print("=" * 60 + "\n")


@app.on_event("shutdown")
def on_shutdown():
    """Gracefully stop background tasks."""
    try:
        from backend.jobs.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


# ─────────────────────── Run ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
