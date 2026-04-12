"""FeinnAgent configuration management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .types import PermissionMode

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv

    _dotenv_loaded = False
    for _dotenv_path in [Path(".env"), Path.home() / ".feinn" / ".env"]:
        if _dotenv_path.exists():
            load_dotenv(_dotenv_path)
            _dotenv_loaded = True
            break
except ImportError:
    pass  # python-dotenv not installed

_DEFAULTS: dict[str, Any] = {
    "model": "anthropic/claude-sonnet-4-20250514",
    "max_tokens": 16384,
    "max_iterations": 50,
    "permission_mode": PermissionMode.ACCEPT_ALL.value,
    "compaction_threshold": 0.70,
    "compaction_preserve_last_n": 6,
    "max_tool_output_chars": 32_000,
    "max_concurrent_agents": 5,
    "max_agent_depth": 3,
    "thinking_enabled": False,
    "thinking_budget": 10_000,
    "server_host": "0.0.0.0",
    "server_port": 8000,
    "log_level": "INFO",
    "log_file": None,  # Path to log file (e.g., "~/.feinn/feinn.log")
}

_ENV_MAP: dict[str, str] = {
    "model": "DEFAULT_MODEL",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "dashscope_api_key": "DASHSCOPE_API_KEY",
    "moonshot_api_key": "MOONSHOT_API_KEY",
    "siliconflow_api_key": "SILICONFLOW_API_KEY",
    "siliconflow_base_url": "SILICONFLOW_BASE_URL",
    "azure_api_key": "AZURE_OPENAI_API_KEY",
    "azure_base_url": "AZURE_OPENAI_URL",
    "vllm_api_key": "VLLM_API_KEY",
    "vllm_base_url": "VLLM_BASE_URL",
    "custom_api_key": "CUSTOM_API_KEY",
    "custom_base_url": "CUSTOM_BASE_URL",
}


def _config_dir() -> Path:
    """Return the FeinnAgent config directory, respecting FEINN_HOME."""
    home = os.environ.get("FEINN_HOME", str(Path.home() / ".feinn"))
    return Path(home)


def _config_file() -> Path:
    return _config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Load configuration: defaults → file → env vars."""
    cfg = dict(_DEFAULTS)

    # Layer 2: config file
    path = _config_file()
    if path.exists():
        try:
            file_cfg = json.loads(path.read_text(encoding="utf-8"))
            cfg.update(file_cfg)
        except (json.JSONDecodeError, OSError):
            pass

    # Layer 3: environment variables override
    for key, env_var in _ENV_MAP.items():
        val = os.environ.get(env_var)
        if val:
            cfg[key] = val

    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """Persist configuration to disk, skipping internal keys."""
    path = _config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in cfg.items() if not k.startswith("_")}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_api_key(provider: str, config: dict[str, Any]) -> str:
    """Resolve API key for a provider: config → env var → empty."""
    key = config.get(f"{provider}_api_key", "")
    if key:
        return key
    env_var = _ENV_MAP.get(f"{provider}_api_key", "")
    return os.environ.get(env_var, "") if env_var else ""


def setup_logging(config: dict[str, Any]) -> None:
    """Setup logging with optional file output."""
    import logging
    import sys

    log_level = config.get("log_level", "INFO")
    log_file = config.get("log_file")

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
