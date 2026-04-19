from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "Market Intelligence AI"
    app_env: str = "dev"
    api_prefix: str = "/api"

    app_secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = "postgresql+psycopg2://market:market@localhost:5432/market_intel"
    redis_url: str = "redis://localhost:6379/0"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "market_chunks"
    vector_size: int = 768

    opensearch_url: str = "http://localhost:9200"
    opensearch_user: str = ""
    opensearch_password: str = ""
    opensearch_index: str = "market_chunks"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_raw: str = "market-intel-raw"

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_chat_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "models/embedding-001"

    retrieval_top_k: int = 40
    final_context_k: int = 10

    alert_importance_high: float = 0.75
    alert_confidence_high: float = 0.70
    alert_importance_medium: float = 0.60
    alert_confidence_medium: float = 0.55

    scheduler_interval_minutes: int = 30


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
