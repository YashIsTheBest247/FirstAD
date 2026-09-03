"""Runtime configuration.

Greenlight runs against Gemini either through a plain API key (fastest to get
going) or through Vertex AI on a Google Cloud project. Both paths are wired,
and the ADK picks between them from these environment variables.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Google Cloud AI -------------------------------------------------
    google_api_key: str = ""
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"

    # Both tiers default to flash, which is what the Gemini API free tier
    # actually gives you useful quota on. Set MODEL_REASONING=gemini-2.5-pro if
    # you have paid quota: it measurably improves the scheduling, compliance and
    # budget stages, which are the ones making consequential judgements.
    model_reasoning: str = "gemini-2.5-flash"
    model_fast: str = "gemini-2.5-flash"

    # Free tiers are rate limited per minute, not just per day, so the pipeline
    # caps how many agents may be in flight at once rather than fanning out as
    # wide as the work allows.
    max_agent_concurrency: int = 3
    agent_retry_attempts: int = 4

    # --- Partner track: Parallel -----------------------------------------
    parallel_api_key: str = ""
    parallel_search_mode: str = "advanced"
    parallel_max_concurrency: int = 3
    # Every researched entity is a billable search, so the default keeps a full
    # run cheap. Raise it when you want feature-length coverage.
    max_researched_entities: int = 12

    # --- App -------------------------------------------------------------
    cors_origins: str = "http://localhost:3000"
    run_store_dir: str = ".runs"
    max_upload_mb: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_gemini(self) -> bool:
        if self.google_genai_use_vertexai:
            return bool(self.google_cloud_project)
        return bool(self.google_api_key)

    @property
    def has_parallel(self) -> bool:
        return bool(self.parallel_api_key)

    def export_to_env(self) -> None:
        """The ADK reads Gemini credentials from the process environment."""
        if self.google_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", self.google_api_key)
        os.environ.setdefault(
            "GOOGLE_GENAI_USE_VERTEXAI", "TRUE" if self.google_genai_use_vertexai else "FALSE"
        )
        if self.google_cloud_project:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self.google_cloud_project)
        if self.google_cloud_location:
            os.environ.setdefault("GOOGLE_CLOUD_LOCATION", self.google_cloud_location)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.export_to_env()
    return s
