"""Multi-LLM router with provider-aware configuration using LiteLLM and DSPy."""

import logging
import os
import threading
from typing import Literal

import dspy
from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_primary_lm: dspy.LM | None = None
_fast_lm: dspy.LM | None = None
_lm_lock = threading.Lock()


class Settings(BaseSettings):
    """Strictly validated environment settings for LLM provider access."""

    model_config = ConfigDict(strict=True, case_sensitive=True)

    LLM_PROVIDER: Literal["vertex_ai", "api_keys"] | None = None
    PRIMARY_LLM_MODEL: str | None = None
    FAST_LLM_MODEL: str | None = None
    VERTEXAI_PROJECT: str | None = None
    VERTEXAI_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> "Settings":
        """Fail fast with actionable errors before Temporal starts work."""
        has_legacy_key = any(
            (self.ANTHROPIC_API_KEY, self.OPENAI_API_KEY, self.GEMINI_API_KEY)
        )

        if self.LLM_PROVIDER is None:
            self.LLM_PROVIDER = "vertex_ai" if self.VERTEXAI_PROJECT else "api_keys"

        if self.LLM_PROVIDER == "vertex_ai" and not self.VERTEXAI_PROJECT:
            msg = "VERTEXAI_PROJECT is required when LLM_PROVIDER=vertex_ai"
            raise ValueError(msg)

        if self.LLM_PROVIDER == "api_keys" and not has_legacy_key:
            msg = "at least one legacy LLM API key is required when LLM_PROVIDER=api_keys"
            raise ValueError(msg)

        if self.PRIMARY_LLM_MODEL is None:
            self.PRIMARY_LLM_MODEL = self._default_primary_model()
        if self.FAST_LLM_MODEL is None:
            self.FAST_LLM_MODEL = self._default_fast_model()

        if self.LLM_PROVIDER == "api_keys" and (
            self.PRIMARY_LLM_MODEL.startswith("vertex_ai/")
            or self.FAST_LLM_MODEL.startswith("vertex_ai/")
        ):
            msg = "LLM_PROVIDER=api_keys cannot use vertex_ai/ models"
            raise ValueError(msg)

        return self

    def _default_primary_model(self) -> str:
        if self.LLM_PROVIDER == "vertex_ai":
            return "vertex_ai/gemini-2.5-flash"
        if self.ANTHROPIC_API_KEY:
            return "anthropic/claude-3-5-sonnet-latest"
        if self.OPENAI_API_KEY:
            return "openai/gpt-4o"
        return "gemini/gemini-2.0-flash"

    def _default_fast_model(self) -> str:
        if self.LLM_PROVIDER == "vertex_ai":
            return "vertex_ai/gemini-2.5-flash"
        if self.GEMINI_API_KEY:
            return "gemini/gemini-2.0-flash"
        return self._default_primary_model()


def _configure_provider_environment(settings: Settings) -> None:
    """Expose provider credentials in the env format expected by LiteLLM."""
    if settings.LLM_PROVIDER == "vertex_ai":
        if settings.VERTEXAI_PROJECT:
            os.environ.setdefault("VERTEXAI_PROJECT", settings.VERTEXAI_PROJECT)
        os.environ.setdefault("VERTEXAI_LOCATION", settings.VERTEXAI_LOCATION)
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            os.environ.setdefault(
                "GOOGLE_APPLICATION_CREDENTIALS",
                settings.GOOGLE_APPLICATION_CREDENTIALS,
            )
        return

    if settings.ANTHROPIC_API_KEY:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY)
    if settings.OPENAI_API_KEY:
        os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    if settings.GEMINI_API_KEY:
        os.environ.setdefault("GEMINI_API_KEY", settings.GEMINI_API_KEY)


def _build_primary_lm() -> dspy.LM:
    settings = Settings()
    _configure_provider_environment(settings)

    lm_kwargs: dict[str, object] = {
        "model": settings.PRIMARY_LLM_MODEL,
        "max_tokens": 4096,
        "timeout": 30,
        "max_retries": 3,
    }
    if (
        settings.LLM_PROVIDER == "api_keys"
        and settings.OPENAI_API_KEY
        and settings.PRIMARY_LLM_MODEL != "openai/gpt-4o"
    ):
        lm_kwargs["fallbacks"] = ["openai/gpt-4o"]

    lm = dspy.LM(**lm_kwargs)

    logger.info(
        "Configured primary DSPy LM (process singleton): %s",
        settings.PRIMARY_LLM_MODEL,
    )
    return lm


def get_configured_lm() -> dspy.LM:
    """Return the process-wide primary DSPy LM (thread-safe singleton).

    DSPy forbids re-initializing global settings from concurrent code paths.
    Temporal runs activities on a thread pool, so parallel batch items must
    share one ``dspy.LM`` instance. Callers still scope usage with
    ``dspy.context(lm=...)`` per prediction.
    """
    global _primary_lm
    if _primary_lm is not None:
        return _primary_lm
    with _lm_lock:
        if _primary_lm is None:
            _primary_lm = _build_primary_lm()
        return _primary_lm


def _build_fast_lm() -> dspy.LM:
    settings = Settings()
    _configure_provider_environment(settings)
    lm = dspy.LM(
        model=settings.FAST_LLM_MODEL,
        timeout=15,
        max_retries=2,
    )
    logger.info(
        "Configured fast DSPy LM (process singleton): %s",
        settings.FAST_LLM_MODEL,
    )
    return lm


def get_fast_lm() -> dspy.LM:
    """Return the process-wide fast LM for lightweight tasks (thread-safe singleton)."""
    global _fast_lm
    if _fast_lm is not None:
        return _fast_lm
    with _lm_lock:
        if _fast_lm is None:
            _fast_lm = _build_fast_lm()
        return _fast_lm
