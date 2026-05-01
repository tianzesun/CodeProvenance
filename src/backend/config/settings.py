"""Application Settings - Centralized configuration management."""

from pathlib import Path
from typing import Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ENGINE_WEIGHTS: Dict[str, float] = {
    "token": 0.10,
    "ngram": 0.08,
    "winnowing": 0.12,
    "ast": 0.22,
    "graph": 0.10,
    "execution": 0.14,
    "embedding": 0.16,
    "llm": 0.08,
}

ENGINE_WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
    "standard": DEFAULT_ENGINE_WEIGHTS.copy(),
    "conservative": {
        "token": 0.15,
        "ngram": 0.12,
        "winnowing": 0.18,
        "ast": 0.20,
        "graph": 0.12,
        "execution": 0.10,
        "embedding": 0.10,
        "llm": 0.03,
    },
    "rewrite-sensitive": {
        "token": 0.05,
        "ngram": 0.04,
        "winnowing": 0.06,
        "ast": 0.25,
        "graph": 0.18,
        "execution": 0.20,
        "embedding": 0.17,
        "llm": 0.05,
    },
}

DEFAULT_DETECTION_MODES = [
    "token",
    "ngram",
    "winnowing",
    "ast",
    "graph",
    "execution",
    "embedding",
    "llm",
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
    DEFAULT_THRESHOLD: float = 0.82

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
