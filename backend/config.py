from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Хмарний голосовий помічник"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/voice_assistant"
    web_origin: str = "http://localhost:5173"
    telegram_bot_token: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str = "mistralai/mistral-7b-instruct"
    groq_api_key: str | None = None
    groq_transcription_model: str = "whisper-large-v3-turbo"
    app_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
