import os
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(PROJECT_ROOT, "backend", ".env"),
        extra="ignore",
    )

    secret_key: str = "change-this-in-production-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day
    database_url: str = f"sqlite:///{os.path.join(PROJECT_ROOT, 'legal_auditor.db')}"
    anthropic_api_key: str = ""
    policies_dir: str = os.path.join(PROJECT_ROOT, "documents", "policies")
    contracts_dir: str = os.path.join(PROJECT_ROOT, "documents", "contracts")
    chroma_db_path: str = os.path.join(PROJECT_ROOT, "chroma_db")


settings = Settings()
