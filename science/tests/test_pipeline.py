"""Deterministic regression tests of the full pipeline on the TEST ONLY synthetic fixture."""

import json
import re

import numpy as np
import pytest

from triagesar.config import AnalysisConfig
from triagesar.fixture import Fixture
from triagesar.infrastructure.osm import Road
from triagesar.pipeline import ablation_summary, run_analysis
from triagesar.processing.quality import QualityState
from triagesar.render import render_overlays

FORBIDDEN = re.compile(r"damage (probability|score|severity)|lives saved|casualt|\bconfidence\b|ground truth(?! )", re.I)


@pytest.fixture(scope="module")
def artifacts(fixture: Fixture, roads: list[Road], config: AnalysisConfig):  # type: ignore[no-untyped-def]
    return run_analysis(fixture, roads, config)


def test_pipeline_is_deterministic(fixture: Fixture, roads: list[Road], config: AnalysisConfig, artifacts) -> None:  # type: ignore[no-untyped-def]
    again = run_analysis(fixture, roads, config)
    assert again.result.model_dump_json() == artifacts.result.model_dump_json()
    np.testing.assert_array_equal(again.quality_state, artifacts.quality_state)


def test_regression_values_on_synthetic_fixture(artifacts) -> None:  # type: ignore[no-untyped-def]
    r = artifacts.result
    assert r.data_kind == "synthetic_test" and r.schema_version == "1.0"
    assert r.radar.wavelength_m == pytest.approx(0.2398339664)
    assert sum(r.quality.counts.values()) == r.quality.total_pixels == r.grid.width * r.grid.height
    assert r.quality.counts["EXCLUDED"] > 0 and r.quality.counts["CAUTION"] > 0
    assert r.reference.method == "local_plane" and r.reference.window_m == pytest.approx(4080.0)
    assert r.reference.quantity == "local LOS range change"
    assert len(r.zones) == 2  # the two local features; the regional field produces none
    assert r.zones[0].median_los_m > 0 > r.zones[1].median_los_m  # one bump of each sign
    true_peak = 9.0 * 0.2398339664 / (4 * np.pi)  # 17.2 cm; a local reference recovers most of it
    assert 0.6 * true_peak < r.zones[0].max_abs_los_m < 1.0 * true_peak
    # Scene-relative context is kept: the positive bump sits on the high side of the regional field.
    assert r.zones[0].scene_median_los_m > r.zones[0].median_los_m
    assert r.zones[0].nearest_road_name == "TEST Road Alpha (T1)" and r.zones[0].nearest_road_distance_m == 0.0
    assert r.threshold.binding == "floor" and r.threshold.threshold_m == pytest.approx(0.03)
    assert "local LOS range change" in r.threshold.rule
    assert [q.rank for q in r.queue] == list(range(1, len(r.queue) + 1))
    assert [q.score for q in r.queue] == sorted((q.score for q in r.queue), reverse=True)
    names = {q.asset_name for q in r.queue}
    assert {"TEST Road Alpha (T1)", "TEST Road Bravo", "TEST Road Charlie (T2)"} <= names
    assert {q.relation for q in r.queue} == {"overlaps", "near"}
    assert all("not ranked" not in q.asset_name for q in r.queue)  # residential roads are not in the config
    assert all(q.corridor.scene_median_los_m is not None for q in r.queue)


def test_scene_wide_motion_defeats_the_scene_median_reference(
    fixture: Fixture, roads: list[Road], config: AnalysisConfig
) -> None:
    """Regression for the first real run: when the whole study area moved, the original rule
    (reference = scene median, threshold = 3 x robust spread of the scene) measures the regional
    field itself and finds no zones. The local reference still finds the local features."""
    old = config.model_copy(update={"reference": config.reference.model_copy(update={"method": "component_median"})})
    r = run_analysis(fixture, roads, old).result
    assert r.reference.method == "component_median" and r.reference.window_m is None
    assert r.threshold.binding == "robust_sigma" and r.threshold.threshold_m > 0.30
    assert r.zones == [] and r.queue == []


def test_close_scores_are_reported_as_an_unstable_ranking(artifacts) -> None:  # type: ignore[no-untyped-def]
    r = artifacts.result
    top_two = {r.queue[0].asset_name, r.queue[1].asset_name}
    assert top_two == {"TEST Road Alpha (T1)", "TEST Road Charlie (T2)"}
    assert abs(r.queue[0].score - r.queue[1].score) < 3.0
    assert r.sensitivity.unstable is True and r.sensitivity.top1_changed_fraction > 0.2
    assert r.queue[0].stability.max_rank > 1


def test_score_components_are_auditable_by_hand(artifacts) -> None:  # type: ignore[no-untyped-def]
    for item in artifacts.result.queue:
        assert sum(c.weight for c in item.components) == pytest.approx(1.0, abs=1e-3)
        assert item.score == pytest.approx(sum(100 * c.value * c.weight for c in item.components), abs=0.05)
        assert all(0.0 <= c.value <= 1.0 for c in item.components)
        assert len(item.explanation.why_ranked) == 7 and "not a damage assessment" in item.explanation.disclaimer


def test_poor_radar_quality_is_visible_on_the_item(artifacts) -> None:  # type: ignore[no-untyped-def]
    queue = artifacts.result.queue
    alpha = next(q for q in queue if q.asset_name.startswith("TEST Road Alpha"))
    assert alpha.evidence_quality == "CAUTION" and alpha.corridor.caution_pixels > 0
    assert any("limited" in c for c in alpha.explanation.caveats)
    charlie = next(q for q in queue if q.asset_name.startswith("TEST Road Charlie"))
    assert charlie.corridor.excluded_pixels > 0
    assert any("excluded" in c for c in charlie.explanation.caveats)


def test_masks_propagate_to_relative_displacement(artifacts) -> None:  # type: ignore[no-untyped-def]
    excluded = artifacts.quality_state == int(QualityState.EXCLUDED)
    assert np.isnan(artifacts.relative_m[excluded]).all()
    assert np.isfinite(artifacts.relative_m[~excluded]).all()
    assert np.isnan(artifacts.analysis_m[excluded]).all()  # the local reference never fills excluded pixels
    unreferenced = int(np.count_nonzero(~excluded & ~np.isfinite(artifacts.analysis_m)))
    assert unreferenced == artifacts.result.reference.unreferenced_pixels


def test_no_overclaiming_language_anywhere_in_results(artifacts) -> None:  # type: ignore[no-untyped-def]
    text = json.dumps(artifacts.result.model_dump(mode="json"))
    assert not FORBIDDEN.search(text.replace("not ground truth", "").replace("not a damage assessment", ""))
    assert "Inspection" in artifacts.result.queue[0].explanation.why_ranked[0]


def test_ablation_quantifies_effect_of_masking(fixture: Fixture, roads: list[Road], config: AnalysisConfig, artifacts) -> None:  # type: ignore[no-untyped-def]
    unmasked = run_analysis(fixture, roads, config, apply_quality_mask=False).result
    summary = ablation_summary(artifacts.result, unmasked)
    assert unmasked.masking_applied is False and unmasked.quality.counts["CAUTION"] == 0
    assert summary["without_masking"]["usable_pixels"] > summary["with_masking"]["usable_pixels"]
    assert summary["without_masking"]["zone_area_km2"] != summary["with_masking"]["zone_area_km2"]


def test_empty_road_list_gives_empty_queue_not_an_error(fixture: Fixture, config: AnalysisConfig) -> None:
    r = run_analysis(fixture, [], config).result
    assert r.queue == [] and len(r.zones) == 2 and r.sensitivity.unstable is None


def test_overlays_are_valid_png_with_corner_coordinates(artifacts) -> None:  # type: ignore[no-untyped-def]
    ov = render_overlays(artifacts.grid, artifacts.relative_m, artifacts.quality_state, artifacts.analysis_m)
    assert ov.displacement_png[:8] == b"\x89PNG\r\n\x1a\n" and ov.quality_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert ov.local_png is not None and ov.local_png[:4] == b"\x89PNG" and ov.local_colour_limit_m < ov.colour_limit_m
    assert render_overlays(artifacts.grid, artifacts.relative_m, artifacts.quality_state).local_png is None
    (w, n), (e, _), (_, s), _ = ov.coordinates
    bw, bs, be, bn = artifacts.result.grid.bounds_wgs84
    assert w == pytest.approx(bw, abs=0.01) and e == pytest.approx(be, abs=0.01)
    assert s == pytest.approx(bs, abs=0.01) and n == pytest.approx(bn, abs=0.01)
    assert ov.colour_limit_m and ov.colour_limit_m > 0
