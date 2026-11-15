"""API test fixtures. Uses the TEST ONLY synthetic event and an empty real-data registry."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.synthetic import build_synthetic_event
from triagesar.config import DEFAULT_CONFIG_PATH, REPO_ROOT


@pytest.fixture(scope="session")
def synthetic_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("api-synthetic")
    build_synthetic_event(root)
    return root


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    """A real-data registry whose Venezuela fixture has NOT been built (roads only)."""
    base = tmp_path / "fixtures"
    base.mkdir()
    registry = json.loads((REPO_ROOT / "data" / "fixtures" / "demo_manifest.json").read_text(encoding="utf-8"))
    registry["events"] = [e for e in registry["events"] if e["id"] == "venezuela-2026-06-24"]
    (base / "demo_manifest.json").write_text(json.dumps(registry), encoding="utf-8")
    return base


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, synthetic_dir: Path, data_dir: Path, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIAGESAR_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TRIAGESAR_SYNTHETIC_DIR", str(synthetic_dir))
    monkeypatch.setenv("TRIAGESAR_INCLUDE_SYNTHETIC", "1")
    monkeypatch.setenv("TRIAGESAR_CONFIG", str(DEFAULT_CONFIG_PATH))
    monkeypatch.setenv("TRIAGESAR_WEB_DIST", str(tmp_path / "no-dist"))
    for name in ("EARTHDATA_TOKEN", "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    from app.main import create_app
    from app.services.analysis import clear_cache

    clear_cache()
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c
    clear_cache()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
