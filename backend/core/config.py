from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str
    claude_model: str = "claude-opus-4-6"
    claude_max_tokens: int = 4096

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "quantdesk_filings"

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "quantdesk"

    # Data sources
    alpha_vantage_api_key: str = ""
    sec_edgar_user_agent: str = "QuantDesk research@example.com"

    # GCP
    gcs_bucket: str = "quantdesk-filings"
    gcp_project: str = ""
    gcp_region: str = "us-central1"

    # API
    api_key: str = ""
    environment: str = "development"
    log_level: str = "INFO"

    # Retrieval
    bm25_top_k: int = 10
    qdrant_top_k: int = 10
    rerank_top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Agent
    max_agent_iterations: int = 10
    agent_timeout_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
