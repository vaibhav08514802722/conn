"""
Shared singleton dependencies: LLM client, MongoDB, Qdrant, Embeddings, Mem0.

ALL connections are LAZY — nothing connects at import time.
Call the getter functions (get_llm_client(), get_db(), etc.) when you need them.
This ensures modules can be imported even when Docker services are not running.
"""
from backend.config import settings


# ────────────────────────── Cached singletons ───────────────────────────────
_llm_client = None
_mongo_client = None
_db = None
_qdrant_client = None
_embeddings = None
_memory = None

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 produces 384-dim vectors


# ────────────────────────── LLM Client (Groq/Llama or Gemini via OpenAI SDK) ─

def get_llm_client():
    """Lazy-init OpenAI client — uses Groq (Llama) if key set, else falls back to Gemini."""
    global _llm_client
    if _llm_client is None:
        from openai import OpenAI
        if settings.groq_api_key:
            _llm_client = OpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
            )
        else:
            _llm_client = OpenAI(
                api_key=settings.gemini_api_key,
                base_url=settings.gemini_base_url,
            )
    return _llm_client


def get_active_model() -> str:
    """Return whichever model name is active."""
    if settings.groq_api_key:
        return settings.groq_model
    return settings.gemini_model


# ────────────────────────── MongoDB ─────────────────────────────────────────

def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        from pymongo import MongoClient
        _mongo_client = MongoClient(settings.mongo_uri)
    return _mongo_client


def get_db():
    global _db
    if _db is None:
        _db = get_mongo_client()[settings.mongo_db_name]
    return _db


def get_portfolios_col():
    return get_db()["portfolios"]


def get_trade_logs_col():
    return get_db()["trade_logs"]


def get_market_sentiments_col():
    return get_db()["market_sentiments"]


# ────────────────────────── Qdrant ──────────────────────────────────────────

def get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(url=settings.qdrant_url)
    return _qdrant_client


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return _embeddings


def ensure_qdrant_collections():
    """Create Qdrant collections if they don't exist yet."""
    from qdrant_client.models import Distance, VectorParams
    client = get_qdrant_client()
    for col_name in [settings.qdrant_market_collection, settings.qdrant_reflection_collection]:
        existing = [c.name for c in client.get_collections().collections]
        if col_name not in existing:
            client.create_collection(
                collection_name=col_name,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            print(f"[Qdrant] Created collection: {col_name}")


def get_vector_store(collection_name: str):
    """Get a LangChain QdrantVectorStore bound to an existing collection."""
    from langchain_qdrant import QdrantVectorStore
    return QdrantVectorStore.from_existing_collection(
        embedding=get_embeddings(),
        url=settings.qdrant_url,
        collection_name=collection_name,
    )


# ────────────────────────── Mem0 (Episodic Memory) ──────────────────────────

def get_memory():
    """Lazy-init Mem0 memory (requires Neo4j + Qdrant running)."""
    global _memory
    if _memory is None:
        from mem0 import Memory

        # Use Groq/Llama when key is available, else fall back to Gemini
        if settings.groq_api_key:
            llm_config = {
                "provider": "groq",
                "config": {
                    "api_key": settings.groq_api_key,
                    "model": settings.groq_model,
                },
            }
        else:
            llm_config = {
                "provider": "gemini",
                "config": {
                    "api_key": settings.gemini_api_key,
                    "model": settings.gemini_model,
                },
            }

        mem0_config = {
            "version": "v1.1",
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": settings.embedding_model,
                    "embedding_dims": EMBEDDING_DIM,
                },
            },
            "llm": llm_config,
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": settings.neo_uri,
                    "username": settings.neo_username,
                    "password": settings.neo_password,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": "localhost",
                    "port": 6333,
                    "embedding_model_dims": EMBEDDING_DIM,
                },
            },
        }
        _memory = Memory.from_config(mem0_config)
    return _memory
