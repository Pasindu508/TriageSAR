"""Typed, validated analysis configuration loaded from TOML."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "triagesar.toml"

COMPONENT_NAMES = (
    "displacement_magnitude",
    "overlap_extent",
    "valid_fraction",
    "coherence",
    "proximity",
    "road_class",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QualityConfig(_Strict):
    coherence_exclude_below: float = Field(0.30, ge=0.0, le=1.0)
    coherence_caution_below: float = Field(0.50, ge=0.0, le=1.0)
    exclude_unwrap_component_zero: bool = True
    small_component_pixels: int = Field(2000, ge=0)
    use_product_mask: bool = True
    summary_valid_fraction: float = Field(0.75, ge=0.0, le=1.0)
    summary_usable_fraction: float = Field(0.50, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> QualityConfig:
        if self.coherence_caution_below < self.coherence_exclude_below:
            raise ValueError("coherence_caution_below must be >= coherence_exclude_below")
        return self


class ReferenceConfig(_Strict):
    method: Literal["local_plane", "component_median"] = "local_plane"
    window_m: float = Field(4000.0, gt=0.0)
    min_window_fraction: float = Field(0.25, gt=0.0, le=1.0)


class HotspotConfig(_Strict):
    threshold_floor_m: float = Field(0.03, gt=0.0)
    robust_sigma_multiplier: float = Field(3.0, gt=0.0)
    min_area_km2: float = Field(0.5, ge=0.0)
    connectivity: Literal[4, 8] = 8
    include_caution_pixels: bool = True


class InfrastructureConfig(_Strict):
    highway_classes: tuple[str, ...] = ("motorway", "trunk", "primary", "secondary", "tertiary")
    corridor_buffer_m: float = Field(250.0, gt=0.0)
    proximity_limit_m: float = Field(1000.0, gt=0.0)


class PrioritisationConfig(_Strict):
    weights: dict[str, float]
    road_class_values: dict[str, float]

    @model_validator(mode="after")
    def _check(self) -> PrioritisationConfig:
        if set(self.weights) != set(COMPONENT_NAMES):
            raise ValueError(f"weights must define exactly: {', '.join(COMPONENT_NAMES)}")
        if any(v < 0 for v in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if sum(self.weights.values()) <= 0:
            raise ValueError("at least one weight must be positive")
        if any(not 0.0 <= v <= 1.0 for v in self.road_class_values.values()):
            raise ValueError("road_class_values must lie in [0, 1]")
        return self

    def normalised_weights(self) -> dict[str, float]:
        total = sum(self.weights.values())
        return {name: self.weights[name] / total for name in COMPONENT_NAMES}


class SensitivityConfig(_Strict):
    perturbation_fraction: float = Field(0.20, ge=0.0, lt=1.0)
    random_draws: int = Field(200, ge=0, le=5000)
    seed: int = 20260624
    unstable_top1_change_fraction: float = Field(0.20, ge=0.0, le=1.0)


class AnalysisConfig(_Strict):
    quality: QualityConfig
    reference: ReferenceConfig
    hotspot: HotspotConfig
    infrastructure: InfrastructureConfig
    prioritisation: PrioritisationConfig
    sensitivity: SensitivityConfig


def load_config(path: Path | None = None) -> AnalysisConfig:
    """Load and validate the analysis configuration. Raises ValueError on bad config."""
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    try:
        with cfg_path.open("rb") as fh:
            raw = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ValueError(f"Configuration file not found: {cfg_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Configuration file is not valid TOML: {cfg_path}: {exc}") from exc
    return AnalysisConfig.model_validate(raw)
