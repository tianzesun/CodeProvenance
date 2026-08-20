"""Application Settings - Centralized configuration management."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ENGINE_WEIGHTS: dict[str, float] = {
    "token": 0.12,
    "winnowing": 0.16,
    "gst": 0.13,
    "ast": 0.17,
    "ngram": 0.10,
    "graph": 0.15,
    "embedding": 0.12,
    "static_rules": 0.05,
}

ENGINE_WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "standard": DEFAULT_ENGINE_WEIGHTS.copy(),
    "conservative": {
        "token": 0.16,
        "winnowing": 0.20,
        "gst": 0.16,
        "ast": 0.18,
        "ngram": 0.12,
        "graph": 0.12,
        "embedding": 0.04,
        "static_rules": 0.02,
    },
    "rewrite-sensitive": {
        "token": 0.05,
        "winnowing": 0.07,
        "gst": 0.08,
        "ast": 0.24,
        "ngram": 0.04,
        "graph": 0.22,
        "embedding": 0.22,
        "static_rules": 0.08,
    },
}


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
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-3.5-turbo"

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"

    # Auth
    AUTH_JWT_SECRET: str
    AUTH_TOKEN_EXPIRE_MINUTES: int = 480
    AUTH_COOKIE_SECURE: bool = False
    FRONTEND_URL: str = "http://localhost:3000"

    # External plagiarism services
    MOSS_USER_ID: str | None = None

    # Embeddings
    EMBEDDING_RUNTIME: str = "local_unixcoder"
    EMBEDDING_MODEL: str = "microsoft/unixcoder-base"
    EMBEDDING_SERVER_URL: str | None = None
    EMBEDDING_SERVER_HOST: str | None = None
    EMBEDDING_SERVER_PORT: int = 8000
    EMBEDDING_DEVICE: str = "auto"
    EMBEDDING_BATCH_SIZE: int = 32

    # AI Detection
    GPTZERO_API_KEY: str | None = None
    GRAMMARLY_API_KEY: str | None = None

    # Detection Pipeline (three-layer decision tree)
    DETECTION_DOMAIN_PRESETS: dict[str, str] = Field(
        default_factory=lambda: {
            "code": "General code plagiarism detection (balanced)",
            "cs_code": "CS programming assignments (AST-weighted)",
            "essay": "Essay/report similarity (semantic-weighted)",
            "math": "Mathematics proofs (structure-weighted)",
        }
    )
    DEFAULT_DETECTION_DOMAIN: str = "code"
    DEFAULT_DETECTION_MODES: list[str] = Field(
        default_factory=lambda: [
            "token",
            "winnowing",
            "gst",
            "ast",
            "ngram",
            "graph",
            "embedding",
            "static_rules",
        ]
    )

    # Engine Weights
    ENGINE_WEIGHTS: dict[str, float] = DEFAULT_ENGINE_WEIGHTS.copy()

    # Advanced
    BATCH_SIZE: int = 32
    MAX_FILE_SIZE_MB: int = 10
    MAX_FILES_PER_JOB: int = 500

    # Integrations
    WEBHOOK_URL: str = ""

    # Audit & Compliance
    AUDIT_LOG_LEVEL: str = "INFO"
    AUDIT_RETENTION_DAYS: int = 365

    # Expert
    DEBUG_MODE: bool = False


settings = AppSettings()
