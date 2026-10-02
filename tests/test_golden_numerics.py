"""Golden safety-net tests for legacy numerics (hybrid baseline, deconvolution, area integration).

Every expectation is ANALYTIC TRUTH of a synthetic chromatogram built here (known Gaussian /
exponentially-modified peaks on a known baseline, seeded noise) -- never "whatever the code
currently prints". Where the current code misses the analytic truth the test is a strict xfail
carrying the precise reason, so a fix flips it to XPASS (strict -> failure) and the marker must
then be removed. These tests exist to protect future refactors of src/hybrid_baseline.py,
src/peak_deconvolution.py, src/peak_models.py and src/peak_integrator.py.
"""
import numpy as np
import pytest
from scipy.integrate import trapezoid
from scipy.stats import exponnorm

import peak_integrator
import peak_models
from hybrid_baseline import HybridBaselineCorrector
from peak_deconvolution import PeakDeconvolution

SQRT_2PI = np.sqrt(2.0 * np.pi)


def gauss(x, amp, center, sigma):
    return amp * np.exp(-0.5 * ((x - center) / sigma) ** 2)


def gauss_area(amp, sigma):
    return amp * sigma * SQRT_2PI


# --------------------------------------------------------------------------------------
# Hybrid baseline
# --------------------------------------------------------------------------------------
BASE_PEAKS = [(1000.0, 8.0, 0.15), (600.0, 12.0, 0.20), (1500.0, 18.0, 0.15)]  # (amp, rt, sigma)
BASE_AREA_RTOL = 0.08          # "a few %": baseline error is allowed to cost <= 8 % of a peak area


def make_baseline_chromatogram(curved: bool, seed: int = 0, noise: float = 1.0):
    t = np.linspace(0.0, 30.0, 3001)
    base = 50.0 + 2.0 * t
    if curved:
        base = base + 0.05 * (t - 15.0) ** 2
    y = base.copy()
    for amp, rt, sig in BASE_PEAKS:
        y += gauss(t, amp, rt, sig)
    y += np.random.default_rng(seed).normal(0.0, noise, t.size)
    return t, y, base


def area_recoveries(t, y, baseline):
    """Corrected area of each peak (window +-6 sigma) divided by its analytic area."""
    corrected = y - baseline
    out = []
    for amp, rt, sig in BASE_PEAKS:
        sel = (t > rt - 6 * sig) & (t < rt + 6 * sig)
        out.append(trapezoid(corrected[sel], t[sel]) / gauss_area(amp, sig))
    return np.array(out)


@pytest.mark.parametrize("method", ["weighted_spline", "adaptive_connect", "robust_fit"])
@pytest.mark.parametrize("curved", [False, True], ids=["linear_base", "curved_base"])
def test_hybrid_baseline_contract(method, curved):
    """Shape/finite/never-above-signal contract holds for every method."""
    t, y, _ = make_baseline_chromatogram(curved)
    baseline = HybridBaselineCorrector(t, y).generate_hybrid_baseline(method=method)
    assert baseline.shape == y.shape
    assert np.all(np.isfinite(baseline))
    assert np.all(baseline <= y + 1e-9)


_WEAK_ANCHORS = (
    "find_baseline_anchor_points picks the lowest point of every fixed-size window even when the whole "
    "window lies on a peak flank (anchors at t=8.39/12.34/17.61 with values 101/216/137 vs true baseline "
    "~67/75/85); their weights are small but not zero, so the baseline climbs under the peaks (apex error "
    "up to +130 on a 600-high peak; its area is recovered at ~68 % instead of 100 %)."
)


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("weighted_spline", marks=pytest.mark.xfail(strict=True, reason=_WEAK_ANCHORS)),
        pytest.param("adaptive_connect", marks=pytest.mark.xfail(strict=True, reason=_WEAK_ANCHORS)),
        "robust_fit",
    ],
)
@pytest.mark.parametrize("curved", [False, True], ids=["linear_base", "curved_base"])
def test_hybrid_baseline_recovers_peak_areas(method, curved):
    """Three well-separated Gaussians on a drifting baseline: each area within BASE_AREA_RTOL."""
    t, y, base = make_baseline_chromatogram(curved)
    baseline = HybridBaselineCorrector(t, y).generate_hybrid_baseline(method=method)
    ratios = area_recoveries(t, y, baseline)
    assert np.all(np.abs(ratios - 1.0) < BASE_AREA_RTOL), f"area recovery per peak: {ratios.round(3)}"


@pytest.mark.xfail(strict=True, reason=_WEAK_ANCHORS + " Simplest case (flat baseline 100, one 1000-high peak): an "
                   "anchor at the peak upslope (t=9.8, value 511) lifts the baseline to ~357 at the apex; area recovered ~64 %.")
def test_hybrid_baseline_flat_single_peak_default_method():
    """The default method on the simplest case (flat baseline, one peak)."""
    t = np.linspace(0.0, 20.0, 2001)
    y = 100.0 + gauss(t, 1000.0, 10.0, 0.15) + np.random.default_rng(3).normal(0.0, 1.0, t.size)
    baseline = HybridBaselineCorrector(t, y).generate_hybrid_baseline()
    sel = (t > 10 - 0.9) & (t < 10 + 0.9)
    ratio = trapezoid((y - baseline)[sel], t[sel]) / gauss_area(1000.0, 0.15)
    assert abs(ratio - 1.0) < BASE_AREA_RTOL, ratio


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("curved", [False, True], ids=["linear_base", "curved_base"])
def test_optimize_baseline_with_linear_peaks_recovers_areas(curved, seed):
    """The path the production scripts use (robust_fit + linear peak segments) is accurate to ~1 %."""
    t, y, _ = make_baseline_chromatogram(curved, seed=seed)
    baseline, params = HybridBaselineCorrector(t, y).optimize_baseline_with_linear_peaks()
    ratios = area_recoveries(t, y, baseline)
    assert np.all(np.abs(ratios - 1.0) < 0.03), f"area recovery per peak: {ratios.round(3)}"


def test_area_check_rejects_biased_baseline():
    """Refutation of the harness itself: a baseline lifted under the peaks must FAIL the area criterion."""
    t, y, base = make_baseline_chromatogram(curved=False)
    assert np.all(np.abs(area_recoveries(t, y, base) - 1.0) < 0.01)          # truth passes
    bump = sum(gauss(t, 0.25 * a, rt, 2 * s) for a, rt, s in BASE_PEAKS)     # 25 %-of-height bump
    ratios = area_recoveries(t, y, base + bump)
    assert not np.all(np.abs(ratios - 1.0) < BASE_AREA_RTOL), ratios


# --------------------------------------------------------------------------------------
# Peak models
# --------------------------------------------------------------------------------------
def test_gaussian_model_area_and_apex():
    x = np.linspace(0, 10, 5001)
    y = peak_models.gaussian(x, 100.0, 5.0, 0.3)
    assert y.max() == pytest.approx(100.0, rel=1e-6)
    assert x[np.argmax(y)] == pytest.approx(5.0, abs=2e-3)
    assert trapezoid(y, x) == pytest.approx(gauss_area(100.0, 0.3), rel=1e-4)


def test_emg_model_matches_scipy_exponnorm():
    x = np.linspace(0, 10, 2001)
    sigma, tau, mu = 0.25, 0.4, 4.0
    model = peak_models.exponentially_modified_gaussian(x, 1.0, mu, sigma, tau)
    ref = exponnorm.pdf(x, tau / sigma, loc=mu, scale=sigma)
    assert x[np.argmax(model)] == pytest.approx(x[np.argmax(ref)], abs=0.02)
    np.testing.assert_allclose(model / model.max(), ref / ref.max(), atol=1e-3)


def test_emg_model_small_tau_is_finite_gaussian_limit():
    """tau -> 0 must not overflow and must converge to the Gaussian of the same amplitude."""
    x = np.linspace(0, 10, 2001)
    gaussian_ref = peak_models.gaussian(x, 5.0, 4.0, 0.25)
    for tau in (1e-9, 1e-6, 1e-3):
        model = peak_models.exponentially_modified_gaussian(x, 5.0, 4.0, 0.25, tau)
        assert np.all(np.isfinite(model))
        np.testing.assert_allclose(model, gaussian_ref, atol=5.0 * (1e-6 + 10 * tau))   # shrinks with tau


@pytest.mark.parametrize("sigma,tau", [(0.1, 2.0), (0.25, 1.5)])
def test_emg_model_large_tau_area_and_scipy_shape(sigma, tau):
    """Strong tailing: area is amplitude*sigma*sqrt(2 pi) (Gaussian-equivalent) and shape equals exponnorm."""
    x = np.linspace(-5.0, 60.0, 65001)
    model = peak_models.exponentially_modified_gaussian(x, 3.0, 4.0, sigma, tau)
    assert np.all(np.isfinite(model))
    assert trapezoid(model, x) == pytest.approx(gauss_area(3.0, sigma), rel=2e-3)
    ref = exponnorm.pdf(x, tau / sigma, loc=4.0, scale=sigma)
    np.testing.assert_allclose(model / model.max(), ref / ref.max(), atol=1e-6)


def test_emg_model_negative_tau_is_mirror_image():
    """Fronting peak (tau<0): mirror of the tailing peak, same area."""
    x = np.linspace(0, 8, 4001)
    tail = peak_models.exponentially_modified_gaussian(x, 2.0, 4.0, 0.2, 0.3)
    front = peak_models.exponentially_modified_gaussian(x, 2.0, 4.0, 0.2, -0.3)
    np.testing.assert_allclose(front, tail[::-1], atol=1e-9)
    assert x[np.argmax(front)] < 4.0 < x[np.argmax(tail)]


# --------------------------------------------------------------------------------------
# Deconvolution (Gaussian / EMG)
# --------------------------------------------------------------------------------------
RT = np.linspace(0.0, 10.0, 1000)
DECON_AREA_RTOL = 0.05
DECON_RT_ATOL = 0.03           # minutes (3 grid points of 0.01 min)


def run_decon(signal, **kwargs):
    idx = np.where(signal > signal.max() * 0.01)[0]
    return PeakDeconvolution(**kwargs).analyze_peak(RT, signal, idx[0], idx[-1], force_deconvolution=True)


def noisy(signal, seed, sd=1.0):
    return signal + np.random.default_rng(seed).normal(0.0, sd, signal.size)


def test_deconvolution_single_gaussian():
    sig = noisy(gauss(RT, 100.0, 5.0, 0.3), seed=1)
    res = run_decon(sig)
    assert res.success and res.n_components == 1
    comp = res.components[0]
    assert comp.retention_time == pytest.approx(5.0, abs=DECON_RT_ATOL)
    assert comp.sigma == pytest.approx(0.3, rel=0.05)
    assert comp.area == pytest.approx(gauss_area(100.0, 0.3), rel=DECON_AREA_RTOL)
    assert res.total_area == pytest.approx(gauss_area(100.0, 0.3), rel=DECON_AREA_RTOL)


def test_deconvolution_resolved_pair():
    """Two equal Gaussians 4 sigma apart: both found, correct RT and area."""
    sig = noisy(gauss(RT, 100.0, 4.0, 0.25) + gauss(RT, 100.0, 5.0, 0.25), seed=3)
    res = run_decon(sig)
    assert res.success and res.n_components == 2
    comps = sorted(res.components, key=lambda c: c.retention_time)
    for comp, rt in zip(comps, (4.0, 5.0)):
        assert comp.retention_time == pytest.approx(rt, abs=DECON_RT_ATOL)
        assert comp.area == pytest.approx(gauss_area(100.0, 0.25), rel=DECON_AREA_RTOL)


def test_deconvolution_unequal_shoulder_pair():
    """Amplitude 100 and 60, 3.6 sigma apart (second is a shoulder): both found with correct areas."""
    sig = noisy(gauss(RT, 100.0, 4.0, 0.25) + gauss(RT, 60.0, 4.9, 0.25), seed=3)
    res = run_decon(sig)
    assert res.success and res.n_components == 2
    comps = sorted(res.components, key=lambda c: c.retention_time)
    assert comps[0].area == pytest.approx(gauss_area(100.0, 0.25), rel=DECON_AREA_RTOL)
    assert comps[1].area == pytest.approx(gauss_area(60.0, 0.25), rel=DECON_AREA_RTOL)


def _overlapped_pair():
    return noisy(gauss(RT, 100.0, 4.5, 0.3) + gauss(RT, 70.0, 5.2, 0.35), seed=1)


def test_deconvolution_overlapped_pair_total_area_conserved():
    """Even when components are mis-counted the summed area must match the analytic sum."""
    res = run_decon(_overlapped_pair())
    truth = gauss_area(100.0, 0.3) + gauss_area(70.0, 0.35)
    assert res.success
    assert res.total_area == pytest.approx(truth, rel=DECON_AREA_RTOL)


@pytest.mark.xfail(
    strict=True,
    reason="Two overlapped Gaussians (100@4.5 sigma .3, 70@5.2 sigma .35; 2.15 sigma apart) are reported as ONE "
    "component (sigma .517): deconvolve_peak breaks out of the n_peaks loop as soon as fit_quality > 0.95, "
    "and a single Gaussian already reaches R2=0.975, so the 2-component model is never tried.",
)
def test_deconvolution_overlapped_pair_component_count():
    res = run_decon(_overlapped_pair())
    assert res.n_components == 2


@pytest.mark.parametrize("sigma,tau", [(0.2, 0.3), (0.25, 0.4)])
def test_deconvolution_tailing_peak_area(sigma, tau):
    sig = noisy(500.0 * exponnorm.pdf(RT, tau / sigma, loc=4.0, scale=sigma), seed=5)
    res = run_decon(sig)
    assert res.success
    assert res.total_area == pytest.approx(500.0, rel=DECON_AREA_RTOL)


@pytest.mark.parametrize("sigma,tau", [(0.1, 0.5), (0.2, 0.8)])
def test_fit_n_emg_strongly_tailing_peak_tight_area(sigma, tau):
    """tau/sigma = 4-5: the old tau (<=3 sigma) and amplitude (<=2x apex) bounds clipped the fit (-4 % area)."""
    sig = noisy(500.0 * exponnorm.pdf(RT, tau / sigma, loc=4.0, scale=sigma), seed=5)
    res = PeakDeconvolution()._fit_n_emg(RT, sig, [RT[np.argmax(sig)]], 4.0)
    assert res.success
    assert res.total_area == pytest.approx(500.0, rel=0.01)
    assert res.components[0].retention_time == pytest.approx(4.0, abs=0.05)


def test_fit_n_emg_on_pure_gaussian_stays_gaussian_in_the_limit():
    """Adverse: a symmetric peak fitted with the EMG model must give the Gaussian area/centre, not an invented tail."""
    sig = noisy(gauss(RT, 100.0, 5.0, 0.3), seed=1)
    res = PeakDeconvolution()._fit_n_emg(RT, sig, [5.0], 5.0)
    assert res.success
    assert res.total_area == pytest.approx(gauss_area(100.0, 0.3), rel=0.02)
    assert res.components[0].retention_time == pytest.approx(5.0, abs=0.03)


def test_deconvolution_rejects_too_small_region():
    """Adverse input: a region of <5 points must fail cleanly, not raise or invent components."""
    sig = gauss(RT, 100.0, 5.0, 0.3)
    res = PeakDeconvolution().deconvolve_peak(RT, sig, 500, 503)
    assert not res.success and res.n_components == 0


# --------------------------------------------------------------------------------------
# Peak area integration (src/peak_integrator.py; area unit = signal * s, time axis in min)
# --------------------------------------------------------------------------------------
INT_T = np.linspace(0.0, 20.0, 4001)
INT_AREA_TRUTH = gauss_area(1000.0, 0.1) * 60.0


def int_signal(baseline, extra=None, seed=0):
    y = baseline + gauss(INT_T, 1000.0, 10.0, 0.1)
    if extra is not None:
        y = y + extra
    return y + np.random.default_rng(seed).normal(0.0, 0.5, INT_T.size)


def test_integrate_peak_noise_free_exact_and_unit_conversion():
    y = 100.0 + gauss(INT_T, 1000.0, 10.0, 0.1)
    area = peak_integrator.integrate_peak(INT_T, y, 10.0)
    assert area == pytest.approx(INT_AREA_TRUTH, rel=0.005)     # minutes -> seconds (x60) included


@pytest.mark.parametrize("slope", [0.0, 3.0], ids=["flat", "drifting"])
def test_integrate_peak_full_noisy(slope):
    area = peak_integrator.integrate_peak(INT_T, int_signal(100.0 + slope * INT_T), 10.0)
    assert area == pytest.approx(INT_AREA_TRUTH, rel=0.03)


@pytest.mark.parametrize("mode", ["left_half", "right_half"])
def test_integrate_peak_half_modes_are_half_the_area(mode):
    area = peak_integrator.integrate_peak(INT_T, int_signal(100.0 + 0.0 * INT_T), 10.0, mode=mode)
    assert area == pytest.approx(0.5 * INT_AREA_TRUTH, rel=0.04)


def test_integrate_peak_neighbour_does_not_leak_into_target():
    """Second resolved peak 1.5 min away must not change the first peak's area materially."""
    y = int_signal(100.0 + 0.0 * INT_T, extra=gauss(INT_T, 600.0, 11.5, 0.1))
    first = peak_integrator.integrate_peak(INT_T, y, 10.0, search_half_width=0.7)
    second = peak_integrator.integrate_peak(INT_T, y, 11.5, search_half_width=0.7)
    assert first == pytest.approx(INT_AREA_TRUTH, rel=0.03)
    assert second == pytest.approx(gauss_area(600.0, 0.1) * 60.0, rel=0.05)


def test_integrate_peak_detailed_reports_apex_and_bounds_zero_baseline():
    """With a zero baseline the 0.3 %-of-max cutoff is hit at +-3.4 sigma: bounds must be ~ +-0.34 min."""
    y = gauss(INT_T, 1000.0, 10.0, 0.1)
    d = peak_integrator.integrate_peak_detailed(INT_T, y, 10.0)
    assert d["peak_rt"] == pytest.approx(10.0, abs=0.01)
    assert d["rt_lo"] == pytest.approx(10.0 - 0.34, abs=0.02)
    assert d["rt_hi"] == pytest.approx(10.0 + 0.34, abs=0.02)


@pytest.mark.xfail(
    strict=True,
    reason="find_peak_boundaries compares the signal with peak_max * threshold_ratio in ABSOLUTE units, not baseline-"
    "subtracted: with a baseline of 100 on a 1000-high peak the cutoff (3.3) is never reached, so both boundaries "
    "fall back to the search-window edge (+-1.2 min = +-12 sigma) instead of ~+-3.4 sigma. The area stays right only "
    "because the straight valley baseline is subtracted; a neighbouring peak inside the window would be swallowed.",
)
def test_integrate_peak_boundaries_with_offset_baseline():
    y = 100.0 + gauss(INT_T, 1000.0, 10.0, 0.1)
    d = peak_integrator.integrate_peak_detailed(INT_T, y, 10.0)
    assert d["rt_hi"] - d["rt_lo"] < 8 * 0.1 + 0.05      # within ~ +-4 sigma


def test_integrate_peak_adverse_inputs_raise():
    y = 100.0 + gauss(INT_T, 1000.0, 10.0, 0.1)
    with pytest.raises(ValueError):
        peak_integrator.integrate_peak(INT_T, y, 50.0)              # hint outside the data
    with pytest.raises(ValueError):
        peak_integrator.integrate_peak(INT_T, y, 10.0, mode="bad")  # unknown mode
