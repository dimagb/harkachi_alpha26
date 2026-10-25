from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "local-demo-secret-change-before-deployment"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://credit:credit@localhost:5432/credit"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_ttl_hours: int = 8
    demo_mode: bool = True
    demo_background: bool = False
    background_path: Path = Path(__file__).resolve().parents[2] / "data/background.json"
    demo_password: str = "demo2026"
    contracts_dir: Path = Path(__file__).resolve().parents[2] / "contracts"
    mocks_url: str = "http://localhost:8001/mock/v1"
    log_level: str = "INFO"
    pipeline_step_delay_sec: float = 2
    source_retry_pause_sec: float = 1
    info_due_days: int = 5
    offer_valid_days: int = 30

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> Self:
        if not self.demo_mode and (
            self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "DEMO_MODE=false: задайте свой JWT_SECRET (не короче 32 символов)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
