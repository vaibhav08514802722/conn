"""
Vector store abstraction — wraps Qdrant for both market_research and reflection_memory.
Separates read/write logic so we can swap to Pinecone later via config.
"""
from langchain_core.documents import Document

from backend.config import settings
from backend.deps import get_embeddings, get_vector_store, ensure_qdrant_collections


def search_reflection_memory(query: str, k: int = 3) -> list[str]:
    """
    Search the reflection_memory collection for past lessons relevant to a query.
    Returns a list of lesson strings.
    """
    try:
        ensure_qdrant_collections()
        vs = get_vector_store(settings.qdrant_reflection_collection)
        results = vs.similarity_search(query=query, k=k)
        return [doc.page_content for doc in results]
    except Exception as e:
        print(f"[VectorService] Reflection search failed: {e}")
        return []


def store_reflection_lesson(lesson: str, metadata: dict) -> None:
    """
    Embed and store a single lesson-learned into the reflection_memory collection.
    metadata should include: {ticker, trade_id, failure_type, created_at}
    """
    try:
        ensure_qdrant_collections()
        vs = get_vector_store(settings.qdrant_reflection_collection)
        doc = Document(page_content=lesson, metadata=metadata)
        vs.add_documents([doc])
        print(f"[VectorService] Stored reflection: {lesson[:80]}...")
    except Exception as e:
        print(f"[VectorService] Failed to store reflection: {e}")


def search_market_research(query: str, k: int = 5) -> list[dict]:
    """
    Search the market_research collection for relevant news/analysis chunks.
    Returns list of {content, metadata} dicts.
    """
    try:
        ensure_qdrant_collections()
        vs = get_vector_store(settings.qdrant_market_collection)
        results = vs.similarity_search(query=query, k=k)
        return [
            {"content": doc.page_content, "metadata": doc.metadata}
            for doc in results
        ]
    except Exception as e:
        print(f"[VectorService] Market search failed: {e}")
        return []


def store_market_documents(documents: list[Document]) -> None:
    """
    Embed and store documents into the market_research collection.
    Used by the indexing pipeline to ingest news articles.
    """
    try:
        ensure_qdrant_collections()
        vs = get_vector_store(settings.qdrant_market_collection)
        vs.add_documents(documents)
        print(f"[VectorService] Stored {len(documents)} market docs")
    except Exception as e:
        print(f"[VectorService] Failed to store market docs: {e}")
