"""The default production baseline (PeakBoundary + Boundary + WeightedSpline / AdaptiveConnect, i.e. what
WorkflowBuilder.with_default_baseline composes) must stay bit-identical to origin/main 9790964.

Reference = tests/frozen_weighted_spline_9790964.py (verbatim old strategies). Matrix: 10 seeds x noise {0.2, 1, 5}
x 6 signal shapes (linear drift, curved drift, sinusoidal wander, 6 peaks + drift, broad sigma=1.5 peak, low SNR
peak) x 2 strategies = 360 comparisons, compared with assert_array_equal.
"""
import numpy as np
import pytest

import frozen_weighted_spline_9790964 as old
from peakpicker.application.workflow import WorkflowBuilder
from peakpicker.baseline import BaselineCorrector, CompositeAnchorFinder, BoundaryAnchorFinder, PeakBoundaryAnchorFinder
from peakpicker.baseline import AdaptiveConnectStrategy, WeightedSplineStrategy
from peakpicker.config import BaselineCorrectorConfig
from peakpicker.infrastructure import ScipyInterpolator, ScipySignalProcessor

T = np.linspace(0.0, 20.0, 2001)


def g(amp, c, s):
    return amp * np.exp(-0.5 * ((T - c) / s) ** 2)


SHAPES = {
    "linear": lambda: 50.0 + 2.0 * T,
    "curved": lambda: 50.0 + 2.0 * T + 0.05 * (T - 10.0) ** 2,
    "wander": lambda: 100.0 + 15.0 * np.sin(T / 2.5) + 0.5 * T,
    "six_peaks": lambda: 40.0 + 1.5 * T + g(900, 3, .12) + g(500, 6, .15) + g(1200, 8.5, .12) + g(300, 12, .2) + g(700, 15, .15) + g(400, 18, .12),
    "broad": lambda: 80.0 + T + g(800, 10, 1.5),
    "low_snr": lambda: 100.0 + g(12, 10, .15),
}


def production(strategy_cls):
    sp, ip = ScipySignalProcessor(), ScipyInterpolator()
    cfg = BaselineCorrectorConfig()
    cfg.generator_config.clip_to_signal = False      # as with_default_baseline does
    ac = cfg.anchor_config
    finder = CompositeAnchorFinder([PeakBoundaryAnchorFinder(sp, ac), BoundaryAnchorFinder(ac)], ac)
    return BaselineCorrector(finder, strategy_cls(ip, cfg.strategy_config), config=cfg)


@pytest.mark.parametrize("pair", [(WeightedSplineStrategy, old.WeightedSplineStrategy),
                                  (AdaptiveConnectStrategy, old.AdaptiveConnectStrategy)], ids=["weighted_spline", "adaptive_connect"])
@pytest.mark.parametrize("shape", list(SHAPES))
@pytest.mark.parametrize("noise", [0.2, 1.0, 5.0])
def test_production_composition_is_bit_identical_to_9790964(pair, shape, noise):
    new_cls, old_cls = pair
    for seed in range(10):
        y = SHAPES[shape]() + np.random.default_rng(seed).normal(0.0, noise, T.size)
        new = production(new_cls).correct(T, y).baseline
        ref = production(old_cls).correct(T, y).baseline
        np.testing.assert_array_equal(new, ref)


def test_with_default_baseline_matches_frozen_reference_on_the_reported_drift_case():
    """The coordinator's reproducer: curved no-peak drift, noise seed 8 (old rmse 1.061, max 6.1)."""
    truth = 50.0 + 2.0 * T + 0.05 * (T - 10.0) ** 2
    y = truth + np.random.default_rng(8).normal(0.0, 1.0, T.size)
    new = WorkflowBuilder().with_default_baseline()._baseline_corrector.correct(T, y).baseline
    corrector = production(old.WeightedSplineStrategy)
    corrector.generator.config.clip_to_signal = False
    np.testing.assert_array_equal(new, corrector.correct(T, y).baseline)
    assert np.sqrt(np.mean((new - truth) ** 2)) < 1.2
