"""
Centralized settings loaded from .env via pydantic-settings.
Single source of truth for all configuration values.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # --- LLM (Groq / Llama — OpenAI-compatible) ---
    groq_api_key: str = Field("", description="Groq API key (free at console.groq.com)")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Fallback: Gemini (if Groq key not set) ---
    gemini_api_key: str = Field("", description="Gemini API key (fallback)")
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.0-flash"

    # --- MongoDB ---
    mongo_uri: str = "mongodb://admin:admin@localhost:27017"
    mongo_db_name: str = "finvibe_db"

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = Field("", description="Qdrant Cloud API key (leave empty for local)")
    qdrant_market_collection: str = "market_research"
    qdrant_reflection_collection: str = "reflection_memory"

    # --- Neo4j (Mem0 graph store) ---
    neo_uri: str = "bolt://localhost:7687"
    neo_username: str = "neo4j"
    neo_password: str = "finvibe123"

    # --- Deployment ---
    allowed_origins: str = Field(
        "http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated CORS origins",
    )

    # --- External APIs ---
    news_api_key: str = ""
    vapi_api_key: str = ""
    fmp_api_key: str = Field("", description="Financial Modeling Prep key (free at financialmodelingprep.com)")

    # --- App Defaults ---
    shadow_portfolio_cash: float = 1_000_000.0
    anxiety_threshold: float = 7.0
    portfolio_impact_threshold: float = 5.0

    # --- Embedding ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton — import this everywhere
settings = Settings()
