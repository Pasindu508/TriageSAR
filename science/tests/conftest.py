"""Shared fixtures. All data created here are TEST ONLY synthetic values."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.synthetic import build_synthetic_event, write_synthetic_gunw
from triagesar.config import AnalysisConfig, load_config
from triagesar.fixture import Fixture, load_fixture
from triagesar.infrastructure.osm import Road, load_roads


@pytest.fixture(scope="session")
def synthetic_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synthetic")
    build_synthetic_event(root)
    return root


@pytest.fixture(scope="session")
def synthetic_h5(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_synthetic_gunw(tmp_path_factory.mktemp("h5") / "TEST_ONLY.h5")


@pytest.fixture(scope="session")
def fixture(synthetic_root: Path) -> Fixture:
    return load_fixture(synthetic_root / "nisar" / "synthetic-test-event")


@pytest.fixture(scope="session")
def roads(synthetic_root: Path) -> list[Road]:
    return load_roads(synthetic_root / "infrastructure" / "synthetic-test-event" / "roads.geojson")


@pytest.fixture(scope="session")
def config() -> AnalysisConfig:
    return load_config()
