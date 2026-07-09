"""
OmniCore — Configuration
All settings are loaded from environment variables.
Never hardcode secrets, API keys, or deployment URLs.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "OmniCore"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # ── Security & JWT ────────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production-minimum-256-bit-random-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_PATH: str = "./data/database/omnicore.db"
    # Set DATABASE_URL to override SQLite (e.g. postgresql://user:pass@host/db)
    DATABASE_URL: Optional[str] = None

    # ── Dataset Storage & Cache ───────────────────────────────────────────────
    DATASET_STORAGE_PATH: str = "./data/cache"

    # ── AI Provider — OpenRouter ──────────────────────────────────────────────
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    # Comma-separated list of allowed origins
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_AUTH: str = "5/15minutes"
    RATE_LIMIT_API: str = "200/minute"
    RATE_LIMIT_BUILDPILOT: str = "20/minute"

    # ── Sync Engine ───────────────────────────────────────────────────────────
    SYNC_INTERVAL_HOURS: int = 24

    # ── HuggingFace Registry & Deployment ────────────────────────────────────
    HF_TOKEN: Optional[str] = None
    HF_ORG_NAME: str = "omnicore-data"
    HF_SPACE_URL: Optional[str] = None

    # ── Properties ───────────────────────────────────────────────────────────
    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"sqlite:///{self.DATABASE_PATH}"

    @property
    def allowed_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
