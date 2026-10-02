"""Analytic-truth tests for the package baseline strategies (weighted_spline / adaptive_connect).

Mirror of the legacy hybrid_baseline flank-anchor tests: an anchor finder that picks the lowest
point of every window (LocalMinAnchorFinder) puts anchors on peak flanks, and a strategy that
interpolates through them lifts the baseline under the peak.
"""
import numpy as np
import pytest
from scipy.integrate import trapezoid
from scipy.stats import exponnorm

from peakpicker.baseline import (
    AdaptiveConnectStrategy,
    BaselineCorrector,
    BoundaryAnchorFinder,
    CompositeAnchorFinder,
    LocalMinAnchorFinder,
    PeakBoundaryAnchorFinder,
    ValleyAnchorFinder,
    WeightedSplineStrategy,
)
from peakpicker.config import BaselineCorrectorConfig
from peakpicker.infrastructure import ScipyInterpolator, ScipySignalProcessor

SQRT_2PI = np.sqrt(2.0 * np.pi)
STRATEGIES = {"weighted_spline": WeightedSplineStrategy, "adaptive_connect": AdaptiveConnectStrategy}


def gauss(x, amp, center, sigma):
    return amp * np.exp(-0.5 * ((x - center) / sigma) ** 2)


def build(kind, strategy):
    sp, ip = ScipySignalProcessor(), ScipyInterpolator()
    cfg = BaselineCorrectorConfig()
    cfg.generator_config.clip_to_signal = False
    ac = cfg.anchor_config
    if kind == "production":      # what WorkflowBuilder.with_default_baseline composes
        finders = [PeakBoundaryAnchorFinder(sp, ac), BoundaryAnchorFinder(ac)]
    else:                         # window-minimum finders, anchors may land on a flank
        finders = [LocalMinAnchorFinder(sp, ac), ValleyAnchorFinder(sp, ac), BoundaryAnchorFinder(ac)]
    return BaselineCorrector(CompositeAnchorFinder(finders, ac), STRATEGIES[strategy](ip, cfg.strategy_config), config=cfg)


def recovery(t, y, baseline, lo, hi, true_area):
    sel = (t > lo) & (t < hi)
    return trapezoid((y - baseline)[sel], t[sel]) / true_area


T = np.linspace(0.0, 20.0, 2001)


def single_peak(seed):
    return 100.0 + gauss(T, 1000.0, 10.0, 0.15) + np.random.default_rng(seed).normal(0.0, 1.0, T.size)


@pytest.mark.parametrize("strategy", list(STRATEGIES))
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_flat_baseline_single_peak_production_finders(strategy, seed):
    y = single_peak(seed)
    r = build("production", strategy).correct(T, y)
    assert abs(recovery(T, y, r.baseline, 9.1, 10.9, 1000 * 0.15 * SQRT_2PI) - 1.0) < 0.03


@pytest.mark.parametrize("strategy", list(STRATEGIES))
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_flat_baseline_single_peak_window_minimum_finders(strategy, seed):
    y = single_peak(seed)
    r = build("window_min", strategy).correct(T, y)
    ratio = recovery(T, y, r.baseline, 9.1, 10.9, 1000 * 0.15 * SQRT_2PI)
    assert abs(ratio - 1.0) < 0.03, ratio


@pytest.mark.parametrize("strategy", list(STRATEGIES))
@pytest.mark.parametrize("curved", [False, True], ids=["linear", "curved"])
def test_peak_free_drift_baseline_is_unchanged_by_the_filter(strategy, curved, monkeypatch):
    """Adverse for the fix: with no peak the flank filter must not strip legitimate drift anchors,
    so the baseline is bit-identical to the one produced with the filter bypassed."""
    import peakpicker.baseline.strategies.weighted_spline as mod

    truth = 50.0 + 2.0 * T + (0.05 * (T - 10.0) ** 2 if curved else 0.0)
    y = truth + np.random.default_rng(4).normal(0.0, 1.0, T.size)
    filtered = build("window_min", strategy).correct(T, y).baseline
    monkeypatch.setattr(mod, "baseline_anchor_mask", lambda i, v, r, k=7: np.ones(len(i), dtype=bool))
    unfiltered = build("window_min", strategy).correct(T, y).baseline
    np.testing.assert_array_equal(filtered, unfiltered)
    # window minima of noisy data sit ~2-3 sigma low; the tracked baseline stays within that band
    assert float(np.sqrt(np.mean((filtered - truth) ** 2))) < 7.0


def test_filter_rejects_flank_anchor_and_keeps_flat_baseline_anchors():
    from peakpicker.baseline.anchor_filters import baseline_anchor_mask

    idx = np.arange(0, 100, 10)
    val = np.array([100.0, 101.0, 99.0, 100.5, 400.0, 100.0, 99.5, 100.2, 100.0, 101.0])
    keep = baseline_anchor_mask(idx, val, signal_range=1000.0)
    assert not keep[4] and keep[np.arange(10) != 4].all()


def test_filter_never_rejects_end_anchors_or_below_baseline_dips():
    from peakpicker.baseline.anchor_filters import baseline_anchor_mask

    idx = np.arange(0, 100, 10)
    val = np.array([900.0, 100.0, 99.0, 100.5, -300.0, 100.0, 99.5, 100.2, 100.0, 900.0])
    assert baseline_anchor_mask(idx, val, signal_range=1000.0).all()


@pytest.mark.parametrize("strategy", list(STRATEGIES))
def test_close_pair_total_area(strategy):
    """Two peaks 2.7 sigma apart on a flat baseline: the pair's summed area must be recovered."""
    y = 100.0 + gauss(T, 800.0, 9.8, 0.15) + gauss(T, 600.0, 10.3, 0.15)
    y = y + np.random.default_rng(5).normal(0.0, 1.0, T.size)
    r = build("window_min", strategy).correct(T, y)
    true = (800.0 + 600.0) * 0.15 * SQRT_2PI
    ratio = recovery(T, y, r.baseline, 8.8, 11.3, true)
    assert abs(ratio - 1.0) < 0.05, ratio


@pytest.mark.parametrize("strategy", list(STRATEGIES))
def test_tailing_peak_area(strategy):
    sigma, tau = 0.12, 0.35
    shape = exponnorm.pdf(T, tau / sigma, loc=10.0, scale=sigma)       # unit-area EMG
    y = 100.0 + 400.0 * shape + np.random.default_rng(6).normal(0.0, 1.0, T.size)
    r = build("window_min", strategy).correct(T, y)
    ratio = recovery(T, y, r.baseline, 9.0, 14.0, 400.0)
    assert abs(ratio - 1.0) < 0.05, ratio


@pytest.mark.parametrize("strategy", list(STRATEGIES))
def test_baseline_never_far_above_signal_envelope(strategy):
    """Contract: finite, right shape, and not above the signal by more than the noise."""
    y = single_peak(0)
    r = build("window_min", strategy).correct(T, y)
    assert r.baseline.shape == y.shape and np.all(np.isfinite(r.baseline))
    assert np.all(r.baseline <= y + 10.0)
