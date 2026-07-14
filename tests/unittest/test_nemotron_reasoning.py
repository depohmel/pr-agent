from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import pr_agent.algo.ai_handlers.litellm_ai_handler as litellm_handler
from pr_agent.algo import NEMOTRON_REASONING_MODELS


def create_mock_settings(models=None, trigger="detailed thinking on"):
    """Create a fake settings object with configurable Nemotron settings."""
    if models is None:
        models = ["openai/large", "openai/large-reviewer"]
    return type('', (), {
        'config': type('', (), {
            'nemotron_reasoning_models': models,
            'nemotron_reasoning_trigger': trigger,
            'verbosity_level': 0,
            'get': lambda self, key, default=None: default
        })(),
        'litellm': type('', (), {
            'get': lambda self, key, default=None: default
        })(),
        'get': lambda self, key, default=None: default
    })()


@pytest.fixture
def mock_logger():
    """Mock logger to capture info and warning calls."""
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_logger") as mock_log:
        mock_log_instance = MagicMock()
        mock_log.return_value = mock_log_instance
        yield mock_log_instance


def test_nemotron_trigger_applies_to_configured_model(mock_logger):
    """Test that trigger is prepended for configured Nemotron models."""
    fake_settings = create_mock_settings()
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_settings", lambda: fake_settings):
        handler = litellm_handler.LiteLLMAIHandler()
        result = handler._apply_nemotron_trigger("openai/large", "ORIGINAL")

        assert result.startswith("detailed thinking on")
        assert "ORIGINAL" in result
        assert result.count("detailed thinking on") == 1


def test_nemotron_trigger_does_not_apply_to_unconfigured_model(mock_logger):
    """Test that trigger is NOT applied for models not in the configured list."""
    fake_settings = create_mock_settings()
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_settings", lambda: fake_settings):
        handler = litellm_handler.LiteLLMAIHandler()
        result = handler._apply_nemotron_trigger("openai/coder", "ORIGINAL")

        assert result == "ORIGINAL"


def test_nemotron_trigger_idempotent(mock_logger):
    """Test that applying trigger twice doesn't duplicate it."""
    fake_settings = create_mock_settings()
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_settings", lambda: fake_settings):
        handler = litellm_handler.LiteLLMAIHandler()
        # Apply once
        result1 = handler._apply_nemotron_trigger("openai/large", "ORIGINAL")
        # Apply again
        result2 = handler._apply_nemotron_trigger("openai/large", result1)

        assert result1 == result2
        assert result2.count("detailed thinking on") == 1


def test_nemotron_trigger_respects_custom_trigger_text(mock_logger):
    """Test that custom trigger text from config is used."""
    fake_settings = create_mock_settings(trigger="custom trigger")
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_settings", lambda: fake_settings):
        handler = litellm_handler.LiteLLMAIHandler()
        result = handler._apply_nemotron_trigger("openai/large", "ORIGINAL")

        assert result.startswith("custom trigger")
        assert "ORIGINAL" in result


def test_nemotron_trigger_respects_custom_model_list(mock_logger):
    """Test that custom model list from config is used."""
    custom_models = ["custom/nemotron-model"]
    fake_settings = create_mock_settings(models=custom_models)
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_settings", lambda: fake_settings):
        handler = litellm_handler.LiteLLMAIHandler()
        # Model in custom list should get trigger
        result = handler._apply_nemotron_trigger("custom/nemotron-model", "ORIGINAL")
        assert result.startswith("detailed thinking on")
        # Default model should NOT get trigger with custom config
        result2 = handler._apply_nemotron_trigger("openai/large", "ORIGINAL")
        assert result2 == "ORIGINAL"


def test_nemotron_trigger_handles_empty_system_prompt(mock_logger):
    """Test that trigger works with empty system prompt."""
    fake_settings = create_mock_settings()
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_settings", lambda: fake_settings):
        handler = litellm_handler.LiteLLMAIHandler()
        result = handler._apply_nemotron_trigger("openai/large", "")

        assert result == "detailed thinking on\n\n"


def test_nemotron_trigger_handles_none_system_prompt(mock_logger):
    """Test that trigger handles None system prompt gracefully."""
    fake_settings = create_mock_settings()
    with patch("pr_agent.algo.ai_handlers.litellm_ai_handler.get_settings", lambda: fake_settings):
        handler = litellm_handler.LiteLLMAIHandler()
        # None should be treated as empty string
        result = handler._apply_nemotron_trigger("openai/large", None)

        assert result.startswith("detailed thinking on")