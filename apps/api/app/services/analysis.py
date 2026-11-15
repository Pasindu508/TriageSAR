"""Runs the science pipeline once per event and caches the result in memory.

The public API only ever reads the prepared fixture. It never downloads NASA data.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.settings import get_settings
from app.models.errors import ConfigurationInvalid, FixtureInvalid, FixtureNotBuilt
from triagesar.config import AnalysisConfig, load_config
from triagesar.events import EventEntry
from triagesar.fixture import Fixture, load_fixture
from triagesar.infrastructure.osm import Road, load_roads
from triagesar.pipeline import AnalysisArtifacts, ablation_summary, run_analysis
from triagesar.provenance.manifest import MANIFEST_NAME, FixtureManifest
from triagesar.render import Overlays, render_overlays


@dataclass
class EventAnalysis:
    fixture: Fixture
    roads: list[Road]
    config: AnalysisConfig
    artifacts: AnalysisArtifacts
    overlays: Overlays | None = None
    ablation: dict[str, Any] | None = None
    overlay_lock: threading.Lock = field(default_factory=threading.Lock)
    thumbnails: dict[str, bytes] = field(default_factory=dict)
    ablation_lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def manifest(self) -> FixtureManifest:
        return self.fixture.manifest


_cache: dict[tuple[str, str, float, float, float], EventAnalysis] = {}
_lock = threading.Lock()


def build_command(entry: EventEntry) -> str | None:
    if entry.data_kind == "synthetic_test":
        return "python scripts/make_synthetic_fixture.py"
    return f"python scripts/build_demo_fixture.py --event {entry.id}"


def status_of(entry: EventEntry) -> tuple[str, str]:
    if not entry.fixture_ready:
        return (
            "fixture_not_built",
            "The real-data fixture for this event has not been built on this machine yet. "
            "No observations are shown rather than showing placeholder values.",
        )
    if not entry.roads_path.is_file():
        return ("roads_missing", "The cached OpenStreetMap road extract for this event is missing.")
    return ("ready", "Fixture and road extract are available.")


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def load_app_config() -> AnalysisConfig:
    try:
        return load_config(get_settings().config_path)
    except ValueError as exc:
        raise ConfigurationInvalid(f"The analysis configuration is invalid: {exc}") from exc


def get_analysis(entry: EventEntry) -> EventAnalysis:
    if not entry.fixture_ready:
        raise FixtureNotBuilt(status_of(entry)[1], hint=build_command(entry))
    settings = get_settings()
    key = (
        entry.id,
        str(entry.nisar_dir),
        _mtime(entry.nisar_dir / MANIFEST_NAME),
        _mtime(entry.roads_path),
        _mtime(settings.config_path),
    )
    with _lock:
        cached = _cache.get(key)
        if cached is not None:
            return cached
        config = load_app_config()
        try:
            fixture = load_fixture(entry.nisar_dir)
            roads = load_roads(entry.roads_path) if entry.roads_path.is_file() else []
        except (OSError, ValueError) as exc:
            raise FixtureInvalid(f"The fixture for {entry.id} could not be read: {exc}") from exc
        analysis = EventAnalysis(fixture, roads, config, run_analysis(fixture, roads, config))
        for stale in [k for k in _cache if k[0] == entry.id]:
            del _cache[stale]
        _cache[key] = analysis
        return analysis


def get_overlays(analysis: EventAnalysis) -> Overlays:
    with analysis.overlay_lock:
        if analysis.overlays is None:
            art = analysis.artifacts
            local = art.analysis_m if art.analysis_m is not art.relative_m else None
            analysis.overlays = render_overlays(
                art.grid, art.relative_m, art.quality_state, local, art.result.threshold.threshold_m
            )
        return analysis.overlays


def get_ablation(analysis: EventAnalysis) -> dict[str, Any]:
    with analysis.ablation_lock:
        if analysis.ablation is None:
            unmasked = run_analysis(analysis.fixture, analysis.roads, analysis.config, apply_quality_mask=False)
            analysis.ablation = ablation_summary(analysis.artifacts.result, unmasked.result)
        return analysis.ablation


def clear_cache() -> None:
    with _lock:
        _cache.clear()
