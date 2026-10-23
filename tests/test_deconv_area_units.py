"""Pin the area unit of deconvolved components against the valley integrator.

``DeconvolvedPeak.area`` is signal * min, ``integrate_peak`` returns signal * s: ``area_signal_s`` bridges them.
Synthetic single Gaussian, no noise, so the two methods must agree closely.
"""
import numpy as np

from src.peak_deconvolution import PeakDeconvolution
from src.peak_integrator import integrate_peak
from src.peak_models import gaussian


def _clean_peak():
    t = np.arange(5.0, 15.0, 1 / 120)
    return t, gaussian(t, 1000.0, 9.0, 0.12)


def test_area_signal_s_matches_valley_integration():
    t, y = _clean_peak()
    i0, i1 = int(np.searchsorted(t, 8.4)), int(np.searchsorted(t, 9.6))
    res = PeakDeconvolution().analyze_peak(t, y, i0, i1, force_deconvolution=True)
    assert res is not None and res.success and res.n_components == 1
    comp = res.components[0]
    valley = integrate_peak(t, y, 9.0, 'full', 1.2)
    assert abs(comp.area_signal_s / valley - 1.0) < 0.01


def test_area_signal_s_is_sixty_times_area():
    t, y = _clean_peak()
    i0, i1 = int(np.searchsorted(t, 8.4)), int(np.searchsorted(t, 9.6))
    comp = PeakDeconvolution().analyze_peak(t, y, i0, i1, force_deconvolution=True).components[0]
    assert comp.area_signal_s == comp.area * 60.0
    # analytic: amplitude * sigma * sqrt(2 pi) in signal * min
    assert abs(comp.area / (1000.0 * 0.12 * np.sqrt(2 * np.pi)) - 1.0) < 0.01
