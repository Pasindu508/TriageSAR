import numpy as np
import pytest

from triagesar.config import COMPONENT_NAMES, PrioritisationConfig, SensitivityConfig, load_config
from triagesar.prioritisation import model as pm
from triagesar.prioritisation.explanation import evidence_quality

W = load_config().prioritisation.normalised_weights()


def test_score_is_the_documented_weighted_sum() -> None:
    row = np.array([[1.0, 0.5, 0.8, 0.6, 1.0, 0.4]])
    expected = 100 * sum(W[n] * v for n, v in zip(COMPONENT_NAMES, row[0], strict=True))
    assert pm.scores(row, W)[0] == pytest.approx(expected)
    assert pm.scores(np.ones((1, 6)), W)[0] == pytest.approx(100.0)
    assert pm.scores(np.zeros((1, 6)), W)[0] == 0.0


def test_ranking_is_deterministic_with_stable_tie_break() -> None:
    s = np.array([50.0, 80.0, 50.0, 80.0])
    assert pm.ranking(s).tolist() == [1, 3, 0, 2]
    assert pm.ranks_from_order(pm.ranking(s)).tolist() == [3, 1, 4, 2]


def test_weights_validation_and_normalisation() -> None:
    raw = {n: 2.0 for n in COMPONENT_NAMES}
    cfg = PrioritisationConfig(weights=raw, road_class_values={"primary": 0.8})
    assert sum(cfg.normalised_weights().values()) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        PrioritisationConfig(weights={**raw, "coherence": -1.0}, road_class_values={})
    with pytest.raises(ValueError):
        PrioritisationConfig(weights={"coherence": 1.0}, road_class_values={})


def test_sensitivity_flags_a_knife_edge_ranking_as_unstable() -> None:
    # Two candidates whose scores are almost identical but driven by different factors.
    m = np.array([[1.0, 0.0, 0.5, 0.5, 0.5, 0.5], [0.0, 1.0, 0.5, 0.5, 0.5, 0.5]])
    w = {**W, "displacement_magnitude": 0.2501, "overlap_extent": 0.25}
    res = pm.sensitivity_analysis(m, w, SensitivityConfig())
    assert res.runs == 212 and res.unstable is True and (res.top1_changed_fraction or 0) > 0.2
    assert res.rank_min == (1, 1) and res.rank_max == (2, 2)


def test_sensitivity_reports_stable_for_a_clear_leader() -> None:
    m = np.array([[1.0, 1.0, 1.0, 1.0, 1.0, 1.0], [0.2, 0.2, 0.2, 0.2, 0.2, 0.2], [0.1, 0.3, 0.1, 0.3, 0.1, 0.3]])
    res = pm.sensitivity_analysis(m, W, SensitivityConfig())
    assert res.unstable is False and res.top1_changed_fraction == 0.0 and res.rank_max[0] == 1


def test_sensitivity_is_seeded_and_handles_empty_queue() -> None:
    m = np.random.default_rng(1).uniform(size=(8, 6))
    a = pm.sensitivity_analysis(m, W, SensitivityConfig())
    b = pm.sensitivity_analysis(m, W, SensitivityConfig())
    assert a == b
    empty = pm.sensitivity_analysis(np.zeros((0, 6)), W, SensitivityConfig())
    assert empty.runs == 0 and empty.unstable is None


def test_evidence_quality_label() -> None:
    assert evidence_quality(0.9, 1.0, 0.75, 0.5) == "VALID"
    assert evidence_quality(0.4, 0.6, 0.75, 0.5) == "CAUTION"
    assert evidence_quality(0.1, 0.2, 0.75, 0.5) == "INSUFFICIENT"
    assert evidence_quality(None, None, 0.75, 0.5) == "INSUFFICIENT"
