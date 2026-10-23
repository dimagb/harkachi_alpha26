from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://credit:credit@localhost:5432/credit"
    jwt_secret: str = "local-demo-secret-change-before-deployment"
    jwt_ttl_hours: int = 8
    demo_mode: bool = True
    demo_password: str = "demo2026"
    contracts_dir: Path = Path(__file__).resolve().parents[2] / "contracts"
    mocks_url: str = "http://localhost:8001/mock/v1"
    log_level: str = "INFO"
    pipeline_step_delay_sec: float = 2
    source_retry_pause_sec: float = 1
    info_due_days: int = 5
    offer_valid_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
