"""Characterization of the peak-shape dedup: legacy src/peak_models.py vs peakpicker emg_fitter / gaussian_fitter.

The two ``_ref_*`` functions are frozen copies of the pre-dedup implementations. They are the proof that the
surviving implementation reproduces the old numbers wherever the old numbers were correct, and a documented
list of the regions where the old package EMG was wrong.
"""
import numpy as np
import pytest
from scipy.special import erfc, erfcx
from scipy.stats import exponnorm

import peak_models
from peakpicker.peak_analysis.deconvolution import emg_fitter, gaussian_fitter


def _ref_legacy_emg(x, amplitude, center, sigma, tau):
    """Frozen copy of peak_models.exponentially_modified_gaussian before the dedup."""
    if abs(tau) < 1e-10:
        return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))
    x = np.asarray(x, dtype=float)
    u = x - center
    if tau < 0:
        u = -u
        tau = -tau
    b = (sigma / tau - u / sigma) / np.sqrt(2.0)
    prefactor = amplitude * sigma * np.sqrt(2 * np.pi) / (2 * tau)
    with np.errstate(over='ignore', invalid='ignore'):
        stable = np.exp(-u ** 2 / (2 * sigma ** 2)) * erfcx(np.where(b >= 0, b, 0.0))
        tail = np.exp(sigma ** 2 / (2 * tau ** 2) - u / tau) * erfc(np.where(b < 0, b, 0.0))
    return prefactor * np.where(b >= 0, stable, tail)


def _ref_package_emg(x, amplitude, center, sigma, tau):
    """Frozen copy of peakpicker...emg_fitter.emg before the dedup."""
    sigma = max(abs(sigma), 1e-10)
    tau = max(abs(tau), 1e-10)
    z = (sigma / tau) - (x - center) / sigma
    exponent = np.clip(0.5 * (sigma / tau) ** 2 - (x - center) / tau, -500, 500)
    return (amplitude * sigma / tau * np.sqrt(np.pi / 2) * np.exp(exponent) * erfc(z / np.sqrt(2)))


X = np.linspace(0.0, 20.0, 4001)
GRID = [(a, c, s, t) for a in (1.0, 250.0) for c in (5.0, 10.0) for s in (0.05, 0.2, 0.8) for t in (0.02, 0.1, 0.5, 2.0)]


@pytest.mark.parametrize("params", GRID)
def test_legacy_emg_shim_is_bit_identical_to_frozen_legacy(params):
    np.testing.assert_array_equal(peak_models.exponentially_modified_gaussian(X, *params), _ref_legacy_emg(X, *params))


@pytest.mark.parametrize("params", [(1.0, 10.0, 0.2, -0.3), (5.0, 10.0, 0.2, 0.0), (5.0, 10.0, 0.2, 1e-12), (5.0, 10.0, 0.2, -1e-12)])
def test_legacy_emg_shim_edge_branches_identical(params):
    np.testing.assert_array_equal(peak_models.exponentially_modified_gaussian(X, *params), _ref_legacy_emg(X, *params))


@pytest.mark.parametrize("params", GRID)
def test_package_emg_matches_frozen_package_where_it_was_correct(params):
    """Wherever the old clip(+-500) was inactive (and the value is above 1e-6 of the peak), old == new to 1e-9."""
    a, c, sg, t = params
    new = emg_fitter.emg(X, *params)
    old = _ref_package_emg(X, *params)
    exponent = 0.5 * (sg / t) ** 2 - (X - c) / t
    ok = np.isfinite(old) & (np.abs(exponent) < 500) & (old > 1e-6 * old.max())
    assert ok.sum() > 20
    np.testing.assert_allclose(new[ok], old[ok], rtol=1e-9)


@pytest.mark.parametrize("params", GRID)
def test_package_emg_matches_scipy_exponnorm_everywhere(params):
    """Independent truth over the whole grid, including the far tail where the old clip(+-500) was wrong."""
    a, c, s, t = params
    truth = exponnorm.pdf(X, t / s, loc=c, scale=s) * s * np.sqrt(2 * np.pi) * a
    np.testing.assert_allclose(emg_fitter.emg(X, *params), truth, rtol=1e-6, atol=1e-12 * a)


def test_old_package_emg_collapsed_for_sigma_over_tau_40():
    """Documented difference: sigma=0.8, tau=0.02 (sigma/tau = 40): the old peak maximum was ~2e-10 instead of ~1."""
    old = _ref_package_emg(X, 1.0, 5.0, 0.8, 0.02)
    new = emg_fitter.emg(X, 1.0, 5.0, 0.8, 0.02)
    assert old.max() < 1e-6 and 0.9 < new.max() < 1.01


@pytest.mark.parametrize("params", GRID)
def test_package_emg_equals_legacy_for_positive_tau(params):
    np.testing.assert_array_equal(emg_fitter.emg(X, *params), peak_models.exponentially_modified_gaussian(X, *params))


def test_package_emg_old_overflow_region_was_wrong_and_new_matches_scipy():
    """sigma/tau large (near-Gaussian, the lower tau bound of EmgFitter): the old clip(+-500)+erfc gave 0."""
    sigma, tau = 0.01, 1e-6
    x = np.linspace(9.9, 10.1, 401)
    truth = exponnorm.pdf(x, tau / sigma, loc=10.0, scale=sigma) * (sigma * np.sqrt(2 * np.pi))
    assert np.max(_ref_package_emg(x, 1.0, 10.0, sigma, tau)) < 1e-6          # old: collapsed to ~0
    np.testing.assert_allclose(emg_fitter.emg(x, 1.0, 10.0, sigma, tau), truth, rtol=1e-6, atol=1e-9)


def test_package_emg_keeps_its_old_guards():
    """sigma sign and tau sign are still absolute-valued by the package wrapper (old contract)."""
    a = emg_fitter.emg(X, 3.0, 10.0, -0.2, -0.3)
    b = emg_fitter.emg(X, 3.0, 10.0, 0.2, 0.3)
    np.testing.assert_array_equal(a, b)
    assert np.all(np.isfinite(emg_fitter.emg(X, 3.0, 10.0, 0.2, 0.0)))


def test_multi_emg_package_matches_sum_of_frozen_components():
    p = (3.0, 8.0, 0.2, 0.3, 2.0, 10.0, 0.25, 0.6)
    expected = _ref_package_emg(X, *p[:4]) + _ref_package_emg(X, *p[4:])
    np.testing.assert_allclose(emg_fitter.multi_emg(X, *p), expected, rtol=1e-9, atol=1e-12)


@pytest.mark.parametrize("params", [(100.0, 5.0, 0.3), (3.0, 10.0, 0.05), (1.0, 0.0, 2.0)])
def test_gaussian_identical(params):
    np.testing.assert_array_equal(peak_models.gaussian(X, *params), gaussian_fitter.gaussian(X, *params))


def test_multi_gaussian_identical_and_legacy_validation_kept():
    p = (80.0, 4.0, 0.3, 60.0, 5.5, 0.4)
    np.testing.assert_array_equal(peak_models.multi_gaussian(X, *p), gaussian_fitter.multi_gaussian(X, *p))
    with pytest.raises(ValueError):
        peak_models.multi_gaussian(X, 1.0, 2.0)
    with pytest.raises(ValueError):
        peak_models.multi_emg(X, 1.0, 2.0, 3.0)


def test_legacy_shims_delegate_to_the_package_implementation():
    assert peak_models._gaussian is gaussian_fitter.gaussian
    assert peak_models._emg_model is emg_fitter.exponentially_modified_gaussian


@pytest.mark.parametrize("sigma,tau,seed", [(0.12, 0.35, 0), (0.2, 0.1, 1), (0.15, 0.6, 2)])
def test_emg_fitter_results_unchanged_by_the_dedup(monkeypatch, sigma, tau, seed):
    """End-to-end: EmgFitter on a noisy tailing peak gives the same R2 and area with the frozen old model."""
    t = np.linspace(8.0, 16.0, 800)
    y = 400.0 * exponnorm.pdf(t, tau / sigma, loc=10.0, scale=sigma) + np.random.default_rng(seed).normal(0, 0.5, t.size)
    new = emg_fitter.EmgFitter(force_scipy=True).fit(t, y, [10.0])
    monkeypatch.setattr(emg_fitter, "emg", _ref_package_emg)
    old = emg_fitter.EmgFitter(force_scipy=True).fit(t, y, [10.0])
    assert abs(new["r2"] - old["r2"]) < 1e-6
    assert abs(sum(new["areas"]) / sum(old["areas"]) - 1.0) < 1e-4
    assert abs(sum(new["areas"]) / 400.0 - 1.0) < 0.01
