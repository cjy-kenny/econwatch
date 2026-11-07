"""Lightweight app configuration (~/.econwatch/config.json). Stdlib only.

Kept separate from data_fetcher so the GUI can read/write settings before the
heavy pandas/matplotlib imports are warmed up.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".econwatch" / "config.json"


def load_config() -> dict:
    """Read ~/.econwatch/config.json; {} when missing or corrupt."""
    if CONFIG_PATH.is_file():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """Write ~/.econwatch/config.json."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_api_key() -> str | None:
    """FRED key: FRED_API_KEY env var first, then ~/.econwatch/config.json."""
    key = os.getenv("FRED_API_KEY")
    if key and key.strip():
        return key.strip()
    key = load_config().get("fred_api_key")
    if key and str(key).strip():
        return str(key).strip()
    return None


def save_api_key(key: str) -> None:
    """Persist the FRED key in ~/.econwatch/config.json; an empty key clears it."""
    config = load_config()
    key = key.strip()
    if key:
        config["fred_api_key"] = key
    else:
        config.pop("fred_api_key", None)
    save_config(config)
