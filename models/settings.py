"""Persistent application settings (stored in the user's app-data folder).

Holds the default directory that file browsers open to, plus a flag marking
whether first-run setup has been completed.
"""

import os
import json

APP_NAME = "XRF-CF-GUI"


def _config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def _config_path() -> str:
    return os.path.join(_config_dir(), "config.json")


def load_settings() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError):
        pass
    return {}


def save_settings(settings: dict) -> None:
    os.makedirs(_config_dir(), exist_ok=True)
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def is_configured() -> bool:
    return bool(load_settings().get("configured"))


def get_default_dir() -> str:
    d = load_settings().get("default_dir", "")
    if d and os.path.isdir(d):
        return d
    return os.path.expanduser("~")


def set_default_dir(path: str) -> None:
    s = load_settings()
    s["default_dir"] = path
    s["configured"] = True
    save_settings(s)
