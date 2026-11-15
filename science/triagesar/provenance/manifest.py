"""Provenance manifest schema for a demo fixture, plus checksum helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MANIFEST_VERSION = "1.0"
MANIFEST_NAME = "manifest.json"
DataKind = Literal["nasa_nisar_gunw", "synthetic_test"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventInfo(_Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    title: str
    summary: str
    event_time_utc: str | None = None
    event_source_name: str | None = None
    event_source_url: str | None = None
    notes: list[str] = Field(default_factory=list)


class SourceInfo(_Model):
    granule_id: str | None
    file_name: str
    collection: str | None = None
    concept_id: str | None = None
    provider: str | None = None
    download_url: str | None = None
    source_size_bytes: int | None = None
    product_version: str | None = None
    product_type: str | None = None
    processing_datetime: str | None = None
    software_version: str | None = None
    track_number: int | str | None = None
    frame_number: int | str | None = None
    orbit_pass_direction: str | None = None
    look_direction: str | None = None
    identification: dict[str, Any] = Field(default_factory=dict)
    identification_paths: dict[str, str] = Field(default_factory=dict)


class AcquisitionInfo(_Model):
    reference_start_utc: str | None
    reference_end_utc: str | None = None
    secondary_start_utc: str | None
    secondary_end_utc: str | None = None


class RadarInfo(_Model):
    wavelength_m: float
    center_frequency_hz: float | None
    derivation: str
    source_hdf5_path: str
    frequency: str | None
    polarisation: str | None


class AoiInfo(_Model):
    bbox_wgs84_requested: tuple[float, float, float, float]
    row_start: int
    row_stop: int
    col_start: int
    col_stop: int
    source_height: int
    source_width: int


class GridInfo(_Model):
    epsg: int | None
    wkt: str
    transform: tuple[float, float, float, float, float, float]
    width: int
    height: int


class LayerInfo(_Model):
    file: str
    hdf5_path: str
    dtype: str
    units: str | None
    fill_value: float | None
    #: True when the source layer uses NaN as its fill value (JSON cannot carry NaN).
    fill_value_is_nan: bool = False
    description: str | None = None
    sha256: str
    bytes: int


class CorrectionInfo(_Model):
    available_layers: list[str]
    applied: list[str] = Field(default_factory=list)
    statement: str


class BuildInfo(_Model):
    command: str
    built_at_utc: str
    app_version: str
    tool_versions: dict[str, str]


class FixtureManifest(_Model):
    manifest_version: str = MANIFEST_VERSION
    data_kind: DataKind
    event: EventInfo
    source: SourceInfo
    acquisition: AcquisitionInfo
    radar: RadarInfo
    aoi: AoiInfo
    grid: GridInfo
    layers: dict[str, LayerInfo]
    corrections: CorrectionInfo
    transformations: list[str]
    build: BuildInfo


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(manifest: FixtureManifest, directory: Path) -> Path:
    path = Path(directory) / MANIFEST_NAME
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return path


def read_manifest(directory: Path) -> FixtureManifest:
    path = Path(directory) / MANIFEST_NAME
    if not path.exists():
        raise FileNotFoundError(f"No fixture manifest at {path}")
    return FixtureManifest.model_validate_json(path.read_text(encoding="utf-8"))


def verify_checksums(directory: Path) -> list[str]:
    """Return a list of problems (empty = every layer file matches its recorded SHA-256)."""
    manifest = read_manifest(directory)
    problems: list[str] = []
    for name, layer in manifest.layers.items():
        file_path = Path(directory) / layer.file
        if not file_path.exists():
            problems.append(f"{name}: missing file {layer.file}")
            continue
        actual = sha256_file(file_path)
        if actual != layer.sha256:
            problems.append(f"{name}: checksum mismatch for {layer.file} (expected {layer.sha256[:12]}…, got {actual[:12]}…)")
    return problems
