"""Tests for configuration management."""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from feinn_agent.config import (
    load_config,
    save_config,
    get_api_key,
    setup_logging,
    _config_dir,
    _config_file,
    _DEFAULTS,
)
from feinn_agent.types import PermissionMode


class TestConfigLoading:
    """Test configuration loading from various sources."""

    def test_load_defaults(self):
        """Test that defaults are loaded correctly."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, "exists", return_value=False):
                cfg = load_config()
                assert cfg["model"] == _DEFAULTS["model"]
                assert cfg["max_iterations"] == 50
                assert cfg["permission_mode"] == PermissionMode.ACCEPT_ALL.value

    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("DEFAULT_MODEL", "openai/gpt-4o")
        monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test-key")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        cfg = load_config()
        assert cfg["model"] == "openai/gpt-4o"
        assert cfg["siliconflow_api_key"] == "sk-test-key"
        assert cfg["log_level"] == "DEBUG"

    def test_config_file_override(self, tmp_path):
        """Test config file loading."""
        config_data = {"model": "anthropic/claude-sonnet-4", "max_tokens": 8192}

        with patch("feinn_agent.config._config_file", return_value=tmp_path / "config.json"):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=json.dumps(config_data)):
                    cfg = load_config()
                    assert cfg["model"] == "anthropic/claude-sonnet-4"
                    assert cfg["max_tokens"] == 8192

    def test_env_beats_file(self, tmp_path, monkeypatch):
        """Test that env vars override config file."""
        monkeypatch.setenv("DEFAULT_MODEL", "openai/gpt-4o-mini")

        config_data = {"model": "anthropic/claude-sonnet-4"}

        with patch("feinn_agent.config._config_file", return_value=tmp_path / "config.json"):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=json.dumps(config_data)):
                    cfg = load_config()
                    assert cfg["model"] == "openai/gpt-4o-mini"

    def test_invalid_config_file(self, tmp_path):
        """Test handling of invalid config file."""
        with patch("feinn_agent.config._config_file", return_value=tmp_path / "config.json"):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value="invalid json"):
                    cfg = load_config()
                    assert cfg["model"] == _DEFAULTS["model"]  # Falls back to defaults


class TestGetApiKey:
    """Test API key resolution."""

    def test_from_config(self):
        """Test getting API key from config."""
        config = {"openai_api_key": "sk-from-config"}
        assert get_api_key("openai", config) == "sk-from-config"

    def test_from_env(self, monkeypatch):
        """Test getting API key from environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        config = {}
        assert get_api_key("anthropic", config) == "sk-from-env"

    def test_config_priority(self, monkeypatch):
        """Test that config takes priority over env."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        config = {"openai_api_key": "sk-from-config"}
        assert get_api_key("openai", config) == "sk-from-config"

    def test_missing_key(self):
        """Test behavior when key is missing."""
        config = {}
        assert get_api_key("nonexistent", config) == ""


class TestSaveConfig:
    """Test configuration persistence."""

    def test_save_config(self, tmp_path):
        """Test saving config to file."""
        cfg = {"model": "test-model", "custom_key": "value"}

        with patch("feinn_agent.config._config_file", return_value=tmp_path / "config.json"):
            save_config(cfg)

            saved_file = tmp_path / "config.json"
            assert saved_file.exists()

            saved_data = json.loads(saved_file.read_text())
            assert saved_data["model"] == "test-model"
            assert saved_data["custom_key"] == "value"

    def test_save_excludes_internal_keys(self, tmp_path):
        """Test that internal keys are not saved."""
        cfg = {"model": "test", "_internal": "secret"}

        with patch("feinn_agent.config._config_file", return_value=tmp_path / "config.json"):
            save_config(cfg)

            saved_file = tmp_path / "config.json"
            saved_data = json.loads(saved_file.read_text())
            assert "_internal" not in saved_data


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_logging_console_only(self):
        """Test logging to console only."""
        config = {"log_level": "INFO", "log_file": None}
        setup_logging(config)  # Should not raise

    def test_setup_logging_with_file(self, tmp_path):
        """Test logging to file."""
        log_file = tmp_path / "test.log"
        config = {"log_level": "DEBUG", "log_file": str(log_file)}
        setup_logging(config)

        # Log file should be created
        assert log_file.parent.exists()

    def test_setup_logging_creates_parent_dir(self, tmp_path):
        """Test that parent directory is created for log file."""
        log_file = tmp_path / "subdir" / "test.log"
        config = {"log_level": "INFO", "log_file": str(log_file)}
        setup_logging(config)

        assert log_file.parent.exists()
