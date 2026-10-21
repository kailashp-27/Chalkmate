from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "postgresql+psycopg://chalkmate_app@127.0.0.1:54322/postgres"
    celery_broker_url: str = "redis://localhost:6379/0"
    migration_database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    storage_bucket: str = "classroom-files"
    web_origin: str = "http://localhost:3000"
    worker_database_url: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    ollama_vision_model: str = ""
    processing_timeout: int = 180
    recovery_report_path: str = ".tmp/recovery-last-report.json"
    mail_provider: Literal["disabled", "mailpit", "resend"] = "mailpit"
    mailpit_url: str = "http://127.0.0.1:54324"
    mail_from: str = "Chalkmate <teacher@example.com>"
    enable_external_email: bool = False
    resend_api_key: SecretStr = SecretStr("")
    resend_webhook_secret: SecretStr = SecretStr("")


@lru_cache
def get_settings() -> Settings:
    return Settings()
