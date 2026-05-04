from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    data_dir: Path = Path("data")
    openai_api_key: SecretStr = SecretStr("")
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    retrieval_top_k: int = 5
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    qdrant_url: str = ""
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "writeups"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def writeups_dir(self) -> Path:
        return self.data_dir / "writeups"

    @property
    def meta_dir(self) -> Path:
        return self.data_dir / "meta"


settings = Settings()
