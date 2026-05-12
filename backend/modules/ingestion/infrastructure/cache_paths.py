from __future__ import annotations

import os
import sys
from pathlib import Path


APP_CACHE_DIR_NAME = "pitwall-insights"


def resolve_provider_cache_dir(
    provider_name: str,
    configured_dir: str | None = None,
) -> Path:
    if configured_dir:
        expanded = Path(os.path.expandvars(os.path.expanduser(configured_dir)))
        if expanded.is_absolute():
            return expanded.resolve()
        return (_default_app_cache_root() / expanded).resolve()

    return (_default_app_cache_root() / provider_name).resolve()


def _default_app_cache_root() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_CACHE_DIR_NAME
        return Path.home() / "AppData" / "Local" / APP_CACHE_DIR_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / APP_CACHE_DIR_NAME

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / APP_CACHE_DIR_NAME
    return Path.home() / ".cache" / APP_CACHE_DIR_NAME
