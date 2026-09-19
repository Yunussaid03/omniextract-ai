from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings managed via environment variables or .env file."""

    APP_NAME: str = "OmniExtract AI"
    APP_ENV: str = "development"
    
    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/omniextract_db"

    # OpenAI Multimodal Integration Settings (Placeholders for future use)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
