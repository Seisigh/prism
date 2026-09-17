"""Environment-driven configuration. No credentials in code, ever — see
.env.example. Postgres and Redis config is environment-only per the
kickoff instructions."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_env: str = "development"
    app_port: int = 8000

    database_url: str = "postgresql://prism:prism@localhost:5432/prism"
    redis_url: str = "redis://localhost:6379/0"

    session_idle_timeout_min: int = 30
    retention_days: int = 90
    flush_interval_ms: int = 250

    catalog_path: Path = REPO_ROOT / "data" / "catalog.json"
    thumbs_dir: Path = REPO_ROOT / "data" / "thumbs"


settings = Settings()
