"""
─────────────────────────────────────────────────────────────────────────────
Law Chatbot — Lazy Singleton Dependencies
All expensive resources (LLM client, Qdrant, MongoDB, embeddings) are
initialized once on first access and cached for the lifetime of the process.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from typing import Optional

from backend.config import settings

# ── Module-level caches ───────────────────────────────────────────────────────
_llm_client = None
_qdrant_client = None
_mongo_client = None
_embeddings = None
_vector_store = None


# ─────────────────────────────────────────────────────────────────────────────
# LLM Client — Groq via OpenAI SDK compatibility layer
# ─────────────────────────────────────────────────────────────────────────────

def get_llm_client():
    """Return the Groq LLM client (official groq SDK)."""
    global _llm_client
    if _llm_client is None:
        from groq import Groq

        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file or environment variables."
            )

        _llm_client = Groq(api_key=settings.groq_api_key)
        print("✓ LLM client initialised (Groq / Llama 3.3)")

    return _llm_client


# ─────────────────────────────────────────────────────────────────────────────
# Qdrant Client + Collection Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def get_qdrant_client():
    """
    Return the Qdrant client and ensure the law_documents collection exists.
    Creates the collection with cosine-distance 384-dim vectors if absent.
    Supports both local Docker and Qdrant Cloud deployments.
    """
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        # Support both local (Docker) and cloud (Qdrant Cloud) deployments
        if settings.qdrant_api_key:
            _qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
            )
            print("✓ Qdrant Cloud connected")
        else:
            _qdrant_client = QdrantClient(url=settings.qdrant_url)
            print("✓ Qdrant local connected")

        # Auto-create collection if it doesn't exist yet
        existing = [c.name for c in _qdrant_client.get_collections().collections]
        if settings.qdrant_collection not in existing:
            _qdrant_client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print(f"✓ Qdrant collection '{settings.qdrant_collection}' created")
        else:
            print(f"✓ Qdrant collection '{settings.qdrant_collection}' ready")

    return _qdrant_client


# ─────────────────────────────────────────────────────────────────────────────
# MongoDB Client
# ─────────────────────────────────────────────────────────────────────────────

def get_mongo_client():
    """Return the MongoDB client (connects to the lawchatbot database)."""
    global _mongo_client
    if _mongo_client is None:
        from pymongo import MongoClient

        _mongo_client = MongoClient(settings.mongo_uri)
        # Verify connection
        _mongo_client.admin.command("ping")
        print(f"✓ MongoDB connected — db: {settings.mongo_db}")

    return _mongo_client


def get_db():
    """Return the lawchatbot MongoDB database object."""
    return get_mongo_client()[settings.mongo_db]


# ─────────────────────────────────────────────────────────────────────────────
# HuggingFace Embeddings (runs locally — no API key needed)
# ─────────────────────────────────────────────────────────────────────────────

def get_embeddings():
    """
    Return a singleton HuggingFace embeddings object.
    Uses all-MiniLM-L6-v2 (384-dim) — same as every other project in this
    workspace.  The model is downloaded once and cached by sentence-transformers.
    """
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        print(f"✓ Embeddings loaded — model: {settings.embedding_model}")

    return _embeddings


# ─────────────────────────────────────────────────────────────────────────────
# LangChain Qdrant Vector Store
# ─────────────────────────────────────────────────────────────────────────────

def get_vector_store():
    """
    Return a LangChain QdrantVectorStore wrapping the law_documents collection.
    Suitable for similarity_search() calls in the chat service.
    """
    global _vector_store
    if _vector_store is None:
        from langchain_qdrant import QdrantVectorStore

        # Ensure the collection exists before connecting
        get_qdrant_client()

        _vector_store = QdrantVectorStore.from_existing_collection(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            embedding=get_embeddings(),
        )
        print(f"✓ Vector store connected — collection: {settings.qdrant_collection}")

    return _vector_store


# ─────────────────────────────────────────────────────────────────────────────
# Redis / Valkey Client (for background ingestion job queue)
# ─────────────────────────────────────────────────────────────────────────────

_redis_client = None


def get_redis():
    """Return a Redis/Valkey client for the RQ job queue."""
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.from_url(settings.redis_url)
        _redis_client.ping()
        print(f"✓ Redis/Valkey connected — {settings.redis_url}")

    return _redis_client
