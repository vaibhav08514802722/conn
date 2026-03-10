"""
─────────────────────────────────────────────────────────────────────────────
Law Chatbot — Application Configuration
Loaded from environment variables / .env file via pydantic-settings.
─────────────────────────────────────────────────────────────────────────────
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048

    # ── Vector store ─────────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""  # For Qdrant Cloud (leave empty for local)
    qdrant_collection: str = "law_documents"

    # ── Database ──────────────────────────────────────────────────────────────
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "lawchatbot"

    # ── Auth ──────────────────────────────────────────────────────────────────
    jwt_secret: str = "change_this_to_a_long_random_string_in_production"

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── Ingestion ────────────────────────────────────────────────────────────
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 6

    # ── Redis / job queue ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"
    # ── CORS ─────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000"  # Comma-separated list
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Convenience alias so other modules can do: from backend.config import settings
settings = get_settings()
