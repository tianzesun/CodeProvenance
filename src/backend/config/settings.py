"""Application Settings - Centralized configuration management."""

from pathlib import Path
from typing import Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ENGINE_WEIGHTS: Dict[str, float] = {
    "token": 0.18,
    "ast": 0.22,
    "winnowing": 0.16,
    "gst": 0.16,
    "semantic": 0.18,
    "web": 0.10,
    "ai_detection": 0.0,
    "execution_cfg": 0.0,
}

DEFAULT_DETECTION_MODES = [
    "token",
    "ast",
    "winnowing",
    "gst",
    "semantic",
    "web",
]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    # Similarity
    DEFAULT_THRESHOLD: float = 0.5

    # LLM / AI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-3.5-turbo"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"

    # Auth
    AUTH_JWT_SECRET: Optional[str] = None
    AUTH_TOKEN_EXPIRE_MINUTES: int = 480
    FRONTEND_URL: str = "http://localhost:3000"

    # External plagiarism services
    MOSS_USER_ID: Optional[str] = None

    # Embeddings
    EMBEDDING_RUNTIME: str = "local_unixcoder"
    EMBEDDING_MODEL: str = "microsoft/unixcoder-base"
    EMBEDDING_SERVER_URL: Optional[str] = None
    EMBEDDING_SERVER_HOST: Optional[str] = None
    EMBEDDING_SERVER_PORT: int = 8000
    EMBEDDING_DEVICE: str = "auto"
    EMBEDDING_BATCH_SIZE: int = 32

    # AI Detection
    GPTZERO_API_KEY: Optional[str] = None
    GRAMMARLY_API_KEY: Optional[str] = None

    # Engine Weights
    ENGINE_WEIGHTS: Dict[str, float] = DEFAULT_ENGINE_WEIGHTS.copy()

    # Advanced
    BATCH_SIZE: int = 32
    MAX_FILE_SIZE_MB: int = 10
    MAX_FILES_PER_JOB: int = 500


settings = AppSettings()
