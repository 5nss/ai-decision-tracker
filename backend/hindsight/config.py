"""Runtime configuration, read from environment variables and an optional .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    gemini_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )
    # "auto" uses Gemini when a key is present and falls back to the offline heuristic otherwise.
    provider: Literal["auto", "gemini", "offline"] = Field(
        default="auto", validation_alias="HINDSIGHT_PROVIDER"
    )
    llm_model: str = Field(default="gemini-flash-latest", validation_alias="HINDSIGHT_MODEL")
    embed_model: str = Field(
        default="gemini-embedding-001", validation_alias="HINDSIGHT_EMBED_MODEL"
    )
    embed_dim: int = Field(default=768, validation_alias="HINDSIGHT_EMBED_DIM")
    llm_timeout_s: float = Field(default=30.0, validation_alias="HINDSIGHT_LLM_TIMEOUT_S")
    llm_retries: int = Field(default=2, validation_alias="HINDSIGHT_LLM_RETRIES")

    database_url: str = Field(
        default=f"sqlite:///{(BACKEND_DIR / 'data' / 'hindsight.db').as_posix()}",
        validation_alias="DATABASE_URL",
    )
    frontend_dist: Path = Field(
        default=REPO_DIR / "frontend" / "dist", validation_alias="HINDSIGHT_FRONTEND_DIST"
    )
    seed_demo: bool = Field(default=True, validation_alias="HINDSIGHT_SEED_DEMO")

    @property
    def use_gemini(self) -> bool:
        if self.provider == "offline":
            return False
        if self.provider == "gemini":
            return True
        return bool(self.gemini_api_key and self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
