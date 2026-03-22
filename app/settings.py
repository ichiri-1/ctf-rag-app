from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_data_dir: Path = Path("data")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    generation_model: str = "cyberagent/open-calm-small"
    max_new_tokens: int = 160
    retrieval_top_k: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
