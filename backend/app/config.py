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


@lru_cache
def get_settings() -> Settings:
    return Settings()
