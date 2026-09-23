from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Knigoluby"
    environment: str = "development"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "knigoluby"
    jwt_secret: str = "development-secret-change-me-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
