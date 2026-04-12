"""Tests for LLM provider detection and configuration."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from feinn_agent.providers import (
    detect_provider,
    get_base_url,
    ProviderInfo,
    _PROVIDER_RULES,
    _CONTEXT_LIMITS,
)


class TestProviderDetection:
    """Test provider auto-detection from model names."""

    @pytest.mark.parametrize("model,expected_provider,expected_model", [
        ("anthropic/claude-sonnet-4", "anthropic", "claude-sonnet-4"),
        ("claude-opus-4", "anthropic", "claude-opus-4"),
        ("openai/gpt-4o", "openai", "gpt-4o"),
        ("gpt-4-turbo", "openai", "gpt-4-turbo"),
        ("o1-preview", "openai", "o1-preview"),
        ("gemini/gemini-2.5-pro", "gemini", "gemini-2.5-pro"),
        ("gemini-1.5-pro", "gemini", "gemini-1.5-pro"),
        ("qwen/qwen2.5-72b", "qwen", "qwen2.5-72b"),
        ("deepseek/deepseek-v3", "deepseek", "deepseek-v3"),
        ("moonshot/kimi-k2", "moonshot", "kimi-k2"),
        ("kimi-latest", "moonshot", "kimi-latest"),
        ("ollama/llama3.2", "ollama", "llama3.2"),
        ("vllm/Qwen2.5-72B", "vllm", "Qwen2.5-72B"),
        ("siliconflow/Pro/zai-org/GLM-5.1", "siliconflow", "Pro/zai-org/GLM-5.1"),
        ("lmstudio/llama-3.1", "lmstudio", "llama-3.1"),
        ("custom/my-model", "custom", "my-model"),
    ])
    def test_provider_detection(self, model, expected_provider, expected_model):
        """Test various model name formats."""
        info = detect_provider(model)
        assert info.provider == expected_provider
        assert info.model == expected_model

    def test_unknown_model_defaults_to_custom(self):
        """Test unknown model defaults to custom provider."""
        info = detect_provider("some-random-model")
        assert info.provider == "custom"
        assert info.model == "some-random-model"

    def test_context_limits(self):
        """Test context limits for different providers."""
        test_cases = [
            ("anthropic/claude-opus-4", 200_000),
            ("openai/gpt-4o", 128_000),
            ("gemini/gemini-2.5-pro", 1_000_000),
            ("qwen/qwen2.5-72b", 1_000_000),
            ("deepseek/deepseek-v3", 128_000),
            ("custom/unknown", 128_000),  # Default
        ]

        for model, expected_limit in test_cases:
            info = detect_provider(model)
            assert info.context_limit == expected_limit, f"Failed for {model}"


class TestGetBaseUrl:
    """Test base URL resolution."""

    def test_openai_default(self):
        """Test OpenAI default URL."""
        url = get_base_url("openai", {})
        assert url == "https://api.openai.com/v1"

    def test_anthropic_no_url(self):
        """Test Anthropic doesn't need base URL (native SDK)."""
        url = get_base_url("anthropic", {})
        assert url == ""

    def test_siliconflow_default(self):
        """Test SiliconFlow default URL."""
        url = get_base_url("siliconflow", {})
        assert url == "https://api.siliconflow.cn/v1"

    def test_siliconflow_custom(self):
        """Test SiliconFlow custom URL from config."""
        url = get_base_url("siliconflow", {"siliconflow_base_url": "https://custom.siliconflow.cn/v1"})
        assert url == "https://custom.siliconflow.cn/v1"

    def test_vllm_default(self):
        """Test vLLM default localhost URL."""
        url = get_base_url("vllm", {})
        assert url == "http://localhost:8000/v1"

    def test_vllm_custom(self):
        """Test vLLM custom URL from config."""
        url = get_base_url("vllm", {"vllm_base_url": "http://vllm-cluster:8000/v1"})
        assert url == "http://vllm-cluster:8000/v1"

    def test_azure_from_config(self):
        """Test Azure URL from config."""
        url = get_base_url("azure", {"azure_base_url": "https://my-resource.openai.azure.com/"})
        assert url == "https://my-resource.openai.azure.com/"

    def test_custom_provider(self):
        """Test custom provider URL."""
        url = get_base_url("custom", {"custom_base_url": "https://custom-api.com/v1"})
        assert url == "https://custom-api.com/v1"

    def test_custom_from_env(self, monkeypatch):
        """Test custom provider URL from environment."""
        monkeypatch.setenv("CUSTOM_BASE_URL", "https://env-api.com/v1")
        url = get_base_url("custom", {})
        assert url == "https://env-api.com/v1"


class TestProviderInfo:
    """Test ProviderInfo dataclass."""

    def test_provider_info_creation(self):
        """Test ProviderInfo can be created."""
        info = ProviderInfo(provider="openai", model="gpt-4o", context_limit=128_000)
        assert info.provider == "openai"
        assert info.model == "gpt-4o"
        assert info.context_limit == 128_000
