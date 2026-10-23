from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "dayan"
    app_env: str = "development"
    debug: bool = True

    # ---- LLM ----
    llm_provider: Literal["lm_studio", "openai", "ollama"] = "lm_studio"
    model_url: str = "http://localhost:1234"
    model_name: str = "local-model"
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1)
    system_prompt_path: str = "ai_model/prompts/system.json"
    llm_disable_thinking: bool = True
    llm_context_max_chars: int = Field(default=3500, ge=500)
    llm_timeout_seconds: float = Field(default=90.0, ge=5.0, le=300.0)
    system_prompt_max_chars: int = Field(default=2500, ge=200)
    page_text_max_chars: int = Field(default=900, ge=100)

    # ---- RAG / Embedding ----
    rag_enabled: bool = True
    rag_top_k: int = Field(default=3, ge=1, le=12)
    embedding_model_name: str = "intfloat/multilingual-e5-small"
    embedding_device: str | None = None
    embedding_batch_size: int = Field(default=8, ge=1, le=64)
    embedding_cpu_threads: int = Field(default=4, ge=1, le=32)
    qdrant_url: str = ""  # مثلاً http://127.0.0.1:6333 — اگر خالی باشد از path محلی
    qdrant_path: str = "./data/qdrant"
    qdrant_collection: str = "documents"

    # ---- دیتابیس اصلی ----
    database_url: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "dayan_db"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    db_fallback_sqlite: bool = True
    db_echo: bool = False

    # ---- Mongo ----
    mongo_uri: str = "mongodb://127.0.0.1:27017"
    mongo_db: str = "dayan_logs"
    memory_max_turns: int = 20

    # ---- Redis ----
    redis_url: str = "redis://127.0.0.1:6379/0"

    # ---- JWT ----
    jwt_secret: str = "change-me-in-production-dayan"
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = Field(default=120, ge=1)
    jwt_refresh_days: int = Field(default=14, ge=1)

    # ---- Rate limit ("تعداد/ثانیه") ----
    rate_limit_enabled: bool = True
    rate_limit_login: str = "10/300"
    rate_limit_register: str = "5/3600"
    rate_limit_chat: str = "30/60"
    rate_limit_default: str = "120/60"

    # ---- CORS / مسیرها ----
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:4000,http://127.0.0.1:4000"
    )
    data_dir: str = "./data"
    uploads_dir: str = "./data/uploads"
    cms_path: str = "./data/cms/site.json"

    # ---- Temporal ----
    temporal_host: str = "127.0.0.1:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "dayan-tasks"

    # ---- Chunking ----
    chunk_size_words: int = 220
    chunk_overlap_words: int = 30

    # ---- Web fallback ----
    web_crawl_enabled: bool = False
    web_base_url: str = ""
    web_max_pages: int = Field(default=10, ge=1, le=100)
    web_timeout_seconds: float = Field(default=15.0, gt=0)
    web_min_doc_score: float = Field(default=0.35, ge=0.0, le=1.0)
    web_user_agent: str = "DayanBot/1.0 (+local; research)"

    search_engine: Literal["site_crawl", "duckduckgo", "bing", "google", "none"] = "none"
    search_api_key: str = ""
    search_cx: str = ""
    search_max_results: int = Field(default=5, ge=1, le=20)
    search_site_filter: str = ""
    search_fetch_pages: bool = True

    # ---- آپلود ----
    upload_max_mb: int = Field(default=10, ge=1, le=100)

    @field_validator("embedding_device", mode="before")
    @classmethod
    def empty_device_to_none(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator(
        "web_base_url",
        "search_api_key",
        "search_cx",
        "search_site_filter",
        "database_url",
        "qdrant_url",
        mode="before",
    )
    @classmethod
    def strip_optional_str(cls, v: object) -> object:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("search_engine", mode="before")
    @classmethod
    def normalize_search_engine(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @property
    def system_prompt_file(self) -> Path:
        path = Path(self.system_prompt_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def postgres_dsn(self) -> str:
        """DSN اصلی برای SQLAlchemy async."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sqlite_dsn(self) -> str:
        db_file = (self.data_root / "dayan.db").as_posix()
        return f"sqlite+aiosqlite:///{db_file}"

    @property
    def qdrant_abs_path(self) -> Path:
        path = Path(self.qdrant_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def data_root(self) -> Path:
        path = Path(self.data_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def uploads_root(self) -> Path:
        path = Path(self.uploads_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def cms_file(self) -> Path:
        path = Path(self.cms_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def chat_completions_url(self) -> str:
        base = self.model_url.rstrip("/")
        return f"{base}/v1/chat/completions"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
