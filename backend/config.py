from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cloud Voice Assistant API"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/voice_assistant"
    web_origin: str = "http://localhost:5173"
    telegram_bot_token: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str = "mistralai/mistral-7b-instruct"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
