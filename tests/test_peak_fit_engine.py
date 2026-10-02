"""peak_fit_engine must reproduce scipy curve_fit(multi_gaussian | multi_emg) bit for bit."""
import numpy as np
import pytest
from scipy.optimize import curve_fit

import peak_models
from src.peak_fit_engine import IncrementalSum, emg_component, fit_peak_sum

X = np.linspace(3.0, 7.0, 150)


def _problem(kind, seed):
    rng = np.random.default_rng(seed)
    if kind == 'gaussian':
        y = (peak_models.gaussian(X, 100, 4.9, 0.12) + peak_models.gaussian(X, 70, 5.2, 0.14)
             + rng.normal(0, 0.5, X.size))
        p0 = [90, 4.88, 0.1, 60, 5.25, 0.12]
        lo = [9, 4.5, 0.01, 6, 4.8, 0.01]
        hi = [180, 5.3, 0.5, 120, 5.6, 0.5]
    else:
        y = (peak_models.exponentially_modified_gaussian(X, 100, 4.8, 0.08, 0.25)
             + rng.normal(0, 0.3, X.size))
        p0 = [90, 4.8, 0.09, 0.1]
        lo = [9, 4.4, 0.009, 0.001]
        hi = [450, 5.2, 0.45, 1.35]
    return y, p0, lo, hi


@pytest.mark.parametrize('kind,seed', [('gaussian', 1), ('gaussian', 2), ('emg', 1), ('emg', 2)])
def test_fit_is_bit_identical_to_curve_fit(kind, seed):
    y, p0, lo, hi = _problem(kind, seed)
    model = peak_models.multi_gaussian if kind == 'gaussian' else peak_models.multi_emg
    ref, _ = curve_fit(model, X, y, p0=p0, bounds=(lo, hi), maxfev=10000)
    new = fit_peak_sum(X, y, p0, lo, hi, kind=kind, max_nfev=10000)
    np.testing.assert_array_equal(new, ref)


@pytest.mark.parametrize('kind', ['gaussian', 'emg'])
def test_iteration_cap_raises_like_curve_fit(kind):
    y, p0, lo, hi = _problem(kind, 3)
    model = peak_models.multi_gaussian if kind == 'gaussian' else peak_models.multi_emg
    with pytest.raises(RuntimeError):
        curve_fit(model, X, y, p0=p0, bounds=(lo, hi), maxfev=2)
    with pytest.raises(RuntimeError):
        fit_peak_sum(X, y, p0, lo, hi, kind=kind, max_nfev=2)


def test_emg_component_matches_reference_model_elementwise():
    rng = np.random.default_rng(0)
    for _ in range(200):
        a, c, s, tau = rng.uniform(1, 100), rng.uniform(4, 6), rng.uniform(0.02, 0.3), rng.uniform(0.001, 1.0)
        np.testing.assert_array_equal(emg_component(X, a, c, s, tau),
                                      peak_models.exponentially_modified_gaussian(X, a, c, s, tau))


def test_incremental_sum_equals_full_sum_for_single_parameter_changes():
    rng = np.random.default_rng(1)
    base = np.array([80, 4.6, 0.1, 0.2, 60, 5.0, 0.12, 0.1, 40, 5.4, 0.1, 0.3])
    inc = IncrementalSum(X, 'emg')
    np.testing.assert_array_equal(inc(base), peak_models.multi_emg(X, *base))
    for _ in range(60):
        p = base.copy()
        j = rng.integers(0, p.size)
        p[j] *= 1 + 1e-7 * rng.normal()
        np.testing.assert_array_equal(inc(p), peak_models.multi_emg(X, *p))
