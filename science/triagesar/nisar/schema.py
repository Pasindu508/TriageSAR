"""Canonical internal names for the GUNW layers TriageSAR understands.

NISAR HDF5 layouts have changed between product versions, so nothing here is a
hard-coded absolute path. Layers are recognised by dataset *basename* and then
validated by shape; see ``hdf5_reader.discover_layers``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SPEED_OF_LIGHT_M_S = 299_792_458.0  # exact, SI definition

#: canonical name -> dataset basenames accepted, in order of preference
LAYER_ALIASES: dict[str, tuple[str, ...]] = {
    "unwrapped_phase": ("unwrappedPhase", "unwrapped_phase"),
    "coherence": ("coherenceMagnitude", "coherence_magnitude", "coherence"),
    "connected_components": ("connectedComponents", "connected_components"),
    "mask": ("mask",),
    "ionosphere_phase_screen": ("ionospherePhaseScreen",),
    "ionosphere_phase_screen_uncertainty": ("ionospherePhaseScreenUncertainty",),
}
REQUIRED_LAYERS = ("unwrapped_phase", "coherence")
OPTIONAL_LAYERS = tuple(k for k in LAYER_ALIASES if k not in REQUIRED_LAYERS)

X_COORD_NAMES = ("xCoordinates", "x_coordinates", "x")
Y_COORD_NAMES = ("yCoordinates", "y_coordinates", "y")
PROJECTION_NAMES = ("projection", "spatial_ref", "crs")
CENTER_FREQUENCY_NAMES = ("centerFrequency", "center_frequency")
WAVELENGTH_NAMES = ("wavelength", "radarWavelength", "radar_wavelength")

#: Correction layers that may ship with the product. TriageSAR never applies
#: them silently; their presence is only reported in provenance.
CORRECTION_LAYER_NAMES = (
    "ionospherePhaseScreen",
    "ionospherePhaseScreenUncertainty",
    "hydrostaticTroposphericPhaseScreen",
    "wetTroposphericPhaseScreen",
    "combinedTroposphericPhaseScreen",
    "slantRangeSolidEarthTidesPhase",
    "alongTrackSolidEarthTidesPhase",
)

POLARISATION_PREFERENCE = ("HH", "VV", "HV", "VH")


class SchemaError(ValueError):
    """The HDF5 file does not contain a usable GUNW layer set."""


@dataclass(frozen=True)
class LayerRef:
    canonical_name: str
    hdf5_path: str
    shape: tuple[int, ...]
    dtype: str
    units: str | None
    fill_value: float | None
    description: str | None


@dataclass(frozen=True)
class GridRef:
    x_path: str
    y_path: str
    projection_path: str | None
    epsg: int | None
    wkt: str | None
    width: int
    height: int


@dataclass(frozen=True)
class WavelengthRef:
    wavelength_m: float
    source_path: str
    #: "center_frequency" (lambda = c / f) or "wavelength" (read directly)
    derivation: str
    center_frequency_hz: float | None


@dataclass(frozen=True)
class CanonicalLayers:
    """Everything the reader recognised in one GUNW file."""

    layer_group: str
    frequency: str | None
    polarisation: str | None
    layers: dict[str, LayerRef]
    grid: GridRef
    wavelength: WavelengthRef
    available_correction_layers: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = field(default_factory=tuple)
