"""
Investment RAG chat service.
- Seeds foundational financial knowledge into Qdrant market_research
- Retrieves relevant chunks for each user question
- Uses active LLM provider for grounded investment answers
- Stores conversation memory per user
"""

from datetime import datetime, timezone
from typing import Any

from langchain_core.documents import Document

from backend.config import settings
from backend.deps import get_llm_client, get_active_model, get_qdrant_client
from backend.services.memory_service import add_user_memory, search_user_memory
from backend.services.vector_service import store_market_documents, search_market_research


def _seed_financial_knowledge_docs() -> list[Document]:
    """Curated starter docs for investment advisory RAG."""
    now = datetime.now(timezone.utc).isoformat()
    docs = [
        {
            "title": "Portfolio Diversification Basics",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.investor.gov/introduction-investing/investing-basics/diversifying-your-investments",
            "content": (
                "Diversification means spreading investments across sectors, asset classes, and geographies to reduce"
                " idiosyncratic risk. Concentrated portfolios can outperform temporarily but carry larger drawdown risk."
                " Position sizing and correlation matter more than just number of holdings."
            ),
        },
        {
            "title": "Risk Management and Position Sizing",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.investopedia.com/articles/trading/09/position-sizing.asp",
            "content": (
                "Position size should be linked to volatility and conviction. A common rule is limiting single-position"
                " exposure and setting maximum portfolio loss tolerance. Risk-adjusted return is better than raw return"
                " for long-term compounding."
            ),
        },
        {
            "title": "Valuation Multiples Overview",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.investopedia.com/terms/p/price-earningsratio.asp",
            "content": (
                "P/E, EV/EBITDA, and price-to-sales must be interpreted relative to sector, growth, and rates."
                " A high multiple can be justified by durable growth and margins; a low multiple can indicate value"
                " or structural weakness."
            ),
        },
        {
            "title": "Earnings Quality Checklist",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.sec.gov/edgar/searchedgar/companysearch",
            "content": (
                "Review revenue growth quality, margin trend, operating cash flow, guidance changes, and one-off items."
                " Strong earnings quality typically includes stable margin expansion, healthy cash conversion, and"
                " consistent guidance execution."
            ),
        },
        {
            "title": "Macro Sensitivity for Stocks",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.federalreserve.gov/monetarypolicy.htm",
            "content": (
                "Growth and duration-sensitive equities are more affected by interest-rate expectations."
                " Financials can benefit from higher rates up to a point; defensives tend to outperform in risk-off"
                " periods. Inflation, rates, and liquidity regimes influence market leadership."
            ),
        },
        {
            "title": "Technical Momentum and Risk",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.investopedia.com/terms/m/momentum.asp",
            "content": (
                "Momentum works best with trend confirmation, rising relative strength, and liquidity support."
                " Late-stage momentum with weak breadth increases reversal risk. Use stop-loss discipline and avoid"
                " averaging down without thesis confirmation."
            ),
        },
        {
            "title": "Behavioral Biases in Investing",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.cfainstitute.org/en/research/foundation/2009/behavioural-finance-and-investment-process",
            "content": (
                "Common biases include overconfidence, recency bias, and loss aversion."
                " Structured process, pre-defined risk limits, and post-trade reviews reduce emotional decision-making."
            ),
        },
        {
            "title": "When to Hold vs Sell",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.investopedia.com/articles/stocks/08/sell-stock.asp",
            "content": (
                "Consider selling when thesis breaks, valuation becomes extreme versus fundamentals,"
                " or risk budget is breached. Holding is justified when thesis remains intact, execution is strong,"
                " and risk-reward remains favorable."
            ),
        },
        {
            "title": "ETF vs Single-Stock Exposure",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.investor.gov/introduction-investing/investing-basics/investment-products/exchange-traded-funds-etfs",
            "content": (
                "ETFs reduce single-company risk and are suitable for core exposure."
                " Single stocks can be used as satellite positions where conviction and edge are high."
                " Blending core ETFs with selective single-stock ideas improves robustness."
            ),
        },
        {
            "title": "AI/Tech Stock Due Diligence",
            "source": "FinVibe Knowledge Base",
            "url": "https://www.sec.gov/edgar/searchedgar/companysearch",
            "content": (
                "For AI/tech stocks, monitor data-center demand, gross margin trend, product roadmap,"
                " competitive moat, and capex intensity. Revenue concentration and customer churn are key risks."
            ),
        },
    ]

    return [
        Document(
            page_content=d["content"],
            metadata={
                "title": d["title"],
                "source": d["source"],
                "url": d["url"],
                "category": "financial_education",
                "created_at": now,
            },
        )
        for d in docs
    ]


def ensure_financial_knowledge_base(min_docs: int = 8) -> dict[str, Any]:
    """Seed starter financial corpus into market_research if collection is sparse."""
    try:
        client = get_qdrant_client()
        count_info = client.count(collection_name=settings.qdrant_market_collection)
        existing = int(getattr(count_info, "count", 0) or 0)

        if existing >= min_docs:
            return {"seeded": False, "existing_docs": existing, "added_docs": 0}

        docs = _seed_financial_knowledge_docs()
        store_market_documents(docs)
        return {
            "seeded": True,
            "existing_docs": existing,
            "added_docs": len(docs),
        }
    except Exception as e:
        return {
            "seeded": False,
            "existing_docs": 0,
            "added_docs": 0,
            "error": str(e),
        }


def _build_system_prompt() -> str:
    return (
        "You are FinVibe Investment Advisor, an expert in stocks and portfolio strategy. "
        "Use ONLY retrieved context when claiming facts. If evidence is weak, say uncertainty clearly. "
        "Provide practical, risk-aware, concise guidance. "
        "When user asks for buy/sell ideas, provide: thesis, risks, position sizing hint, and timeframe. "
        "Never guarantee returns."
    )


def _format_context_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return "No retrieved context."

    lines = []
    for idx, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata") or {}
        title = meta.get("title", f"Source {idx}")
        source = meta.get("source", "Unknown")
        content = (chunk.get("content") or "").strip()
        lines.append(f"[{idx}] {title} ({source})\n{content}")
    return "\n\n".join(lines)


def ask_investment_rag_chat(user_id: str, question: str, top_k: int = 6) -> dict:
    """Retrieve + generate grounded investment answer with citations and memory."""
    if not question or not question.strip():
        return {
            "answer": "Please ask a specific investment question.",
            "citations": [],
            "confidence": 0.0,
            "disclaimer": "Educational content only. Not financial advice.",
        }

    seed_info = ensure_financial_knowledge_base()

    user_memories = search_user_memory(user_id, f"investment preferences context {question}")
    retrieved = search_market_research(question, k=top_k)

    context_block = _format_context_chunks(retrieved)
    memory_block = "\n".join([f"- {m}" for m in user_memories[:5]]) if user_memories else "None"

    prompt = f"""
Question:
{question}

User memory:
{memory_block}

Retrieved financial context:
{context_block}

Return JSON only with schema:
{{
  "answer": "clear answer in plain English",
  "confidence": 0.0,
  "action_bias": "BUY|HOLD|SELL|MIXED",
  "timeframe": "short|medium|long",
  "risk_notes": ["risk 1", "risk 2"],
  "followups": ["question 1", "question 2"]
}}
"""

    try:
        client = get_llm_client()
        resp = client.chat.completions.create(
            model=get_active_model(),
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
            max_tokens=900,
        )

        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            parsed = __import__("json").loads(raw)
        except Exception:
            parsed = {
                "answer": raw or "I could not generate a reliable answer.",
                "confidence": 0.35,
                "action_bias": "MIXED",
                "timeframe": "medium",
                "risk_notes": ["Model output parsing was not exact."],
                "followups": [],
            }

        citations = []
        for i, chunk in enumerate(retrieved, 1):
            meta = chunk.get("metadata") or {}
            citations.append({
                "id": i,
                "title": meta.get("title", f"Source {i}"),
                "source": meta.get("source", "Unknown"),
                "url": meta.get("url", ""),
                "snippet": (chunk.get("content") or "")[:240],
            })

        answer_text = parsed.get("answer", "No answer generated.")
        confidence = parsed.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except Exception:
            confidence = 0.0

        add_user_memory(
            user_id,
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer_text},
            ],
        )

        return {
            "answer": answer_text,
            "confidence": round(confidence, 3),
            "action_bias": str(parsed.get("action_bias", "MIXED")).upper(),
            "timeframe": str(parsed.get("timeframe", "medium")).lower(),
            "risk_notes": parsed.get("risk_notes", []),
            "followups": parsed.get("followups", []),
            "citations": citations,
            "disclaimer": "Educational content only. Not financial advice.",
            "seed_info": seed_info,
            "retrieved_count": len(retrieved),
            "memory_count": len(user_memories),
        }

    except Exception as e:
        return {
            "answer": "I could not process this question right now. Please try again.",
            "confidence": 0.0,
            "action_bias": "MIXED",
            "timeframe": "medium",
            "risk_notes": [str(e)],
            "followups": [],
            "citations": [],
            "disclaimer": "Educational content only. Not financial advice.",
            "seed_info": seed_info,
            "retrieved_count": len(retrieved),
            "memory_count": len(user_memories),
        }
