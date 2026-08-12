from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - Python < 3.11
    raise RuntimeError("Universal Search Skill requires Python 3.11+") from exc


@dataclass
class Settings:
    provider: str = "auto"
    mode: str = "auto"
    max_results: int = 8
    max_chars_total: int = 12000
    timeout_seconds: float = 30.0
    fallback: bool = True

    parallel_api_key_env: str = "PARALLEL_API_KEY"
    parallel_base_url: str = "https://api.parallel.ai/v1/search"

    openrouter_api_key_env: str = "OPENROUTER_API_KEY"
    openrouter_base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    openrouter_model: str = "~openai/gpt-latest"
    openrouter_engine: str = "parallel"
    openrouter_app_title: str = "Universal Search Skill"
    openrouter_http_referer: str | None = None

    @property
    def parallel_api_key(self) -> str | None:
        return _clean(os.getenv(self.parallel_api_key_env))

    @property
    def openrouter_api_key(self) -> str | None:
        return _clean(os.getenv(self.openrouter_api_key_env))


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


def discover_config(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path

    env_path = _clean(os.getenv("UNIVERSAL_SEARCH_CONFIG"))
    if env_path:
        return Path(env_path).expanduser()

    cwd = Path.cwd() / "config.toml"
    if cwd.exists():
        return cwd

    return None


def load_settings(config_path: str | None = None) -> Settings:
    settings = Settings()
    path = discover_config(config_path)

    data: dict[str, Any] = {}
    if path:
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open("rb") as fh:
            data = tomllib.load(fh)

    search = _section(data, "search")
    parallel = _section(data, "parallel")
    openrouter = _section(data, "openrouter")

    settings.provider = str(search.get("provider", settings.provider))
    settings.mode = str(search.get("mode", settings.mode))
    settings.max_results = int(search.get("max_results", settings.max_results))
    settings.max_chars_total = int(search.get("max_chars_total", settings.max_chars_total))
    settings.timeout_seconds = float(search.get("timeout_seconds", settings.timeout_seconds))
    settings.fallback = bool(search.get("fallback", settings.fallback))

    settings.parallel_api_key_env = str(parallel.get("api_key_env", settings.parallel_api_key_env))
    settings.parallel_base_url = str(parallel.get("base_url", settings.parallel_base_url))

    settings.openrouter_api_key_env = str(openrouter.get("api_key_env", settings.openrouter_api_key_env))
    settings.openrouter_base_url = str(openrouter.get("base_url", settings.openrouter_base_url))
    settings.openrouter_model = str(openrouter.get("model", settings.openrouter_model))
    settings.openrouter_engine = str(openrouter.get("engine", settings.openrouter_engine))
    settings.openrouter_app_title = str(openrouter.get("app_title", settings.openrouter_app_title))
    settings.openrouter_http_referer = _clean(openrouter.get("http_referer"))

    # Environment overrides for frequently changed values.
    settings.openrouter_model = _clean(os.getenv("OPENROUTER_MODEL")) or settings.openrouter_model
    settings.openrouter_engine = _clean(os.getenv("OPENROUTER_SEARCH_ENGINE")) or settings.openrouter_engine

    return settings
