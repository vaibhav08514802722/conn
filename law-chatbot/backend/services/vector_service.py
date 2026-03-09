"""
─────────────────────────────────────────────────────────────────────────────
Phase 2 — Vector Service
Thin wrapper around Qdrant — search, add docs, delete by doc_id.
─────────────────────────────────────────────────────────────────────────────
"""

from langchain_qdrant import QdrantVectorStore
from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.config import settings
from backend.deps import get_embeddings, get_qdrant_client


def _store() -> QdrantVectorStore:
    """Connect to the existing law_documents collection."""
    return QdrantVectorStore.from_existing_collection(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
        embedding=get_embeddings(),
    )


# ── Search ─────────────────────────────────────────────────────────────────────
def search_laws(query: str, k: int = 6, act_name: str = None) -> list:
    """
    Retrieve the top-k most relevant law chunks for a query.
    Optionally filter by act_name metadata.
    Returns a list of LangChain Document objects.
    """
    try:
        store = _store()
    except Exception:
        return []  # Collection empty or not ready

    try:
        if act_name:
            results = store.similarity_search_with_score(
                query=query,
                k=k,
                filter=Filter(
                    must=[FieldCondition(key="metadata.act_name", match=MatchValue(value=act_name))]
                ),
            )
        else:
            results = store.similarity_search_with_score(query=query, k=k)
    except Exception:
        return []  # Empty collection throws, treat as no results

    # Attach relevance score to each document's metadata
    docs = []
    for doc, score in results:
        doc.metadata["relevance_score"] = round(float(score), 4)
        docs.append(doc)
    return docs


# ── Add documents ──────────────────────────────────────────────────────────────
def add_documents(docs: list) -> int:
    """Batch-upsert LangChain Documents into Qdrant. Returns chunk count."""
    QdrantVectorStore.from_documents(
        documents=docs,
        embedding=get_embeddings(),
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
    )
    return len(docs)


# ── Delete all chunks belonging to a document ─────────────────────────────────
def delete_document(doc_id: str) -> int:
    """Remove all Qdrant points that belong to doc_id. Returns deleted count."""
    client = get_qdrant_client()
    result = client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))]
        ),
    )
    return getattr(result, "deleted", 0)


# ── Collection info ────────────────────────────────────────────────────────────
def collection_info() -> dict:
    """Return basic stats about the law_documents collection."""
    client = get_qdrant_client()
    info = client.get_collection(settings.qdrant_collection)
    return {
        "collection": settings.qdrant_collection,
        "vectors_count": info.vectors_count,
        "points_count": info.points_count,
        "status": str(info.status),
    }

