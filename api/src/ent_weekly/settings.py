from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pubmed_email: str = ""
    ncbi_api_key: str | None = None
    pubmed_tool: str = "ent-weekly"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str = ""
    deepseek_model: str = ""
    llm_timeout_seconds: int = 60
    llm_max_concurrent: int = 3
    db_path: Path = Path("/data/ent_weekly.db")
    snapshot_dir: Path = Path("/data/snapshots")
    journal_quality_path: Path = Path("/data/journal-quality.json")
    regen_token: str = ""


settings = Settings()
