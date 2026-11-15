"""Acquisition / identification metadata extracted from a GUNW file."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import h5py

from .hdf5_reader import _decode, iter_datasets

#: canonical field -> accepted dataset basenames inside an ``identification`` group
IDENTIFICATION_FIELDS: dict[str, tuple[str, ...]] = {
    "reference_start_time": ("referenceZeroDopplerStartTime",),
    "reference_end_time": ("referenceZeroDopplerEndTime",),
    "secondary_start_time": ("secondaryZeroDopplerStartTime",),
    "secondary_end_time": ("secondaryZeroDopplerEndTime",),
    "track_number": ("trackNumber",),
    "frame_number": ("frameNumber",),
    "orbit_pass_direction": ("orbitPassDirection",),
    "look_direction": ("lookDirection",),
    "absolute_orbit_number": ("absoluteOrbitNumber", "referenceAbsoluteOrbitNumber"),
    "product_version": ("productVersion",),
    "product_type": ("productType",),
    "product_level": ("productLevel",),
    "granule_id": ("granuleId",),
    "mission_id": ("missionId",),
    "processing_datetime": ("processingDateTime",),
    "processing_type": ("processingType",),
    "product_specification_version": ("productSpecificationVersion",),
    "composite_release_id": ("compositeReleaseId",),
    "is_urgent_observation": ("isUrgentObservation",),
    "bounding_polygon": ("boundingPolygon",),
}
SOFTWARE_VERSION_NAMES = ("softwareVersion", "isce3Version", "version")


@dataclass(frozen=True)
class GunwMetadata:
    fields: dict[str, Any]
    source_paths: dict[str, str]
    software_version: str | None
    software_version_path: str | None

    def get(self, key: str) -> Any:
        return self.fields.get(key)


def read_metadata(h5: h5py.File) -> GunwMetadata:
    """Collect identification metadata. Missing fields are simply absent (never guessed)."""
    fields: dict[str, Any] = {}
    paths: dict[str, str] = {}
    software: str | None = None
    software_path: str | None = None
    for path, ds in iter_datasets(h5):
        parts = [p for p in path.split("/") if p]
        base = parts[-1]
        if "identification" in parts[:-1]:
            for canonical, names in IDENTIFICATION_FIELDS.items():
                if base in names and canonical not in fields and ds.size <= 64:
                    try:
                        fields[canonical] = _decode(ds[()])
                        paths[canonical] = path
                    except (OSError, TypeError, ValueError):
                        pass
        if software is None and base in SOFTWARE_VERSION_NAMES and "processingInformation" in parts and ds.size == 1:
            try:
                software = str(_decode(ds[()]))
                software_path = path
            except (OSError, TypeError, ValueError):
                pass
    return GunwMetadata(fields, paths, software, software_path)
