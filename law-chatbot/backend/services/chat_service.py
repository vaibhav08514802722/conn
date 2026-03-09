"""
─────────────────────────────────────────────────────────────────────────────
Phase 3 — Chat Service  (RAG + memory + structured response)
Flow: retrieve law chunks → build prompt → call Groq → parse JSON → save
─────────────────────────────────────────────────────────────────────────────
"""

import json

from backend.config import settings
from backend.deps import get_llm_client
from backend.services.vector_service import search_laws
from backend.services import memory_service

# ── System prompt (Phase 7 — legal prompt engineering) ───────────────────────
SYSTEM_PROMPT = """You are LexBot, a friendly and knowledgeable legal assistant.
You help users understand laws, regulations, and legal procedures in plain language.

RULES:
1. Always cite the exact section/article number and act name from the context provided.
2. Explain legal concepts in simple, easy-to-understand language — avoid heavy jargon.
3. If the retrieved context does not clearly answer the question, say so honestly.
4. Always end with: responses are informational only, not legal advice.
5. Suggest 2-3 related follow-up questions the user might find useful.

RESPONSE FORMAT — reply ONLY with valid JSON (no extra text):
{
  "answer": "<clear plain-language explanation>",
  "citations": [
    {
      "section": "<e.g. Section 302>",
      "act": "<e.g. Indian Penal Code, 1860>",
      "chapter": "<chapter name or null>",
      "page": <page number or null>,
      "source": "<document title or URL>",
      "relevance_score": <0.0-1.0>
    }
  ],
  "confidence": <0.0-1.0>,
  "disclaimer": "This is informational only and does not constitute legal advice. Consult a qualified lawyer for your specific situation.",
  "related_questions": ["question 1", "question 2", "question 3"]
}"""


# ── Main ask function ─────────────────────────────────────────────────────────
def ask(user_id: str, question: str, session_id: str = None) -> dict:
    """
    RAG-based legal Q&A.
    1. Retrieve relevant law chunks from Qdrant
    2. Load conversation history from MongoDB
    3. Build messages for Groq
    4. Parse structured JSON response
    5. Save turn to MongoDB
    Returns the full response dict matching ChatResponse schema.
    """

    # ── Step 1: Create/validate session ──────────────────────────────────────
    if not session_id:
        session_id = memory_service.create_session(user_id)
        memory_service.auto_title_session(session_id, question)

    # ── Step 2: Retrieve law chunks ───────────────────────────────────────────
    retrieved_docs = search_laws(question, k=settings.retrieval_top_k)

    # Build context string from retrieved chunks
    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        meta = doc.metadata
        context_parts.append(
            f"[{i}] Source: {meta.get('document_title', 'Unknown')} — "
            f"{meta.get('act_name', '')} | Page {meta.get('page', 'N/A')}\n"
            f"{doc.page_content}"
        )
    context = "\n\n".join(context_parts) if context_parts else "No relevant law documents found."

    # ── Step 3: Load conversation history ────────────────────────────────────
    history = memory_service.get_history(session_id, limit=10)

    # ── Step 4: Build message list for Groq ──────────────────────────────────
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add history (older messages give LLM conversation context)
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Current user question with retrieved context
    user_message = (
        f"RETRIEVED LAW CONTEXT:\n{context}\n\n"
        f"USER QUESTION: {question}"
    )
    messages.append({"role": "user", "content": user_message})

    # ── Step 5: Call Groq ─────────────────────────────────────────────────────
    llm = get_llm_client()
    completion = llm.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
    raw_reply = completion.choices[0].message.content.strip()

    # ── Step 6: Parse JSON response ───────────────────────────────────────────
    response = _parse_response(raw_reply, retrieved_docs, session_id)

    # ── Step 7: Save both turns to MongoDB ────────────────────────────────────
    memory_service.save_message(session_id, "user", question)
    memory_service.save_message(
        session_id, "assistant", response["answer"], response["citations"]
    )

    return response


# ── JSON parser with graceful fallback ────────────────────────────────────────
def _parse_response(raw: str, retrieved_docs: list, session_id: str) -> dict:
    """
    Try to parse the LLM's JSON reply.
    If it fails, build a sensible fallback from the retrieved chunks.
    """
    # Strip accidental markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])

    try:
        data = json.loads(cleaned)

        # Ensure all expected fields exist
        return {
            "answer":           data.get("answer", cleaned),
            "citations":        data.get("citations", []),
            "confidence":       float(data.get("confidence", 0.7)),
            "disclaimer":       data.get(
                "disclaimer",
                "This is informational only. Consult a qualified lawyer.",
            ),
            "related_questions": data.get("related_questions", []),
            "session_id":       session_id,
        }

    except json.JSONDecodeError:
        # Fallback: return raw text + auto-build citations from retrieved docs
        citations = [
            {
                "section":         doc.metadata.get("section", ""),
                "act":             doc.metadata.get("act_name", ""),
                "chapter":         doc.metadata.get("chapter", None),
                "page":            doc.metadata.get("page", None),
                "source":          doc.metadata.get("source", ""),
                "relevance_score": doc.metadata.get("relevance_score", 0.5),
            }
            for doc in retrieved_docs
        ]
        return {
            "answer":           raw,
            "citations":        citations,
            "confidence":       0.6,
            "disclaimer":       "This is informational only. Consult a qualified lawyer.",
            "related_questions": [],
            "session_id":       session_id,
        }

