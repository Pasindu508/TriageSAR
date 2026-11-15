"""Build and load the offline demo fixture: a value-preserving crop of one GUNW product.

``build_fixture`` reads a window from a real NISAR GUNW HDF5 file (local path, or
remote URL read through HTTP range requests so the multi-gigabyte file never has
to be stored) and writes each layer, bit-for-bit, to a lossless GeoTIFF together
with a provenance manifest and SHA-256 checksums.
"""

from __future__ import annotations

import datetime as dt
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import rasterio
from pyproj import CRS

from . import __version__
from .nisar import hdf5_reader
from .nisar.metadata import read_metadata
from .nisar.schema import CanonicalLayers
from .processing.georeference import GridGeometry, grid_from_coordinates, window_for_bbox
from .provenance.manifest import (
    AcquisitionInfo,
    AoiInfo,
    BuildInfo,
    CorrectionInfo,
    DataKind,
    EventInfo,
    FixtureManifest,
    GridInfo,
    LayerInfo,
    RadarInfo,
    SourceInfo,
    read_manifest,
    sha256_file,
    write_manifest,
)

CORRECTION_STATEMENT = (
    "TriageSAR applies no ionospheric, tropospheric or solid-Earth-tide correction to the unwrapped phase. "
    "Correction layers listed as available ship with the product and are left untouched."
)
MAX_FIXTURE_PIXELS = 6_000_000  # keeps the fixture small enough for git


def open_gunw(source: str, token: str | None = None) -> h5py.File:
    """Open a GUNW file from a local path or an https URL (HTTP range reads, bearer token)."""
    if source.startswith(("https://", "http://")):
        if not source.startswith("https://"):
            raise ValueError("Remote products must be read over https")
        import fsspec

        headers = {"Authorization": f"Bearer {token}"} if token else {}
        fs = fsspec.filesystem("https", client_kwargs={"headers": headers, "trust_env": True})
        fobj = fs.open(source, mode="rb", block_size=8 * 1024 * 1024, cache_type="blockcache")
        return h5py.File(fobj, "r")
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"GUNW file not found: {path}")
    return h5py.File(path, "r")


def _crs_from(layers: CanonicalLayers) -> CRS:
    if layers.grid.epsg is not None:
        return CRS.from_epsg(layers.grid.epsg)
    return CRS.from_wkt(layers.grid.wkt or "")


def _write_geotiff(path: Path, array: np.ndarray, grid: GridGeometry, nodata: float | None) -> None:
    profile: dict[str, Any] = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": array.dtype.name,
        "crs": grid.crs.to_wkt(),
        "transform": grid.transform,
        "compress": "deflate",
        "predictor": 3 if array.dtype.kind == "f" else 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    if nodata is not None and np.isfinite(nodata):
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)


def build_fixture(
    source: str,
    out_dir: Path,
    bbox_wgs84: tuple[float, float, float, float],
    event: EventInfo,
    command: str,
    data_kind: DataKind = "nasa_nisar_gunw",
    token: str | None = None,
    frequency: str | None = None,
    polarisation: str | None = None,
    source_overrides: dict[str, Any] | None = None,
) -> FixtureManifest:
    """Crop a GUNW product to ``bbox_wgs84`` and write the fixture. Values are not modified."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    transformations: list[str] = []
    with open_gunw(source, token) as h5:
        layers = hdf5_reader.discover_layers(h5, frequency=frequency, polarisation=polarisation)
        meta = read_metadata(h5)
        crs = _crs_from(layers)
        x, y = hdf5_reader.read_coordinates(h5, layers.grid)
        rows, cols = window_for_bbox(x, y, crs, bbox_wgs84)
        n_pixels = (rows.stop - rows.start) * (cols.stop - cols.start)
        if n_pixels > MAX_FIXTURE_PIXELS:
            raise ValueError(
                f"AOI covers {n_pixels:,} pixels; the fixture limit is {MAX_FIXTURE_PIXELS:,}. Choose a smaller bbox."
            )
        xs, ys = x[cols], y[rows]
        flip = bool(ys[1] > ys[0])
        if flip:
            ys = ys[::-1]
            transformations.append("Rows reversed so the grid is north-up (lossless reordering).")
        grid = grid_from_coordinates(xs, ys, crs)
        transformations.insert(
            0,
            f"Cropped to rows {rows.start}:{rows.stop}, columns {cols.start}:{cols.stop} of the "
            f"{layers.grid.height} x {layers.grid.width} source grid (pixel centres inside the requested bbox).",
        )
        layer_infos: dict[str, LayerInfo] = {}
        for name, ref in sorted(layers.layers.items()):
            data = hdf5_reader.read_window(h5, ref, rows, cols)
            if flip:
                data = data[::-1, :]
            data = np.ascontiguousarray(data)
            file_name = f"{name}.tif"
            _write_geotiff(out_dir / file_name, data, grid, ref.fill_value)
            layer_infos[name] = LayerInfo(
                file=file_name,
                hdf5_path=ref.hdf5_path,
                dtype=ref.dtype,
                units=ref.units,
                fill_value=ref.fill_value if (ref.fill_value is not None and np.isfinite(ref.fill_value)) else None,
                fill_value_is_nan=bool(ref.fill_value is not None and np.isnan(ref.fill_value)),
                description=ref.description,
                sha256=sha256_file(out_dir / file_name),
                bytes=(out_dir / file_name).stat().st_size,
            )
        transformations.append(
            "Each layer written unchanged (same dtype, no scaling, no resampling, no interpolation) to a "
            "DEFLATE-compressed GeoTIFF in the product's native CRS."
        )

    file_name = source.rsplit("/", 1)[-1].split("?", 1)[0]
    src_fields: dict[str, Any] = {
        "granule_id": meta.get("granule_id") or file_name.removesuffix(".h5"),
        "file_name": file_name,
        "download_url": source if source.startswith("https://") else None,
        "product_version": _opt_str(meta.get("product_version")),
        "product_type": _opt_str(meta.get("product_type")),
        "processing_datetime": _opt_str(meta.get("processing_datetime")),
        "software_version": meta.software_version,
        "track_number": meta.get("track_number"),
        "frame_number": meta.get("frame_number"),
        "orbit_pass_direction": _opt_str(meta.get("orbit_pass_direction")),
        "look_direction": _opt_str(meta.get("look_direction")),
        "identification": {k: v for k, v in meta.fields.items() if k != "bounding_polygon"},
        "identification_paths": meta.source_paths,
    }
    src_fields.update(source_overrides or {})
    manifest = FixtureManifest(
        data_kind=data_kind,
        event=event,
        source=SourceInfo(**src_fields),
        acquisition=AcquisitionInfo(
            reference_start_utc=_opt_str(meta.get("reference_start_time")),
            reference_end_utc=_opt_str(meta.get("reference_end_time")),
            secondary_start_utc=_opt_str(meta.get("secondary_start_time")),
            secondary_end_utc=_opt_str(meta.get("secondary_end_time")),
        ),
        radar=RadarInfo(
            wavelength_m=layers.wavelength.wavelength_m,
            center_frequency_hz=layers.wavelength.center_frequency_hz,
            derivation=layers.wavelength.derivation,
            source_hdf5_path=layers.wavelength.source_path,
            frequency=layers.frequency,
            polarisation=layers.polarisation,
        ),
        aoi=AoiInfo(
            bbox_wgs84_requested=bbox_wgs84,
            row_start=rows.start,
            row_stop=rows.stop,
            col_start=cols.start,
            col_stop=cols.stop,
            source_height=layers.grid.height,
            source_width=layers.grid.width,
        ),
        grid=GridInfo(
            epsg=layers.grid.epsg,
            wkt=grid.crs.to_wkt(),
            transform=tuple(grid.transform)[:6],
            width=grid.width,
            height=grid.height,
        ),
        layers=layer_infos,
        corrections=CorrectionInfo(
            available_layers=list(layers.available_correction_layers), applied=[], statement=CORRECTION_STATEMENT
        ),
        transformations=transformations,
        build=BuildInfo(
            command=command,
            built_at_utc=dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            app_version=__version__,
            tool_versions={
                "python": platform.python_version(),
                "h5py": h5py.__version__,
                "hdf5": h5py.version.hdf5_version,
                "numpy": np.__version__,
                "rasterio": rasterio.__version__,
            },
        ),
    )
    write_manifest(manifest, out_dir)
    return manifest


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class Fixture:
    directory: Path
    manifest: FixtureManifest
    grid: GridGeometry
    arrays: dict[str, np.ndarray]

    def layer(self, name: str) -> np.ndarray | None:
        return self.arrays.get(name)


def load_fixture(directory: Path) -> Fixture:
    """Load a fixture directory. Raises FileNotFoundError / ValueError with a clear message."""
    directory = Path(directory)
    manifest = read_manifest(directory)
    arrays: dict[str, np.ndarray] = {}
    grid: GridGeometry | None = None
    for name, info in manifest.layers.items():
        path = directory / info.file
        if not path.is_file():
            raise FileNotFoundError(f"Fixture layer file missing: {path}")
        with rasterio.open(path) as src:
            arrays[name] = src.read(1)
            layer_grid = GridGeometry(CRS.from_wkt(src.crs.to_wkt()), src.transform, src.width, src.height)
        if grid is None:
            grid = layer_grid
        elif layer_grid.shape != grid.shape or not layer_grid.transform.almost_equals(grid.transform):
            raise ValueError(f"Fixture layer {name} is not on the same grid as the other layers")
    if grid is None or "unwrapped_phase" not in arrays or "coherence" not in arrays:
        raise ValueError(f"Fixture at {directory} lacks the required unwrapped_phase / coherence layers")
    return Fixture(directory, manifest, grid, arrays)
