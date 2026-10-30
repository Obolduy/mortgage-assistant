from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    db_pool_min: int = 1
    db_pool_max: int = 10

    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = "gemma-4-e4b-it"
    llm_timeout_s: float = 120.0
    llm_max_retries: int = 3
    agent_max_turns: int = 6
    agent_timeout_s: float = 300.0
    answer_max_attempts: int = 2
    confidence_threshold: float = 0.6
    llm_prices: dict[str, tuple[int, int]] = {}
    context_max_chars: int = 3000

    embed_model: str = "intfloat/multilingual-e5-base"
    embed_query_prefix: str = "query: "
    embed_doc_template: str = "passage: {text}"
    embed_batch: int = 32
    search_top_k: int = 5
    search_threshold: float = 0.81
    upload_max_bytes: int = 10_000_000

    temporal_host: str = "localhost:7233"
    temporal_task_queue: str = "mortgage"
    temporal_activity_threads: int = 4


settings = Settings()
