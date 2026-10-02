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


@pytest.mark.parametrize(
    "method",
    ["weighted_spline", "adaptive_connect", "robust_fit"],
)
@pytest.mark.parametrize("curved", [False, True], ids=["linear_base", "curved_base"])
def test_hybrid_baseline_recovers_peak_areas(method, curved):
    """Three well-separated Gaussians on a drifting baseline: each area within BASE_AREA_RTOL."""
    t, y, base = make_baseline_chromatogram(curved)
    baseline = HybridBaselineCorrector(t, y).generate_hybrid_baseline(method=method)
    ratios = area_recoveries(t, y, baseline)
    assert np.all(np.abs(ratios - 1.0) < BASE_AREA_RTOL), f"area recovery per peak: {ratios.round(3)}"


def test_hybrid_baseline_flat_single_peak_default_method():
    """The default method on the simplest case (flat baseline, one peak)."""
    t = np.linspace(0.0, 20.0, 2001)
    y = 100.0 + gauss(t, 1000.0, 10.0, 0.15) + np.random.default_rng(3).normal(0.0, 1.0, t.size)
    baseline = HybridBaselineCorrector(t, y).generate_hybrid_baseline()
    sel = (t > 10 - 0.9) & (t < 10 + 0.9)
    ratio = trapezoid((y - baseline)[sel], t[sel]) / gauss_area(1000.0, 0.15)
    assert abs(ratio - 1.0) < BASE_AREA_RTOL, ratio


@pytest.mark.parametrize("method", ["weighted_spline", "adaptive_connect"])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_hybrid_baseline_flat_single_peak_seeds(method, seed):
    t = np.linspace(0.0, 20.0, 2001)
    y = 100.0 + gauss(t, 1000.0, 10.0, 0.15) + np.random.default_rng(seed).normal(0.0, 1.0, t.size)
    baseline = HybridBaselineCorrector(t, y).generate_hybrid_baseline(method=method)
    sel = (t > 10 - 0.9) & (t < 10 + 0.9)
    ratio = trapezoid((y - baseline)[sel], t[sel]) / gauss_area(1000.0, 0.15)
    assert abs(ratio - 1.0) < 0.03, ratio


@pytest.mark.parametrize("curved", [False, True], ids=["linear_base", "curved_base"])
def test_flank_anchor_filter_keeps_every_anchor_on_a_peak_free_drift(curved):
    """Adverse: with NO peak the flank-anchor filter must not discard legitimate drift/curvature anchors,
    and the weighted_spline baseline must then be identical to what it was without the filter."""
    t = np.linspace(0.0, 30.0, 3001)
    truth = 50.0 + 2.0 * t + (0.05 * (t - 15.0) ** 2 if curved else 0.0)
    y = truth + np.random.default_rng(4).normal(0.0, 1.0, t.size)
    corr = HybridBaselineCorrector(t, y)
    corr.find_baseline_anchor_points()
    idx = np.array([p.index for p in corr.baseline_points])
    vals = np.array([p.value for p in corr.baseline_points])
    assert corr._baseline_anchor_mask(idx, vals).all()


def test_flank_anchor_filter_rejects_flank_anchor_but_keeps_flat_baseline_anchors():
    t = np.linspace(0.0, 20.0, 2001)
    y = 100.0 + gauss(t, 1000.0, 10.0, 0.15) + np.random.default_rng(3).normal(0.0, 1.0, t.size)
    corr = HybridBaselineCorrector(t, y)
    corr.find_baseline_anchor_points()
    idx = np.array([p.index for p in corr.baseline_points])
    vals = np.array([p.value for p in corr.baseline_points])
    keep = corr._baseline_anchor_mask(idx, vals)
    assert not keep[vals > 120].any() and keep[vals < 105].all()


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


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("kind", ["gauss_sd1", "gauss_sd4", "gauss_clean", "emg", "emg_strong"])
def test_deconvolution_single_peak_is_never_oversplit(kind, seed):
    """Guard for the BIC component selection: a truly single peak (symmetric, noisy, tailing) stays ONE component."""
    rng = np.random.default_rng(seed)
    if kind.startswith("gauss"):
        sd = {"gauss_sd1": 1.0, "gauss_sd4": 4.0, "gauss_clean": 0.0}[kind]
        sig = gauss(RT, 100.0, 5.0, 0.3) + rng.normal(0.0, sd, RT.size)
        truth = gauss_area(100.0, 0.3)
    else:
        sigma, tau = (0.25, 0.4) if kind == "emg" else (0.1, 0.5)
        sig = 500.0 * exponnorm.pdf(RT, tau / sigma, loc=4.0, scale=sigma) + rng.normal(0.0, 1.0, RT.size)
        truth = 500.0
    res = run_decon(sig)
    assert res.success and res.n_components == 1
    assert res.total_area == pytest.approx(truth, rel=DECON_AREA_RTOL)


@pytest.mark.parametrize("seed", range(4))
def test_deconvolution_overlapped_pair_component_count_and_areas_over_seeds(seed):
    """2.15 sigma apart: two components over several noise realisations, areas near the analytic values."""
    sig = noisy(gauss(RT, 100.0, 4.5, 0.3) + gauss(RT, 70.0, 5.2, 0.35), seed=seed)
    res = run_decon(sig)
    assert res.success and res.n_components == 2
    comps = sorted(res.components, key=lambda c: c.retention_time)
    assert comps[0].area == pytest.approx(gauss_area(100.0, 0.3), rel=DECON_AREA_RTOL)
    assert comps[1].area == pytest.approx(gauss_area(70.0, 0.35), rel=DECON_AREA_RTOL)


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
    # threshold_ratio 1e-4: the default 3e-3 cutoff leaves ~3 signal units of tail under the valley line
    # (-0.77 % by design, identical for every baseline offset -- see the next test)
    area = peak_integrator.integrate_peak(INT_T, y, 10.0, threshold_ratio=1e-4)
    assert area == pytest.approx(INT_AREA_TRUTH, rel=0.005)     # minutes -> seconds (x60) included


def test_integrate_peak_default_cutoff_truncation_bias_is_small_and_offset_independent():
    """Documented design bias of the 0.3 % cutoff: about -0.8 % (tail under the valley line), never more than 1 %."""
    areas = [peak_integrator.integrate_peak(INT_T, off + gauss(INT_T, 1000.0, 10.0, 0.1), 10.0)
             for off in (-300.0, 0.0, 100.0)]
    assert areas[0] == pytest.approx(areas[1], rel=1e-9) and areas[2] == pytest.approx(areas[1], rel=1e-9)
    assert areas[1] == pytest.approx(INT_AREA_TRUTH, rel=0.01)
    assert areas[1] < INT_AREA_TRUTH


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


def test_integrate_peak_boundaries_with_offset_baseline():
    y = 100.0 + gauss(INT_T, 1000.0, 10.0, 0.1)
    d = peak_integrator.integrate_peak_detailed(INT_T, y, 10.0)
    assert d["rt_hi"] - d["rt_lo"] < 8 * 0.1 + 0.05      # within ~ +-4 sigma


@pytest.mark.parametrize("offset", [-300.0, 0.0, 100.0, 5000.0], ids=["negative", "zero", "offset", "large_offset"])
def test_integrate_peak_bounds_and_area_independent_of_baseline_offset(offset):
    """Boundaries and area must not depend on the absolute baseline level (negative, zero, large)."""
    y = offset + gauss(INT_T, 1000.0, 10.0, 0.1)
    d = peak_integrator.integrate_peak_detailed(INT_T, y, 10.0)
    assert d["rt_lo"] == pytest.approx(10.0 - 0.34, abs=0.03)
    assert d["rt_hi"] == pytest.approx(10.0 + 0.34, abs=0.03)
    assert d["area"] == pytest.approx(INT_AREA_TRUTH, rel=0.01)


def test_integrate_peak_offset_baseline_stops_at_valley_of_neighbour():
    """Offset baseline + neighbour 0.9 min away inside the window: the target must stop at the valley, not swallow it."""
    y = 100.0 + gauss(INT_T, 1000.0, 10.0, 0.1) + gauss(INT_T, 800.0, 10.9, 0.1)
    d = peak_integrator.integrate_peak_detailed(INT_T, y, 10.0)
    assert d["rt_hi"] < 10.6
    assert d["area"] == pytest.approx(INT_AREA_TRUTH, rel=0.03)


def test_integrate_peak_adverse_inputs_raise():
    y = 100.0 + gauss(INT_T, 1000.0, 10.0, 0.1)
    with pytest.raises(ValueError):
        peak_integrator.integrate_peak(INT_T, y, 50.0)              # hint outside the data
    with pytest.raises(ValueError):
        peak_integrator.integrate_peak(INT_T, y, 10.0, mode="bad")  # unknown mode
