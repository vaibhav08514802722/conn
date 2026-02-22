"""
Agent routes — invoke the LangGraph, get vibe analysis + strategy + execution.
Includes SSE streaming for real-time frontend updates.
"""
import json as json_lib
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from backend.graph.builder import compile_graph_simple
from backend.services.rag_chat_service import ask_investment_rag_chat, ensure_financial_knowledge_base

router = APIRouter(prefix="/api/agent", tags=["Agent"])


# ─────────────────────── Request / Response Models ──────────────────────────

class AnalyzeRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, example=["AAPL", "MSFT", "TSLA"])
    user_id: str = Field(default="demo", description="User identifier")


class VibeScoreResponse(BaseModel):
    ticker: str
    sentiment_score: float
    anxiety_score: float
    vibe_label: str
    key_driver: str


class TradeResult(BaseModel):
    trade_id: str
    ticker: str
    action: str
    status: str
    message: str
    shares: float = 0
    price: float = 0
    value: float = 0


class AnalyzeResponse(BaseModel):
    status: str
    tickers_analyzed: list[str]
    market_data: dict
    vibe_scores: list[VibeScoreResponse]
    trade_decisions: list[dict]
    execution_results: list[TradeResult]
    alert_sent: bool
    alert_reason: str
    messages: list[dict]
    timestamp: str


class RAGChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    user_id: str = Field(default="demo", description="User identifier")
    top_k: int = Field(default=6, ge=2, le=12)


class Citation(BaseModel):
    id: int
    title: str
    source: str
    url: str
    snippet: str


class RAGChatResponse(BaseModel):
    status: str
    answer: str
    confidence: float
    action_bias: str
    timeframe: str
    risk_notes: list[str]
    followups: list[str]
    citations: list[Citation]
    disclaimer: str
    retrieved_count: int
    memory_count: int


# ─────────────────────── Endpoints ──────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_tickers(request: AnalyzeRequest):
    """
    Run the full pipeline:
    Researcher → Vibe Analyst → Strategist → Executor/Alerter → Reflector
    """
    tickers = [t.strip().upper() for t in request.tickers]

    print(f"\n{'='*60}")
    print(f"[API] /api/agent/analyze — tickers={tickers} user={request.user_id}")
    print(f"{'='*60}")

    try:
        graph = compile_graph_simple()

        initial_state = {
            "messages": [{"role": "user", "content": f"Analyze vibes for: {', '.join(tickers)}"}],
            "user_id": request.user_id,
            "tickers": tickers,
            "market_data": {},
            "news_articles": [],
            "vibe_scores": [],
            "portfolio_snapshot": {},
            "reflection_memories": [],
            "trade_decisions": [],
            "should_alert": False,
            "alert_reason": "",
            "execution_results": [],
            "alert_sent": False,
        }

        final_state = graph.invoke(initial_state)

        # Extract results
        vibe_scores = final_state.get("vibe_scores", [])
        market_data = final_state.get("market_data", {})
        trade_decisions = final_state.get("trade_decisions", [])
        execution_results = final_state.get("execution_results", [])
        alert_sent = final_state.get("alert_sent", False)
        alert_reason = final_state.get("alert_reason", "")

        # Serialize messages
        messages = []
        for msg in final_state.get("messages", []):
            if hasattr(msg, "content"):
                messages.append({"role": getattr(msg, "type", "assistant"), "content": msg.content})
            elif isinstance(msg, dict):
                messages.append(msg)

        return AnalyzeResponse(
            status="success",
            tickers_analyzed=tickers,
            market_data=market_data,
            vibe_scores=[VibeScoreResponse(**vs) for vs in vibe_scores],
            trade_decisions=trade_decisions,
            execution_results=[TradeResult(**_normalize_trade_result(r)) for r in execution_results],
            alert_sent=alert_sent,
            alert_reason=alert_reason,
            messages=messages,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        print(f"[API] Error in /analyze: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=RAGChatResponse)
def rag_chat(request: RAGChatRequest):
    """RAG-based investment chatbot endpoint with citations + persistent memory."""
    try:
        result = ask_investment_rag_chat(
            user_id=request.user_id,
            question=request.question,
            top_k=request.top_k,
        )
        return RAGChatResponse(
            status="ok",
            answer=result.get("answer", ""),
            confidence=float(result.get("confidence", 0.0)),
            action_bias=str(result.get("action_bias", "MIXED")),
            timeframe=str(result.get("timeframe", "medium")),
            risk_notes=result.get("risk_notes", []),
            followups=result.get("followups", []),
            citations=result.get("citations", []),
            disclaimer=str(result.get("disclaimer", "Educational content only. Not financial advice.")),
            retrieved_count=int(result.get("retrieved_count", 0)),
            memory_count=int(result.get("memory_count", 0)),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/seed")
def seed_rag_knowledge():
    """Seed foundational financial knowledge into RAG collection if needed."""
    try:
        result = ensure_financial_knowledge_base()
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_trade_result(r: dict) -> dict:
    """Ensure all TradeResult fields exist with defaults."""
    return {
        "trade_id": r.get("trade_id", ""),
        "ticker": r.get("ticker", ""),
        "action": r.get("action", ""),
        "status": r.get("status", ""),
        "message": r.get("message", ""),
        "shares": r.get("shares", 0),
        "price": r.get("price", 0),
        "value": r.get("value", 0),
    }


# ─────────────────────── Portfolio Endpoint ─────────────────────────────────

@router.get("/portfolio")
def get_portfolio():
    """Get the current shadow portfolio state."""
    try:
        from backend.deps import get_portfolios_col
        doc = get_portfolios_col().find_one(
            {"user_id": "finvibe-agent", "portfolio_type": "shadow"}
        )
        if not doc:
            return {"status": "not_found", "message": "No shadow portfolio. Run seed_portfolio first."}
        doc.pop("_id", None)
        return {"status": "ok", "portfolio": doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades")
def get_trade_history(limit: int = 20):
    """Get recent trade log entries."""
    try:
        from backend.deps import get_trade_logs_col
        trades = list(
            get_trade_logs_col()
            .find({}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return {"status": "ok", "trades": trades, "count": len(trades)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
def get_alerts(limit: int = 10):
    """Get recent anxiety alerts."""
    try:
        from backend.deps import get_db
        alerts = list(
            get_db()["alerts"]
            .find({}, {"_id": 0})
            .sort("triggered_at", -1)
            .limit(limit)
        )
        return {"status": "ok", "alerts": alerts, "count": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def agent_health():
    """Health check for the agent subsystem."""
    return {"status": "ok", "service": "finvibe-agent", "version": "0.3.0"}


# ─────────────────────── SSE Streaming ──────────────────────────────────────

@router.get("/stream")
def stream_analysis(
    tickers: str = Query(..., description="Comma-separated tickers, e.g. AAPL,MSFT"),
    user_id: str = Query(default="demo"),
):
    """
    Stream the full pipeline via Server-Sent Events.
    Each node emits an SSE event as it completes.

    Usage: EventSource('/api/agent/stream?tickers=AAPL,MSFT&user_id=demo')
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No tickers provided")

    def event_generator():
        try:
            graph = compile_graph_simple()

            initial_state = {
                "messages": [{"role": "user", "content": f"Analyze vibes for: {', '.join(ticker_list)}"}],
                "user_id": user_id,
                "tickers": ticker_list,
                "market_data": {},
                "news_articles": [],
                "vibe_scores": [],
                "portfolio_snapshot": {},
                "reflection_memories": [],
                "trade_decisions": [],
                "should_alert": False,
                "alert_reason": "",
                "execution_results": [],
                "alert_sent": False,
            }

            # Stream node-by-node using LangGraph's stream()
            for event in graph.stream(initial_state, stream_mode="updates"):
                for node_name, node_output in event.items():
                    # Serialize the output, handling non-serializable types
                    safe_output = _make_serializable(node_output)
                    sse_data = {
                        "node": node_name,
                        "status": "complete",
                        "data": safe_output,
                    }
                    yield f"data: {json_lib.dumps(sse_data, default=str)}\n\n"

            # Final done event
            yield f"data: {json_lib.dumps({'node': 'pipeline', 'status': 'done'})}\n\n"

        except Exception as e:
            error_event = {"node": "pipeline", "status": "error", "error": str(e)}
            yield f"data: {json_lib.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _make_serializable(obj):
    """Recursively convert non-JSON-serializable objects to strings."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(item) for item in obj]
    elif isinstance(obj, (datetime,)):
        return obj.isoformat()
    elif hasattr(obj, "content"):  # LangChain message objects
        return {"role": getattr(obj, "type", "assistant"), "content": obj.content}
    else:
        try:
            json_lib.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)


# ─────────────────────── Reflections Endpoint ───────────────────────────────

@router.get("/reflections")
def get_reflections(limit: int = 50):
    """
    Fetch all lessons learned from Qdrant reflection_memory collection.
    Returns the agent's self-improvement history.
    """
    try:
        from backend.deps import get_qdrant_client, get_embeddings
        from backend.config import settings

        client = get_qdrant_client()
        collection = settings.qdrant_reflection_collection

        # Scroll through all points in the collection
        results = client.scroll(
            collection_name=collection,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        lessons = []
        if results and results[0]:
            for point in results[0]:
                payload = point.payload or {}
                lessons.append({
                    "id": str(point.id),
                    "lesson": payload.get("page_content", payload.get("text", "")),
                    "ticker": payload.get("metadata", {}).get("ticker", "unknown"),
                    "trade_id": payload.get("metadata", {}).get("trade_id", ""),
                    "created_at": payload.get("metadata", {}).get("created_at", ""),
                })

        return {
            "status": "ok",
            "reflections": lessons,
            "count": len(lessons),
        }

    except Exception as e:
        print(f"[API] Error fetching reflections: {e}")
        return {"status": "ok", "reflections": [], "count": 0}

