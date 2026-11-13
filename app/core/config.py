from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str = "Knigoluby"
    environment: str = "development"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "knigoluby"
    jwt_secret: str = "development-secret-change-me-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_ssl: bool = False
    brevo_api_key: str | None = None
    email_from_email: str | None = None
    email_from_name: str = "Книголюби"
    frontend_url: str = "http://localhost:5173"

    @field_validator("brevo_api_key", mode="before")
    @classmethod
    def normalize_brevo_key(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
