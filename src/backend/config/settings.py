"""Application Settings - Centralized configuration management.

Conventions
-----------
* Anything that is, or can contain, a credential is a ``SecretStr`` (database and Redis URLs, JWT secret, API
  keys, SMTP password, webhook URL). It prints as ``**********`` in ``repr()``, logs and validation errors. Call
  ``.get_secret_value()`` only at the point of use, and never log the result.
* Production secrets should be injected into the process environment by a secret store. The ``.env.local`` file
  is a local-development convenience: set ``APP_ENV=production`` and it is never read.
* List and dict settings are read from the environment as JSON, for example
  ``DEFAULT_DETECTION_MODES='["token","ast"]'``.
* Settings are read-only after start-up (``frozen``), and are created lazily by ``get_settings()``.
"""

import ipaddress
import logging
import math
import os
import re
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ── Engine weights ───────────────────────────────────────────────────────────

# Read-only views: these used to be plain dicts, so code that normalised or edited a profile in place changed
# it for every caller. Use ``get_weight_profile()`` / ``AppSettings.engine_weights()`` to get an editable copy.
DEFAULT_ENGINE_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {
        "token": 0.12,
        "winnowing": 0.16,
        "gst": 0.13,
        "ast": 0.17,
        "ngram": 0.10,
        "graph": 0.15,
        "embedding": 0.12,
        "static_rules": 0.05,
    }
)

ENGINE_NAMES: tuple[str, ...] = tuple(DEFAULT_ENGINE_WEIGHTS)

ENGINE_WEIGHT_PROFILES: Mapping[str, Mapping[str, float]] = MappingProxyType(
    {
        "standard": MappingProxyType(dict(DEFAULT_ENGINE_WEIGHTS)),
        "conservative": MappingProxyType(
            {
                "token": 0.16,
                "winnowing": 0.20,
                "gst": 0.16,
                "ast": 0.18,
                "ngram": 0.12,
                "graph": 0.12,
                "embedding": 0.04,
                "static_rules": 0.02,
            }
        ),
        "rewrite-sensitive": MappingProxyType(
            {
                "token": 0.05,
                "winnowing": 0.07,
                "gst": 0.08,
                "ast": 0.24,
                "ngram": 0.04,
                "graph": 0.22,
                "embedding": 0.22,
                "static_rules": 0.08,
            }
        ),
    }
)

WEIGHT_SUM_TOLERANCE = 1e-6


def check_weights(weights: Mapping[str, float], label: str) -> list[str]:
    """Return a list of problems with an engine-weight table (empty when it is valid)."""
    problems: list[str] = []
    unknown = sorted(set(weights) - set(ENGINE_NAMES))
    if unknown:
        problems.append(f"{label}: unknown engine(s) {', '.join(unknown)} (known: {', '.join(ENGINE_NAMES)})")
    bad = [
        name
        for name, value in weights.items()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
    ]
    if bad:
        problems.append(f"{label}: weight(s) for {', '.join(sorted(bad))} must be finite numbers >= 0")
    elif weights and abs(sum(weights.values()) - 1.0) > WEIGHT_SUM_TOLERANCE:
        problems.append(f"{label}: weights must sum to 1.0 (they sum to {sum(weights.values()):.6f})")
    elif not weights:
        problems.append(f"{label}: must not be empty")
    return problems


# The built-in tables are checked once, at import, so a bad edit fails immediately and not on the first scan.
for _profile_name, _profile in ENGINE_WEIGHT_PROFILES.items():
    _problems = check_weights(_profile, f"profile {_profile_name!r}")
    if _problems:  # pragma: no cover - guards against future edits
        raise RuntimeError("; ".join(_problems))


def get_weight_profile(name: str) -> dict[str, float]:
    """An editable copy of a named profile."""
    try:
        return dict(ENGINE_WEIGHT_PROFILES[name])
    except KeyError:
        raise KeyError(f"Unknown weight profile {name!r}. Available: {', '.join(ENGINE_WEIGHT_PROFILES)}") from None


# ── Validation helpers (plain functions, so they can be unit-tested without building settings) ──

#: Provider keys from `integrations.provider_catalog`. Keep in sync with the catalog, or import it from there.
KNOWN_LLM_PROVIDERS: frozenset[str] = frozenset(
    {"openai", "anthropic", "google", "xai", "mistral", "deepseek", "groq", "openrouter", "ollama"}
)

_WEAK_SECRETS = frozenset(
    {"changeme", "change-me", "change_me", "secret", "password", "dev", "development", "test", "replace-me", "your-secret-here"}
)

_LOOPBACK_HOSTS = frozenset({"localhost"})


def weak_secret_reason(secret: str) -> str | None:
    """Why a signing secret is unacceptable, or None. The returned text never contains the secret."""
    if len(secret) < 32:
        return "is shorter than 32 characters"
    if secret.strip().lower() in _WEAK_SECRETS:
        return "is a well-known placeholder"
    if len(set(secret)) < 10:
        return "has too little variety (use a randomly generated value)"
    return None


def check_outbound_url(
    url: str, *, label: str, debug: bool, allow_private: bool = False
) -> list[tuple[str, str]]:
    """Check a URL the server will call. Returns ``(severity, message)`` pairs: "error" or "policy".

    This only inspects the URL as written. A host *name* can still resolve to an internal address, so the code that
    makes the request must also refuse private, loopback and link-local results of DNS resolution.
    """
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError:
        return [("error", f"{label}: is not a valid URL")]
    if parts.scheme.lower() not in ("http", "https") or not host:
        return [("error", f"{label}: must be an http(s) URL with a host name")]

    results: list[tuple[str, str]] = []
    if parts.username or parts.password:
        results.append(("error", f"{label}: must not contain a user name or password in the URL"))

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    loopback = host in _LOOPBACK_HOSTS or (ip is not None and ip.is_loopback)

    if parts.scheme.lower() == "http" and not (debug or loopback):
        results.append(("policy", f"{label}: must use https"))
    if loopback:
        # Local services (Ollama, an embedding server) are fine; a webhook or scan target on this machine is not.
        if not allow_private and not debug:
            results.append(("error", f"{label}: must not point at the local machine"))
    elif ip is not None:
        # 169.254.169.254 (cloud metadata) and fe80::/10 are link-local: never a legitimate target.
        # (Loopback is handled above: Python also counts ::1 as "reserved", which used to reject it here.)
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            results.append(("error", f"{label}: must not point at a link-local or reserved address"))
        elif ip.is_private and not allow_private and not debug:
            results.append(("error", f"{label}: must not point at a private network address"))
    return results


_ENV_PREFIXES = (
    "AUTH_", "LLM_", "EMAIL_", "EMBEDDING_", "GUEST_", "SOURCE_SCAN_", "AUDIT_", "ALLOW_", "EXPOSE_",
    "DEFAULT_", "MAX_", "OPENAI_", "ANTHROPIC_", "OLLAMA_", "SENDGRID_", "GPTZERO_", "GRAMMARLY_", "MOSS_",
    "DETECTION_", "SECURITY_",
)  # fmt: skip

_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def unknown_setting_names(names: Iterable[str], known: Iterable[str]) -> list[str]:
    """Names that look like settings (known prefix) but match no field: almost always a typo."""
    known_upper = {k.upper() for k in known}
    return sorted(
        {n for n in names if n.upper().startswith(_ENV_PREFIXES) and n.upper() not in known_upper}
    )


def _env_file_names(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    try:
        return [m.group(1) for line in path.read_text(encoding="utf-8").splitlines() if (m := _ENV_LINE.match(line))]
    except OSError:
        return []


def _resolve_env_file() -> Path | None:
    """The env file to read, or None. Production (APP_ENV=production) never reads a file."""
    if os.environ.get("APP_ENV", "development").strip().lower() == "production":
        return None
    override = os.environ.get("APP_ENV_FILE")
    # Resolved to an absolute path so it doesn't depend on the working directory.
    return Path(override) if override else Path(__file__).resolve().parent.parent / ".env.local"


_ENV_FILE = _resolve_env_file()


# ── Settings ─────────────────────────────────────────────────────────────────


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Core
    #: Contains the database password.
    DATABASE_URL: SecretStr
    #: May contain a password (redis://:password@host).
    REDIS_URL: SecretStr = SecretStr("redis://localhost:6379/0")

    # Similarity
    #: NOTE: the web app falls back to 0.75 when a job carries no threshold. Keep the two in step, or return this
    #: value from the API so the front end never needs its own default.
    DEFAULT_THRESHOLD: float = Field(0.82, ge=0.0, le=1.0)

    # LLM / AI
    #: Active provider key from `integrations.provider_catalog` (openai,
    #: anthropic, google, xai, mistral, deepseek, groq, openrouter, ollama).
    LLM_PROVIDER: str = "openai"
    #: Optional secondary provider used when the primary one is unavailable.
    LLM_FALLBACK_PROVIDER: str = ""
    #: Per-provider API keys, keyed by canonical provider name. Takes precedence over the legacy
    #: OPENAI_API_KEY / ANTHROPIC_API_KEY fields below (use `llm_api_key()` to read the effective key).
    LLM_API_KEYS: dict[str, SecretStr] = Field(default_factory=dict)
    #: Per-provider model overrides. An empty string means "use the newest
    #: model the provider currently offers", resolved at call time so the
    #: application never pins an obsolete model by accident.
    #: Because the resolved model can change without a deploy, store the model id that actually produced each
    #: result alongside it, or earlier results can't be reproduced or explained.
    LLM_MODEL_OVERRIDES: dict[str, str] = Field(default_factory=dict)
    #: Per-provider base URL overrides (self-hosted gateways, proxies, ...). API keys are sent to these hosts.
    LLM_BASE_URLS: dict[str, str] = Field(default_factory=dict)

    # Legacy per-provider fields. LLM_API_KEYS / LLM_MODEL_OVERRIDES / LLM_BASE_URLS win when both are set.
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = ""

    ANTHROPIC_API_KEY: SecretStr | None = None
    ANTHROPIC_MODEL: str = ""

    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # Auth
    #: Must be at least 32 random characters in production.
    AUTH_JWT_SECRET: SecretStr
    AUTH_TOKEN_EXPIRE_MINUTES: int = Field(480, ge=1, le=43200)
    AUTH_COOKIE_SECURE: bool = False
    FRONTEND_URL: str = "http://localhost:3000"

    # Release security policy
    #: How violations of the production rules in `_check_security_policy` are handled when DEBUG_MODE is off:
    #: "enforce" refuses to start, "warn" logs them. "warn" exists to ease a rollout and should not be permanent.
    SECURITY_POLICY_MODE: Literal["enforce", "warn"] = "enforce"
    #: Serve the interactive API reference at /docs, /redoc and /openapi.json.
    #: Off by default: the schema describes every endpoint in the system.
    EXPOSE_API_DOCS: bool = False
    #: Allow upload / AI review / benchmark endpoints to be called without a
    #: session cookie or API key. Only enable this for local demos.
    ALLOW_ANONYMOUS_ANALYSIS: bool = False
    #: Create the seeded development/demo API keys at startup. Requires
    #: DEBUG_MODE as well, so a production deployment cannot enable it by
    #: accident with a single stray variable.
    ALLOW_DEV_API_KEYS: bool = False

    # Guest demo sessions ("Try the checker without an account").
    #: Expose POST /api/auth/guest on the login page. A guest session is a
    #: short-lived cookie that owns no workspace: guest jobs are never written
    #: to the database and are swept from memory/disk when the session expires.
    #: Set to false on deployments that must not offer anonymous compute.
    GUEST_LOGIN_ENABLED: bool = True
    #: Lifetime of a guest session and of the results it produced.
    GUEST_SESSION_MINUTES: int = Field(30, ge=1, le=240)

    # External plagiarism / AI-detection services. These send student work to a third party, so each one needs an
    # explicit *_ENABLED switch: a key sitting in the environment is not enough. Use the `*_active` properties.
    MOSS_ENABLED: bool = False
    MOSS_USER_ID: str | None = None

    # Embeddings
    EMBEDDING_RUNTIME: str = "local_unixcoder"
    EMBEDDING_MODEL: str = "microsoft/unixcoder-base"
    EMBEDDING_SERVER_URL: str | None = None
    EMBEDDING_SERVER_HOST: str | None = None
    EMBEDDING_SERVER_PORT: int = Field(8000, ge=1, le=65535)
    EMBEDDING_DEVICE: str = Field("auto", pattern=r"^(auto|cpu|mps|cuda(:\d+)?)$")
    EMBEDDING_BATCH_SIZE: int = Field(32, ge=1)

    # AI Detection
    GPTZERO_ENABLED: bool = False
    GPTZERO_API_KEY: SecretStr | None = None
    GRAMMARLY_ENABLED: bool = False
    GRAMMARLY_API_KEY: SecretStr | None = None

    # Email delivery (password reset, review notifications, and test sends).
    #: ``console`` logs the message to stdout (development only: it prints reset links), ``smtp`` uses the
    #: ``EMAIL_*`` fields below, and ``sendgrid`` uses ``SENDGRID_API_KEY``.
    EMAIL_BACKEND: Literal["console", "smtp", "sendgrid"] = "console"
    EMAIL_HOST: str = "localhost"
    EMAIL_PORT: int = Field(587, ge=1, le=65535)
    EMAIL_USER: str = ""
    EMAIL_PASSWORD: SecretStr | None = None
    EMAIL_FROM: str = "noreply@integritydesk.com"
    #: STARTTLS (typically port 587). For implicit TLS (typically port 465) use EMAIL_USE_SSL instead; set only one.
    EMAIL_USE_TLS: bool = True
    EMAIL_USE_SSL: bool = False
    SENDGRID_API_KEY: SecretStr | None = None

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
    DEFAULT_DETECTION_MODES: list[str] = Field(default_factory=lambda: list(ENGINE_NAMES))

    # Engine Weights (must sum to 1.0 and use known engine names; see `check_weights`)
    ENGINE_WEIGHTS: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_ENGINE_WEIGHTS))

    # Advanced
    BATCH_SIZE: int = Field(32, ge=1)
    MAX_FILE_SIZE_MB: int = Field(10, ge=1)
    #: Ceiling on the line count of a single submission. The byte cap alone does
    #: not bound analysis cost: a million-line file of short statements is under
    #: 10 MB but drives the engine pipeline for hours.
    MAX_FILE_LINES: int = Field(50_000, ge=1)
    MAX_FILES_PER_JOB: int = Field(500, ge=1)

    # Integrations
    #: Slack/Teams-style webhook URLs are bearer secrets, so this is a SecretStr (empty means "off").
    WEBHOOK_URL: SecretStr = SecretStr("")

    # Public source scanning (GitHub / Stack Overflow provenance checks)
    SOURCE_SCAN_ENABLED: bool = False
    SOURCE_SCAN_SITES: list[str] = Field(default_factory=lambda: ["https://github.com"])

    # Audit & Compliance
    AUDIT_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    AUDIT_RETENTION_DAYS: int = Field(365, ge=1)

    # Expert
    DEBUG_MODE: bool = False

    # ── Field validators ─────────────────────────────────────────────────────

    @field_validator("AUDIT_LOG_LEVEL", mode="before")
    @classmethod
    def _upper_log_level(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("LLM_PROVIDER", "LLM_FALLBACK_PROVIDER", mode="after")
    @classmethod
    def _known_provider(cls, value: str, info) -> str:
        value = value.strip().lower()
        if not value and info.field_name == "LLM_PROVIDER":
            raise ValueError("LLM_PROVIDER must not be empty")
        if value and value not in KNOWN_LLM_PROVIDERS:
            raise ValueError(f"{info.field_name} must be one of: {', '.join(sorted(KNOWN_LLM_PROVIDERS))}")
        return value

    @field_validator("LLM_API_KEYS", "LLM_MODEL_OVERRIDES", "LLM_BASE_URLS", mode="after")
    @classmethod
    def _lowercase_provider_keys(cls, value: dict) -> dict:
        # "OpenAI" and "openai" used to be two different entries.
        return {str(key).strip().lower(): item for key, item in value.items()}

    # ── Cross-field checks ───────────────────────────────────────────────────

    @model_validator(mode="after")
    def _check_consistency(self) -> "AppSettings":
        """Rules that must hold in every environment. A violation stops start-up."""
        errors: list[str] = []
        policy: list[str] = []
        warnings: list[str] = []

        # Detection pipeline
        errors += check_weights(self.ENGINE_WEIGHTS, "ENGINE_WEIGHTS")
        if not self.DEFAULT_DETECTION_MODES:
            errors.append("DEFAULT_DETECTION_MODES: must list at least one engine")
        unweighted = sorted(set(self.DEFAULT_DETECTION_MODES) - set(self.ENGINE_WEIGHTS))
        if unweighted:
            errors.append(f"DEFAULT_DETECTION_MODES: no weight set for {', '.join(unweighted)}")
        if self.DEFAULT_DETECTION_DOMAIN not in self.DETECTION_DOMAIN_PRESETS:
            errors.append(
                f"DEFAULT_DETECTION_DOMAIN {self.DEFAULT_DETECTION_DOMAIN!r} is not one of "
                f"DETECTION_DOMAIN_PRESETS ({', '.join(self.DETECTION_DOMAIN_PRESETS)})"
            )

        # Email: each backend needs its own settings, or the first password-reset email fails.
        if self.EMAIL_USE_TLS and self.EMAIL_USE_SSL:
            errors.append("EMAIL_USE_TLS (STARTTLS) and EMAIL_USE_SSL (implicit TLS) are mutually exclusive")
        if self.EMAIL_BACKEND == "smtp":
            if not self.EMAIL_HOST.strip():
                errors.append("EMAIL_BACKEND=smtp requires EMAIL_HOST")
            if self.EMAIL_USER and not self.EMAIL_PASSWORD:
                errors.append("EMAIL_USER is set but EMAIL_PASSWORD is not")
            host = self.EMAIL_HOST.strip().lower()
            if not (self.EMAIL_USE_TLS or self.EMAIL_USE_SSL) and host not in ("localhost", "127.0.0.1", "::1"):
                policy.append("EMAIL_BACKEND=smtp to a remote host needs EMAIL_USE_TLS or EMAIL_USE_SSL")
        if self.EMAIL_BACKEND == "sendgrid" and not self.SENDGRID_API_KEY:
            errors.append("EMAIL_BACKEND=sendgrid requires SENDGRID_API_KEY")

        # Outbound URLs. These are the addresses the server calls, and API keys go to the LLM ones.
        urls: list[tuple[str, str, bool]] = [
            ("OPENAI_BASE_URL", self.OPENAI_BASE_URL, True),
            ("OLLAMA_BASE_URL", self.OLLAMA_BASE_URL, True),
        ]
        urls += [(f"LLM_BASE_URLS[{k}]", v, True) for k, v in self.LLM_BASE_URLS.items() if v]
        if self.EMBEDDING_SERVER_URL:
            urls.append(("EMBEDDING_SERVER_URL", self.EMBEDDING_SERVER_URL, True))
        webhook = self.WEBHOOK_URL.get_secret_value().strip()
        if webhook:
            urls.append(("WEBHOOK_URL", webhook, False))
        urls += [(f"SOURCE_SCAN_SITES[{i}]", site, False) for i, site in enumerate(self.SOURCE_SCAN_SITES)]
        for label, url, allow_private in urls:
            for severity, message in check_outbound_url(url, label=label, debug=self.DEBUG_MODE, allow_private=allow_private):
                (errors if severity == "error" else policy).append(message)

        # Conflicting duplicate settings (values are never logged)
        for provider, legacy in (("openai", self.OPENAI_API_KEY), ("anthropic", self.ANTHROPIC_API_KEY)):
            new = self.LLM_API_KEYS.get(provider)
            if new and legacy and new.get_secret_value() != legacy.get_secret_value():
                warnings.append(
                    f"{provider}: LLM_API_KEYS and {provider.upper()}_API_KEY are both set and differ; LLM_API_KEYS is used"
                )
        # A key present but its service switched off is almost always a half-finished rollout.
        for name, enabled, key in (
            ("GPTZERO", self.GPTZERO_ENABLED, self.GPTZERO_API_KEY),
            ("GRAMMARLY", self.GRAMMARLY_ENABLED, self.GRAMMARLY_API_KEY),
        ):
            if key and not enabled:
                warnings.append(f"{name}_API_KEY is set but {name}_ENABLED is false, so the service is not used")
            if enabled and not key:
                errors.append(f"{name}_ENABLED is true but {name}_API_KEY is not set")
        if self.MOSS_ENABLED and not self.MOSS_USER_ID:
            errors.append("MOSS_ENABLED is true but MOSS_USER_ID is not set")

        if errors:
            raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))

        # Production policy. "Production" means DEBUG_MODE is off, the same test the dev-key rule already uses.
        if not self.DEBUG_MODE:
            policy += self._production_policy_problems()
            if _ENV_FILE is not None and _ENV_FILE.is_file():
                warnings.append(
                    f"settings are being read from {_ENV_FILE.name}; in production, inject them from a secret store "
                    "and set APP_ENV=production"
                )
            if self.EXPOSE_API_DOCS:
                warnings.append("EXPOSE_API_DOCS is on: the API schema is public")
            if self.GUEST_LOGIN_ENABLED:
                warnings.append("GUEST_LOGIN_ENABLED is on: anonymous users can run analyses")

        if policy:
            message = "Configuration violates the production security policy:\n- " + "\n- ".join(policy)
            if self.SECURITY_POLICY_MODE == "enforce":
                raise ValueError(message + "\n(Set DEBUG_MODE=true for local development.)")
            logger.warning("%s\n(SECURITY_POLICY_MODE=warn: continuing)", message)
        for text in warnings:
            logger.warning("Configuration: %s", text)
        return self

    def _production_policy_problems(self) -> list[str]:
        problems: list[str] = []
        if not self.AUTH_COOKIE_SECURE:
            problems.append("AUTH_COOKIE_SECURE must be true")
        if urlsplit(self.FRONTEND_URL).scheme.lower() != "https":
            problems.append("FRONTEND_URL must be an https URL")
        reason = weak_secret_reason(self.AUTH_JWT_SECRET.get_secret_value())
        if reason:
            problems.append(f"AUTH_JWT_SECRET {reason}")
        if self.EMAIL_BACKEND == "console":
            problems.append("EMAIL_BACKEND=console prints password-reset links to the log; configure smtp or sendgrid")
        if self.ALLOW_DEV_API_KEYS:
            problems.append("ALLOW_DEV_API_KEYS requires DEBUG_MODE")
        if self.ALLOW_ANONYMOUS_ANALYSIS:
            problems.append("ALLOW_ANONYMOUS_ANALYSIS is for local demos only and requires DEBUG_MODE")
        return problems

    # ── Accessors (one place for each precedence rule) ───────────────────────

    @property
    def is_production(self) -> bool:
        return not self.DEBUG_MODE

    @property
    def moss_active(self) -> bool:
        return self.MOSS_ENABLED and bool(self.MOSS_USER_ID)

    @property
    def gptzero_active(self) -> bool:
        return self.GPTZERO_ENABLED and bool(self.GPTZERO_API_KEY)

    @property
    def grammarly_active(self) -> bool:
        return self.GRAMMARLY_ENABLED and bool(self.GRAMMARLY_API_KEY)

    def llm_api_key(self, provider: str) -> SecretStr | None:
        """The effective key for a provider: LLM_API_KEYS first, then the legacy field."""
        provider = provider.strip().lower()
        legacy = {"openai": self.OPENAI_API_KEY, "anthropic": self.ANTHROPIC_API_KEY}.get(provider)
        return self.LLM_API_KEYS.get(provider) or legacy

    @property
    def auth_jwt_secret(self) -> str:
        """The JWT signing key as a plain string.

        ``jose`` requires a ``str``/``bytes`` key and raises ``JWSError`` when handed a
        ``SecretStr`` wrapper, so every sign/verify call site must go through this
        accessor rather than reading ``AUTH_JWT_SECRET`` directly.
        """
        return self.AUTH_JWT_SECRET.get_secret_value()

    def llm_model(self, provider: str) -> str:
        """The configured model, or "" meaning "the provider's newest"."""
        provider = provider.strip().lower()
        legacy = {"openai": self.OPENAI_MODEL, "anthropic": self.ANTHROPIC_MODEL}.get(provider, "")
        return self.LLM_MODEL_OVERRIDES.get(provider) or legacy

    def llm_base_url(self, provider: str) -> str:
        provider = provider.strip().lower()
        legacy = {"openai": self.OPENAI_BASE_URL, "ollama": self.OLLAMA_BASE_URL}.get(provider, "")
        return self.LLM_BASE_URLS.get(provider) or legacy

    def engine_weights(self) -> dict[str, float]:
        """An editable copy; the settings object itself is read-only."""
        return dict(self.ENGINE_WEIGHTS)


# ── Access ───────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """The process-wide settings, created on first use. Tests can call ``get_settings.cache_clear()``."""
    loaded = AppSettings()  # type: ignore[call-arg]  # required fields come from the environment
    # `extra="ignore"` made a misspelt variable (AUTH_COOKIE_SECUR=true) vanish and leave the default in force.
    names = list(os.environ) + _env_file_names(_ENV_FILE)
    for name in unknown_setting_names(names, AppSettings.model_fields):
        logger.warning("Configuration: %s looks like a setting but matches no known field (typo?)", name)
    return loaded


if TYPE_CHECKING:
    settings: AppSettings


def __getattr__(name: str):
    # `from config.settings import settings` keeps working, but the settings are now built when first imported by
    # name, not when the module is imported, so tools that only need DEFAULT_ENGINE_WEIGHTS don't need the full env.
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
