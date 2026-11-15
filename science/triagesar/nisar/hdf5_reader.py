"""Defensive reader for NISAR GUNW HDF5 products.

The reader never relies on one absolute dataset path. It walks the file,
recognises layers by basename (see ``schema.LAYER_ALIASES``), validates their
dimensions against the coordinate vectors found next to them, and reports
exactly which HDF5 paths were used so provenance can record them.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import h5py
import numpy as np

from .schema import (
    CENTER_FREQUENCY_NAMES,
    CORRECTION_LAYER_NAMES,
    LAYER_ALIASES,
    OPTIONAL_LAYERS,
    POLARISATION_PREFERENCE,
    PROJECTION_NAMES,
    SPEED_OF_LIGHT_M_S,
    WAVELENGTH_NAMES,
    X_COORD_NAMES,
    Y_COORD_NAMES,
    CanonicalLayers,
    GridRef,
    LayerRef,
    SchemaError,
    WavelengthRef,
)

_FREQ_RE = re.compile(r"frequency([A-Z])$")


def _decode(value: Any) -> Any:
    """Turn HDF5 scalars / byte strings into plain Python values."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\x00")
    if isinstance(value, np.ndarray):
        if value.shape == ():
            return _decode(value[()])
        if value.dtype.kind in ("S", "O"):
            return [_decode(v) for v in value.tolist()]
        return value.tolist()
    if isinstance(value, np.generic):
        return _decode(value.item())
    return value


def iter_datasets(h5: h5py.File | h5py.Group) -> Iterator[tuple[str, h5py.Dataset]]:
    """Yield ``(absolute_path, dataset)`` for every dataset below ``h5``."""
    found: list[tuple[str, h5py.Dataset]] = []

    def visit(name: str, obj: Any) -> None:
        if isinstance(obj, h5py.Dataset):
            found.append((obj.name, obj))

    h5.visititems(visit)
    yield from found


def _attr(ds: h5py.Dataset, *names: str) -> Any:
    for name in names:
        if name in ds.attrs:
            return _decode(ds.attrs[name])
    return None


def _fill_value(ds: h5py.Dataset) -> float | None:
    raw = _attr(ds, "_FillValue", "fill_value", "missing_value")
    if raw is None:
        return None
    try:
        if isinstance(raw, list):
            raw = raw[0]
        return float(raw)
    except (TypeError, ValueError):
        return None


def _layer_ref(canonical: str, ds: h5py.Dataset) -> LayerRef:
    units = _attr(ds, "units", "unit")
    desc = _attr(ds, "description", "long_name")
    return LayerRef(
        canonical_name=canonical,
        hdf5_path=ds.name,
        shape=tuple(int(s) for s in ds.shape),
        dtype=str(ds.dtype),
        units=str(units) if units is not None else None,
        fill_value=_fill_value(ds),
        description=str(desc) if desc is not None else None,
    )


def _split(path: str) -> list[str]:
    return [p for p in path.split("/") if p]


def _frequency_of(path: str) -> str | None:
    for part in _split(path):
        m = _FREQ_RE.match(part)
        if m:
            return m.group(1)
    return None


def _polarisation_of(path: str) -> str | None:
    for part in reversed(_split(path)[:-1]):
        if part in POLARISATION_PREFERENCE:
            return part
    return None


def _find_upwards(h5: h5py.File, start_group: str, names: tuple[str, ...]) -> h5py.Dataset | None:
    """Look for a dataset called one of ``names`` in ``start_group`` or any ancestor."""
    parts = _split(start_group)
    while True:
        group_path = "/" + "/".join(parts)
        group = h5.get(group_path)
        if isinstance(group, h5py.Group):
            for name in names:
                obj = group.get(name)
                if isinstance(obj, h5py.Dataset):
                    return obj
        if not parts:
            return None
        parts.pop()


def _parse_epsg(ds: h5py.Dataset) -> tuple[int | None, str | None]:
    """Return ``(epsg, wkt)`` from a CF-style projection dataset."""
    epsg: int | None = None
    for key in ("epsg_code", "epsg", "EPSG"):
        if key in ds.attrs:
            try:
                epsg = int(np.asarray(ds.attrs[key]).ravel()[0])
                break
            except (TypeError, ValueError):
                pass
    if epsg is None and ds.shape in ((), (1,)) and ds.dtype.kind in ("i", "u"):
        value = int(np.asarray(ds[()]).ravel()[0])
        if 1024 <= value <= 998_999:
            epsg = value
    wkt = None
    for key in ("spatial_ref", "crs_wkt", "wkt"):
        if key in ds.attrs:
            wkt = str(_decode(ds.attrs[key]))
            break
    return epsg, wkt


def _rank_candidate(path: str, frequency: str | None, polarisation: str | None) -> tuple[int, int, int, str]:
    freq = _frequency_of(path) or "~"
    pol = _polarisation_of(path)
    freq_rank = 0 if (frequency is not None and freq == frequency) else (1 if frequency is None else 2)
    if polarisation is not None:
        pol_rank = 0 if pol == polarisation else 99
    else:
        pol_rank = POLARISATION_PREFERENCE.index(pol) if pol in POLARISATION_PREFERENCE else 50
    return (freq_rank, ord(freq[0]), pol_rank, path)


def discover_layers(
    h5: h5py.File,
    frequency: str | None = None,
    polarisation: str | None = None,
) -> CanonicalLayers:
    """Recognise the canonical GUNW layers in an open HDF5 file.

    ``frequency`` ("A"/"B") and ``polarisation`` ("HH", ...) narrow the choice
    when a product carries several; otherwise frequency A and the first
    available co-polarised channel are preferred. Raises ``SchemaError`` with a
    specific message when the file cannot be used.
    """
    datasets = list(iter_datasets(h5))
    phase_names = LAYER_ALIASES["unwrapped_phase"]
    candidates = [
        (path, ds) for path, ds in datasets if path.rsplit("/", 1)[-1] in phase_names and ds.ndim == 2
    ]
    if not candidates:
        wrong_dim = [p for p, ds in datasets if p.rsplit("/", 1)[-1] in phase_names]
        if wrong_dim:
            raise SchemaError(
                f"Unwrapped-phase dataset(s) found but not 2-D: {', '.join(wrong_dim)}"
            )
        raise SchemaError("No unwrapped-phase dataset found (looked for: " + ", ".join(phase_names) + ")")

    candidates.sort(key=lambda item: _rank_candidate(item[0], frequency, polarisation))
    phase_path, phase_ds = candidates[0]
    if frequency is not None and _frequency_of(phase_path) != frequency:
        raise SchemaError(f"Requested frequency {frequency!r} not present in file")
    if polarisation is not None and _polarisation_of(phase_path) != polarisation:
        raise SchemaError(f"Requested polarisation {polarisation!r} not present in file")

    group_path = phase_path.rsplit("/", 1)[0] or "/"
    group = h5[group_path]
    layers: dict[str, LayerRef] = {"unwrapped_phase": _layer_ref("unwrapped_phase", phase_ds)}

    # Layers normally sit next to the phase (per polarisation). Some, such as the
    # product ``mask``, are stored one level up and shared by all polarisations.
    parent_path = group_path.rsplit("/", 1)[0] or "/"
    search_groups = [group] + ([h5[parent_path]] if parent_path != group_path else [])
    for canonical, aliases in LAYER_ALIASES.items():
        if canonical == "unwrapped_phase":
            continue
        for search_group, alias in ((g, a) for g in search_groups for a in aliases):
            obj = search_group.get(alias)
            if not isinstance(obj, h5py.Dataset):
                continue
            if obj.shape != phase_ds.shape:
                if canonical in OPTIONAL_LAYERS:
                    continue  # optional layer on a different grid: ignore, do not guess
                raise SchemaError(
                    f"{obj.name} has shape {obj.shape}, expected {phase_ds.shape} to match {phase_path}"
                )
            layers[canonical] = _layer_ref(canonical, obj)
            break
    if "coherence" not in layers:
        raise SchemaError(f"No coherence dataset found next to {phase_path}")

    x_ds = _find_upwards(h5, group_path, X_COORD_NAMES)
    y_ds = _find_upwards(h5, group_path, Y_COORD_NAMES)
    if x_ds is None or y_ds is None:
        raise SchemaError(f"No x/y coordinate vectors found for {phase_path}")
    height, width = (int(s) for s in phase_ds.shape)
    if x_ds.ndim != 1 or y_ds.ndim != 1 or x_ds.shape[0] != width or y_ds.shape[0] != height:
        raise SchemaError(
            f"Coordinate vectors do not match raster dimensions: "
            f"x{tuple(x_ds.shape)} y{tuple(y_ds.shape)} vs raster (height={height}, width={width})"
        )
    proj_ds = _find_upwards(h5, group_path, PROJECTION_NAMES)
    epsg, wkt = (None, None) if proj_ds is None else _parse_epsg(proj_ds)
    if epsg is None and wkt is None:
        raise SchemaError(f"No coordinate reference system found for {phase_path}")
    grid = GridRef(
        x_path=x_ds.name,
        y_path=y_ds.name,
        projection_path=None if proj_ds is None else proj_ds.name,
        epsg=epsg,
        wkt=wkt,
        width=width,
        height=height,
    )

    wavelength = _discover_wavelength(h5, group_path)
    corrections = sorted(
        {path for path, _ in datasets if path.rsplit("/", 1)[-1] in CORRECTION_LAYER_NAMES}
    )
    return CanonicalLayers(
        layer_group=group_path,
        frequency=_frequency_of(phase_path),
        polarisation=_polarisation_of(phase_path),
        layers=layers,
        grid=grid,
        wavelength=wavelength,
        available_correction_layers=tuple(corrections),
        alternatives=tuple(path for path, _ in candidates[1:]),
    )


def _discover_wavelength(h5: h5py.File, group_path: str) -> WavelengthRef:
    """Derive the radar wavelength from product metadata only (never a nominal value)."""
    wl_ds = _find_upwards(h5, group_path, WAVELENGTH_NAMES)
    if wl_ds is not None:
        value = float(np.asarray(wl_ds[()]).ravel()[0])
        if not (0.001 < value < 10.0):
            raise SchemaError(f"Implausible wavelength {value} m at {wl_ds.name}")
        return WavelengthRef(value, wl_ds.name, "wavelength", None)
    cf_ds = _find_upwards(h5, group_path, CENTER_FREQUENCY_NAMES)
    if cf_ds is None:
        raise SchemaError(
            "No radar wavelength or centre-frequency metadata found; refusing to assume a nominal value"
        )
    freq = float(np.asarray(cf_ds[()]).ravel()[0])
    units = str(_attr(cf_ds, "units", "unit") or "").strip().lower()
    scale = {"": 1.0, "hz": 1.0, "hertz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}.get(units)
    if scale is None:
        raise SchemaError(f"Unrecognised centre-frequency units {units!r} at {cf_ds.name}")
    freq_hz = freq * scale
    if not (1e8 < freq_hz < 1e11):
        raise SchemaError(f"Implausible centre frequency {freq_hz} Hz at {cf_ds.name}")
    return WavelengthRef(SPEED_OF_LIGHT_M_S / freq_hz, cf_ds.name, "center_frequency", freq_hz)


def read_coordinates(h5: h5py.File, grid: GridRef) -> tuple[np.ndarray, np.ndarray]:
    """Return the full x and y coordinate vectors (pixel centres)."""
    x = np.asarray(h5[grid.x_path][()], dtype=np.float64)
    y = np.asarray(h5[grid.y_path][()], dtype=np.float64)
    for name, vec in (("x", x), ("y", y)):
        if vec.size < 2:
            raise SchemaError(f"{name} coordinate vector too short")
        steps = np.diff(vec)
        if not np.all(np.isfinite(steps)) or np.any(steps == 0) or np.any(np.sign(steps) != np.sign(steps[0])):
            raise SchemaError(f"{name} coordinate vector is not strictly monotonic")
        if not np.allclose(steps, steps[0], rtol=1e-6, atol=1e-9):
            raise SchemaError(f"{name} coordinate vector is not regularly spaced")
    return x, y


def read_window(h5: h5py.File, layer: LayerRef, rows: slice, cols: slice) -> np.ndarray:
    """Read a rectangular window of one layer without modifying its values."""
    return np.asarray(h5[layer.hdf5_path][rows, cols])


def describe_tree(h5: h5py.File, max_attr_len: int = 80) -> list[str]:
    """Human-readable listing of groups, datasets, shapes, dtypes, units and CRS."""
    lines: list[str] = []

    def visit(name: str, obj: Any) -> None:
        depth = name.count("/")
        indent = "  " * depth
        label = name.rsplit("/", 1)[-1]
        if isinstance(obj, h5py.Group):
            lines.append(f"{indent}{label}/")
            return
        bits = [f"shape={tuple(obj.shape)}", f"dtype={obj.dtype}"]
        units = _attr(obj, "units", "unit")
        if units:
            bits.append(f"units={units}")
        fill = _fill_value(obj)
        if fill is not None:
            bits.append(f"fill={fill:g}")
        epsg, _ = _parse_epsg(obj) if label in PROJECTION_NAMES else (None, None)
        if epsg:
            bits.append(f"EPSG:{epsg}")
        if obj.shape == () or (obj.ndim == 1 and obj.shape[0] <= 4 and obj.dtype.kind in "SOiuf"):
            try:
                text = str(_decode(obj[()]))
                bits.append("value=" + (text if len(text) <= max_attr_len else text[: max_attr_len - 1] + "…"))
            except (OSError, TypeError, ValueError):
                pass
        desc = _attr(obj, "description", "long_name")
        if desc:
            text = str(desc)
            bits.append("desc=" + (text if len(text) <= max_attr_len else text[: max_attr_len - 1] + "…"))
        lines.append(f"{indent}{label}  [{', '.join(bits)}]")

    h5.visititems(visit)
    return lines
