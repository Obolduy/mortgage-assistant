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


settings = Settings()
