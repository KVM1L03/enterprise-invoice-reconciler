"""Tests for LLM provider configuration."""

import os
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

import ai_worker.llm_router as llm_router


@pytest.fixture(autouse=True)
def reset_lm_singletons() -> Iterator[None]:
    """Keep singleton state from leaking across router tests."""
    llm_router._primary_lm = None
    llm_router._fast_lm = None
    yield
    llm_router._primary_lm = None
    llm_router._fast_lm = None


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "LLM_PROVIDER",
        "PRIMARY_LLM_MODEL",
        "FAST_LLM_MODEL",
        "VERTEXAI_PROJECT",
        "VERTEXAI_LOCATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(key, raising=False)


def test_settings_accepts_vertex_ai_without_api_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "vertex_ai")
    monkeypatch.setenv("VERTEXAI_PROJECT", "invoice-reconciler-prod")
    monkeypatch.setenv("VERTEXAI_LOCATION", "europe-west4")

    settings = llm_router.Settings()

    assert settings.LLM_PROVIDER == "vertex_ai"
    assert settings.VERTEXAI_PROJECT == "invoice-reconciler-prod"
    assert settings.VERTEXAI_LOCATION == "europe-west4"
    assert settings.PRIMARY_LLM_MODEL == "vertex_ai/gemini-2.5-flash"
    assert settings.FAST_LLM_MODEL == "vertex_ai/gemini-2.5-flash"


def test_settings_defaults_to_legacy_provider_when_api_keys_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    settings = llm_router.Settings()

    assert settings.LLM_PROVIDER == "api_keys"
    assert settings.PRIMARY_LLM_MODEL == "openai/gpt-4o"
    assert settings.FAST_LLM_MODEL == "openai/gpt-4o"


def test_legacy_provider_uses_legacy_models_and_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "api_keys")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")

    calls: list[dict[str, object]] = []

    class FakeLM:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(llm_router.dspy, "LM", FakeLM)

    lm = llm_router.get_configured_lm()

    assert isinstance(lm, FakeLM)
    assert calls == [
        {
            "model": "anthropic/claude-3-5-sonnet-latest",
            "max_tokens": 4096,
            "timeout": 30,
            "max_retries": 3,
            "fallbacks": ["openai/gpt-4o"],
        }
    ]


def test_vertex_ai_exports_google_application_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "vertex_ai")
    monkeypatch.setenv("VERTEXAI_PROJECT", "invoice-reconciler-prod")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/var/secrets/google/key.json")

    llm_router.Settings()
    llm_router._configure_provider_environment(llm_router.Settings())

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "/var/secrets/google/key.json"


def test_settings_requires_vertex_ai_project(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "vertex_ai")

    with pytest.raises(ValidationError, match="VERTEXAI_PROJECT"):
        llm_router.Settings()


def test_settings_requires_api_key_for_legacy_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "api_keys")

    with pytest.raises(ValidationError, match="at least one legacy LLM API key"):
        llm_router.Settings()


def test_settings_rejects_vertex_model_for_legacy_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "api_keys")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("PRIMARY_LLM_MODEL", "vertex_ai/gemini-2.5-pro")

    with pytest.raises(ValidationError, match="cannot use vertex_ai/ models"):
        llm_router.Settings()


def test_primary_lm_uses_vertex_ai_model_and_exports_litellm_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "vertex_ai")
    monkeypatch.setenv("VERTEXAI_PROJECT", "invoice-reconciler-prod")
    monkeypatch.setenv("VERTEXAI_LOCATION", "europe-west4")
    monkeypatch.setenv("PRIMARY_LLM_MODEL", "vertex_ai/gemini-2.5-pro")

    calls: list[dict[str, object]] = []

    class FakeLM:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(llm_router.dspy, "LM", FakeLM)

    lm = llm_router.get_configured_lm()

    assert isinstance(lm, FakeLM)
    assert calls == [
        {
            "model": "vertex_ai/gemini-2.5-pro",
            "max_tokens": 4096,
            "timeout": 30,
            "max_retries": 3,
        }
    ]
    assert os.environ["VERTEXAI_PROJECT"] == "invoice-reconciler-prod"
    assert os.environ["VERTEXAI_LOCATION"] == "europe-west4"


def test_fast_lm_uses_configured_vertex_ai_fast_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "vertex_ai")
    monkeypatch.setenv("VERTEXAI_PROJECT", "invoice-reconciler-prod")
    monkeypatch.setenv("VERTEXAI_LOCATION", "europe-west4")
    monkeypatch.setenv("FAST_LLM_MODEL", "vertex_ai/gemini-2.5-flash")

    calls: list[dict[str, object]] = []

    class FakeLM:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(llm_router.dspy, "LM", FakeLM)

    lm = llm_router.get_fast_lm()

    assert isinstance(lm, FakeLM)
    assert calls == [
        {
            "model": "vertex_ai/gemini-2.5-flash",
            "timeout": 15,
            "max_retries": 2,
        }
    ]
