from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

#centralized Configuration

# Path to the .env file in the day3 project root
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Typed centralized application settings loaded from .env file.
    Missing required environment variables will cause startup validation failure.
    """
    DATABASE_URL: str
    TOKEN_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    ALLOWED_CORS_ORIGINS: str
    API_VERSION: str

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Single config object created once when the config module is imported
settings = Settings()
