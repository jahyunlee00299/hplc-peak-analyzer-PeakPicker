"""Characterization of the three anchor finders and the shared flank-anchor mask.

hybrid_baseline.find_baseline_anchor_points, improved_baseline.find_anchors and the package anchor finders are
different algorithms (adaptive percentile + MAD outlier cut / cluster-based minima with priority dedup and negative
shift / fixed windows over the whole signal + composite filter). Their outputs are NOT identical on realistic
chromatograms, so they are not merged; the measured overlap is pinned here so a future merge is a conscious act.
"""
import numpy as np
import pytest

from hybrid_baseline import HybridBaselineCorrector
from improved_baseline import ImprovedBaselineCorrector
from peakpicker.baseline import BoundaryAnchorFinder, CompositeAnchorFinder, LocalMinAnchorFinder, ValleyAnchorFinder
from peakpicker.baseline.anchor_filters import baseline_anchor_mask
from peakpicker.config import AnchorFinderConfig
from peakpicker.infrastructure import ScipySignalProcessor


def gauss(x, amp, center, sigma):
    return amp * np.exp(-0.5 * ((x - center) / sigma) ** 2)


T = np.linspace(0.0, 30.0, 3001)
PEAKS = gauss(T, 1000, 8, 0.15) + gauss(T, 600, 12, 0.2) + gauss(T, 1500, 18, 0.15)
FIXTURES = {
    "flat_single": 100.0 + gauss(T, 1000, 10, 0.15),
    "drift_three": 50.0 + 2.0 * T + PEAKS,
    "curved_three": 50.0 + 2.0 * T + 0.05 * (T - 15.0) ** 2 + PEAKS,
}


def noisy(name):
    return FIXTURES[name] + np.random.default_rng(0).normal(0.0, 1.0, T.size)


def package_anchor_indices(y):
    sp, cfg = ScipySignalProcessor(), AnchorFinderConfig()
    finder = CompositeAnchorFinder([LocalMinAnchorFinder(sp, cfg), ValleyAnchorFinder(sp, cfg), BoundaryAnchorFinder(cfg)], cfg)
    return {p.index for p in finder.find_anchors(T, y)}


@pytest.mark.parametrize("name", list(FIXTURES))
def test_hybrid_and_package_finders_are_not_identical(name):
    y = noisy(name)
    hybrid = {p.index for p in HybridBaselineCorrector(T, y).find_baseline_anchor_points()}
    package = package_anchor_indices(y)
    assert hybrid != package


@pytest.mark.parametrize("name", ["drift_three", "curved_three"])
def test_hybrid_and_package_finders_overlap_is_partial_on_drifting_baselines(name):
    """Measured Jaccard on these fixtures: ~0.4 (hybrid 73-75 anchors, package 84-87)."""
    y = noisy(name)
    hybrid = {p.index for p in HybridBaselineCorrector(T, y).find_baseline_anchor_points()}
    package = package_anchor_indices(y)
    jaccard = len(hybrid & package) / len(hybrid | package)
    assert jaccard < 0.7


@pytest.mark.parametrize("name", list(FIXTURES))
def test_improved_finder_differs_from_hybrid(name):
    y = noisy(name)
    hybrid = {p.index for p in HybridBaselineCorrector(T, y).find_baseline_anchor_points()}
    improved = {a.index for a in ImprovedBaselineCorrector(T, y).find_anchors()}
    assert improved != hybrid


def _frozen_legacy_mask(indices, values, intensity, k=7):
    """Frozen copy of HybridBaselineCorrector._baseline_anchor_mask (batch 2) before it delegated."""
    n = len(indices)
    keep = np.ones(n, dtype=bool)
    if n < 6:
        return keep
    floor = 0.005 * np.ptp(intensity)
    for _ in range(3):
        idx_k, val_k = indices[keep], values[keep]
        if len(idx_k) < 6:
            break
        kk = min(k, len(idx_k) - 1)
        resid = np.empty(len(idx_k))
        for j in range(len(idx_k)):
            order = np.argsort(np.abs(idx_k - idx_k[j]))[1:kk + 1]
            resid[j] = val_k[j] - np.median(val_k[order])
        scale = max(1.4826 * np.median(np.abs(resid - np.median(resid))), floor)
        bad = resid > 3.0 * scale
        bad[0] = bad[-1] = False
        if not bad.any():
            break
        keep_positions = np.flatnonzero(keep)
        keep[keep_positions[bad]] = False
    if keep.sum() < 4:
        return np.ones(n, dtype=bool)
    return keep


@pytest.mark.parametrize("name", list(FIXTURES))
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_hybrid_mask_equals_frozen_copy_and_package_helper(name, seed):
    y = FIXTURES[name] + np.random.default_rng(seed).normal(0.0, 1.0, T.size)
    corr = HybridBaselineCorrector(T, y)
    corr.find_baseline_anchor_points()
    idx = np.array([p.index for p in corr.baseline_points])
    vals = np.array([p.value for p in corr.baseline_points])
    frozen = _frozen_legacy_mask(idx, vals, y)
    np.testing.assert_array_equal(corr._baseline_anchor_mask(idx, vals), frozen)
    np.testing.assert_array_equal(baseline_anchor_mask(idx, vals, float(np.ptp(y))), frozen)
