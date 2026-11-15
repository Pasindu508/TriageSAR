"""Runtime settings, read from the environment. No credentials are ever needed by the API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from triagesar.config import DEFAULT_CONFIG_PATH, REPO_ROOT


@dataclass(frozen=True)
class Settings:
    config_path: Path
    web_dist: Path
    cors_origins: tuple[str, ...]
    max_queue_page: int = 200


def get_settings() -> Settings:
    origins = os.environ.get("TRIAGESAR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return Settings(
        config_path=Path(os.environ.get("TRIAGESAR_CONFIG") or DEFAULT_CONFIG_PATH),
        web_dist=Path(os.environ.get("TRIAGESAR_WEB_DIST") or REPO_ROOT / "apps" / "web" / "dist"),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )
