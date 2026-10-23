from __future__ import annotations

import re
import secrets
import tomllib
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, SecretStr

_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ProviderName(StrEnum):
    MOCK = "mock"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    XAI = "xai"


API_KEY_ENV: Final[dict[ProviderName, str]] = {
    ProviderName.ANTHROPIC: "ANTHROPIC_API_KEY",
    ProviderName.OPENAI: "OPENAI_API_KEY",
    ProviderName.GEMINI: "GEMINI_API_KEY",
    ProviderName.XAI: "XAI_API_KEY",
}


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    root: Path
    provider: ProviderName
    model: str
    api_key: SecretStr | None
    xai_base_url: str
    site_path: Path
    vehicles_path: Path
    db_url: str
    max_repairs: int = Field(ge=0, le=5)
    history_turns: int = Field(ge=1, le=50)
    confirm_ttl_s: int = Field(ge=30, le=3600)
    request_timeout_s: float = Field(gt=0, le=120)
    sdk_max_retries: int = Field(ge=0, le=3)
    operation_timeout_s: float = Field(gt=0, le=300)
    provider_concurrency: int = Field(ge=1, le=32)
    max_output_tokens: int = Field(ge=256, le=8192)
    max_body_bytes: int
    max_message_chars: int
    max_history_chars: int
    max_output_text_chars: int
    max_tool_args_bytes: int
    allowed_hosts: tuple[str, ...]
    instance_nonce: str

    def __repr__(self) -> str:
        return (
            f"AppSettings(provider={self.provider!r}, model={self.model!r}, "
            f"root={self.root!r}, api_key={'***' if self.api_key else None})"
        )


class SettingsError(Exception):
    pass


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise SettingsError(f"{path} line {line_no}: expected KEY=VALUE")
        key_part, value_part = line.split("=", 1)
        key = key_part.strip()
        if not _KEY_PATTERN.match(key):
            raise SettingsError(f"{path} line {line_no}: invalid key")
        value = value_part.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            if " #" in value:
                value = value.split(" #", 1)[0].rstrip()
        if key in result:
            raise SettingsError(f"{path} line {line_no}: duplicate key {key}")
        result[key] = value
    return result


def _resolve_path(root: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (root / p).resolve()


def _resolve_db_url(root: Path, url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url
    path_part = url[len("sqlite:///") :]
    if path_part.startswith("/"):
        return url
    resolved = (root / path_part).resolve()
    return f"sqlite:///{resolved}"


def load_settings(
    env: Mapping[str, str] | None = None,
    *,
    dotenv_enabled: bool = True,
) -> AppSettings:
    import os

    merged: dict[str, str] = dict(os.environ)
    if env is not None:
        merged.update(env)

    root_raw = merged.get("RCC_ROOT")
    root = Path(root_raw).resolve() if root_raw else _default_root()

    dotenv_path_raw = merged.get("RCC_DOTENV", str(root / ".env"))
    if dotenv_enabled and dotenv_path_raw.lower() != "off":
        dotenv_path = Path(dotenv_path_raw)
        if not dotenv_path.is_absolute():
            dotenv_path = root / dotenv_path
        for k, v in read_dotenv(dotenv_path).items():
            merged.setdefault(k, v)

    config_path_raw = merged.get("RCC_CONFIG", str(root / "config" / "app.toml"))
    config_path = Path(config_path_raw)
    if not config_path.is_absolute():
        config_path = root / config_path
    if not config_path.is_file():
        raise SettingsError(f"config file not found: {config_path}")

    with config_path.open("rb") as f:
        cfg = tomllib.load(f)

    defaults = cfg.get("defaults", {})
    llm = cfg.get("llm", {})
    limits = cfg.get("limits", {})
    server = cfg.get("server", {})
    models = cfg.get("models", {})
    endpoints = cfg.get("endpoints", {})
    max_tokens_table = cfg.get("max_output_tokens", {})

    provider_raw = merged.get("RCC_PROVIDER", defaults.get("provider", "mock"))
    try:
        provider = ProviderName(provider_raw.lower())
    except ValueError as exc:
        raise SettingsError(f"unknown RCC_PROVIDER: {provider_raw}") from exc

    model = merged.get("RCC_MODEL") or models.get(provider.value)
    if not model:
        raise SettingsError(f"no model configured for provider {provider.value}")

    api_key: SecretStr | None = None
    if provider != ProviderName.MOCK:
        env_name = API_KEY_ENV[provider]
        key_val = merged.get(env_name)
        if not key_val:
            raise SettingsError(f"missing required environment variable {env_name}")
        api_key = SecretStr(key_val)

    site_path = _resolve_path(
        root, merged.get("RCC_SITE", defaults.get("site", "config/sites/demo_farm.toml"))
    )
    vehicles_path = _resolve_path(
        root,
        merged.get("RCC_VEHICLES", defaults.get("vehicles", "config/vehicles.toml")),
    )
    db_url = _resolve_db_url(
        root, merged.get("RCC_DB_URL", defaults.get("db_url", "sqlite:///data/rcc.db"))
    )

    max_repairs = int(merged.get("RCC_MAX_REPAIRS", defaults.get("max_repairs", 2)))
    history_turns = int(defaults.get("history_turns", 10))
    confirm_ttl_s = int(defaults.get("confirm_ttl_s", 600))

    max_output_tokens = int(max_tokens_table.get(provider.value, 2048))

    allowed = tuple(server.get("allowed_hosts", ["localhost", "127.0.0.1"]))
    instance_nonce = merged.get("RCC_INSTANCE_NONCE") or secrets.token_hex(8)

    return AppSettings(
        root=root,
        provider=provider,
        model=model,
        api_key=api_key,
        xai_base_url=str(endpoints.get("xai_base_url", "https://api.x.ai/v1")),
        site_path=site_path,
        vehicles_path=vehicles_path,
        db_url=db_url,
        max_repairs=max_repairs,
        history_turns=history_turns,
        confirm_ttl_s=confirm_ttl_s,
        request_timeout_s=float(llm.get("request_timeout_s", 30)),
        sdk_max_retries=int(llm.get("sdk_max_retries", 1)),
        operation_timeout_s=float(llm.get("operation_timeout_s", 75)),
        provider_concurrency=int(llm.get("provider_concurrency", 4)),
        max_output_tokens=max_output_tokens,
        max_body_bytes=int(limits.get("max_body_bytes", 16384)),
        max_message_chars=int(limits.get("max_message_chars", 2000)),
        max_history_chars=int(limits.get("max_history_chars", 16000)),
        max_output_text_chars=int(limits.get("max_output_text_chars", 4000)),
        max_tool_args_bytes=int(limits.get("max_tool_args_bytes", 32768)),
        allowed_hosts=allowed,
        instance_nonce=instance_nonce,
    )
