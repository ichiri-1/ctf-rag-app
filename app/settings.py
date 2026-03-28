from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    app_data_dir: Path = Path("data")
    chroma_persist_dir: Path = Path("data/chroma")
    chroma_collection: str = "documents"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    generation_model: str = "cyberagent/open-calm-small"
    openai_api_key: SecretStr = SecretStr("")
    max_new_tokens: int = 80
    repetition_penalty: float = 1.15
    no_repeat_ngram: int = 3
    retrieval_top_k: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
