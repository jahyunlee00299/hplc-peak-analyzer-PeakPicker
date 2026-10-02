"""
EMG Peak Fitter
===============

Exponentially Modified Gaussian (EMG) model for asymmetric HPLC peaks.

EMG is the standard model for chromatographic tailing peaks (USP tailing factor > 1).
It is the convolution of a Gaussian with an exponential decay:

  f(x) = (A * σ / τ) * sqrt(π/2) * exp(σ²/(2τ²) - (x-μ)/τ)
                       * erfc((σ/τ - (x-μ)/σ) / sqrt(2))

Parameters:
  A   — amplitude (peak area ∝ A)
  μ   — centre (retention time)
  σ   — Gaussian width (sigma)
  τ   — exponential decay constant (tailing: τ > 0)

References:
  Jeansonne & Foley (1991) J. Chromatogr. Sci. 29, 258-266
  Kalambet et al. (2011) J. Chemometrics 25, 352-356
"""

import logging
from typing import List, Optional, Tuple

import numpy as np
from scipy.special import erfc, erfcx
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)

try:
    import lmfit
    _LMFIT_AVAILABLE = True
except ImportError:
    _LMFIT_AVAILABLE = False
    logger.info("lmfit not installed — EMG fitting will use scipy.optimize.curve_fit.")


# ─────────────────────────────────────────────────────────────────────────────
# Core model functions
# ─────────────────────────────────────────────────────────────────────────────

def exponentially_modified_gaussian(x, amplitude, center, sigma, tau):
    """
    Exponentially Modified Gaussian (EMG) peak model - the single EMG implementation.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    amplitude : float
        Gaussian-equivalent peak height (area = amplitude * sigma * sqrt(2*pi))
    center : float
        Gaussian centre mu (not the apex of a tailing peak)
    sigma : float
        Gaussian width parameter
    tau : float
        Exponential decay time constant. Positive = right tailing, negative = left
        tailing (fronting, mirror image); |tau| < 1e-10 returns the pure Gaussian.
    """
    if abs(tau) < 1e-10:
        # If tau is very small, just return Gaussian
        return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))

    x = np.asarray(x, dtype=float)
    u = x - center
    if tau < 0:
        # Fronting peak = mirror image of the tailing peak with |tau|
        u = -u
        tau = -tau

    # Standard EMG with Gaussian-equivalent height `amplitude` (area = amplitude*sigma*sqrt(2*pi)):
    #   A/(2*tau) * exp(sigma^2/(2*tau^2) - u/tau) * erfc((sigma/tau - u/sigma)/sqrt(2))
    # Written overflow-free: for b >= 0 use exp(-u^2/(2 sigma^2)) * erfcx(b), since
    # exp(a)*erfc(b) = exp(a - b^2)*erfcx(b) and a - b^2 = -u^2/(2 sigma^2).
    b = (sigma / tau - u / sigma) / np.sqrt(2.0)
    prefactor = amplitude * sigma * np.sqrt(2 * np.pi) / (2 * tau)
    with np.errstate(over='ignore', invalid='ignore'):
        stable = np.exp(-u ** 2 / (2 * sigma ** 2)) * erfcx(np.where(b >= 0, b, 0.0))
        tail = np.exp(sigma ** 2 / (2 * tau ** 2) - u / tau) * erfc(np.where(b < 0, b, 0.0))
    return prefactor * np.where(b >= 0, stable, tail)


def emg(x: np.ndarray, amplitude: float, center: float,
        sigma: float, tau: float) -> np.ndarray:
    """
    EMG for the fitters: ``exponentially_modified_gaussian`` with |sigma| >= 1e-10 and
    tau forced to a positive (right-tailing) magnitude >= 1e-10, as the bounded fits expect.
    """
    sigma = max(abs(sigma), 1e-10)
    tau = max(abs(tau), 1e-10)
    return exponentially_modified_gaussian(x, amplitude, center, sigma, tau)


def multi_emg(x: np.ndarray, *params) -> np.ndarray:
    """Sum of N EMG peaks. params = [A0,μ0,σ0,τ0, A1,μ1,σ1,τ1, ...]"""
    y = np.zeros_like(x, dtype=float)
    for i in range(0, len(params), 4):
        y += emg(x, *params[i:i + 4])
    return y


# ─────────────────────────────────────────────────────────────────────────────
# Fitter class
# ─────────────────────────────────────────────────────────────────────────────

class EmgFitter:
    """
    Fits one or more EMG components to a peak region.

    Prefers lmfit (better bounds handling, richer output) when available;
    falls back to scipy.optimize.curve_fit.
    """

    def __init__(
        self,
        max_iter: int = 5000,
        r2_threshold: float = 0.90,
        force_scipy: bool = False,
    ):
        self.max_iter = max_iter
        self.r2_threshold = r2_threshold
        self._use_lmfit = _LMFIT_AVAILABLE and not force_scipy

    # ------------------------------------------------------------------
    def fit(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        centers: Optional[List[float]] = None,
    ) -> dict:
        """
        Fit EMG model to signal.

        Parameters
        ----------
        time : np.ndarray
            Time array (RT values)
        signal : np.ndarray
            Baseline-corrected intensity
        centers : list of float, optional
            Initial RT guesses for each component.
            If None, single peak at argmax.

        Returns
        -------
        dict with keys:
          - 'r2'        : float — goodness of fit
          - 'params'    : list of (amplitude, center, sigma, tau) per component
          - 'fitted'    : np.ndarray — fitted curve
          - 'areas'     : list of float — individual component areas
          - 'method'    : str — 'lmfit' or 'scipy'
        """
        if centers is None:
            centers = [float(time[np.argmax(signal)])]

        p0, bounds = self._build_init(time, signal, centers)

        if self._use_lmfit:
            return self._fit_lmfit(time, signal, centers, p0, bounds)
        return self._fit_scipy(time, signal, p0, bounds)

    # ------------------------------------------------------------------
    def _build_init(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        centers: List[float],
    ) -> Tuple[list, tuple]:
        """Build initial parameter guess and bounds."""
        time_range = float(time[-1] - time[0])
        p0, lo, hi = [], [], []

        for c in centers:
            idx = int(np.argmin(np.abs(time - c)))
            amp = max(float(signal[idx]), 1.0)
            sigma = max(time_range * 0.02, 0.01)
            tau = sigma * 0.5

            p0.extend([amp, c, sigma, tau])
            lo.extend([0.0, time[0], 1e-6, 1e-6])
            hi.extend([amp * 5, time[-1], time_range, time_range])

        return p0, (lo, hi)

    # ------------------------------------------------------------------
    def _fit_scipy(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        p0: list,
        bounds: tuple,
    ) -> dict:
        try:
            popt, _ = curve_fit(
                multi_emg, time, signal,
                p0=p0, bounds=bounds,
                maxfev=self.max_iter,
                method='trf',
            )
        except Exception as e:
            logger.warning("EMG scipy fit failed: %s — returning flat.", e)
            return self._failed_result(time, signal)

        fitted = multi_emg(time, *popt)
        r2 = self._r2(signal, fitted)
        params = [tuple(popt[i:i + 4]) for i in range(0, len(popt), 4)]
        areas = [self._emg_area(a, s, t) for a, _, s, t in params]

        return {'r2': r2, 'params': params, 'fitted': fitted,
                'areas': areas, 'method': 'scipy'}

    # ------------------------------------------------------------------
    def _fit_lmfit(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        centers: List[float],
        p0: list,
        bounds: tuple,
    ) -> dict:
        lo, hi = bounds
        model_params = lmfit.Parameters()

        for k, c in enumerate(centers):
            idx = int(np.argmin(np.abs(time - c)))
            amp = max(float(signal[idx]), 1.0)
            sigma = max((time[-1] - time[0]) * 0.02, 0.01)
            tau = sigma * 0.5

            model_params.add(f'amp_{k}',    value=amp,   min=0,         max=amp * 5)
            model_params.add(f'center_{k}', value=c,     min=time[0],   max=time[-1])
            model_params.add(f'sigma_{k}',  value=sigma, min=1e-6,      max=time[-1] - time[0])
            model_params.add(f'tau_{k}',    value=tau,   min=1e-6,      max=time[-1] - time[0])

        def residual(params):
            y = np.zeros_like(time, dtype=float)
            for k in range(len(centers)):
                y += emg(time,
                         params[f'amp_{k}'].value,
                         params[f'center_{k}'].value,
                         params[f'sigma_{k}'].value,
                         params[f'tau_{k}'].value)
            return y - signal

        try:
            result = lmfit.minimize(residual, model_params, method='least_squares',
                                    max_nfev=self.max_iter)
        except Exception as e:
            logger.warning("EMG lmfit fit failed: %s — falling back to scipy.", e)
            return self._fit_scipy(time, signal, p0, bounds)

        fitted = signal + result.residual
        r2 = self._r2(signal, fitted)
        params = []
        areas = []
        for k in range(len(centers)):
            a = result.params[f'amp_{k}'].value
            mu = result.params[f'center_{k}'].value
            s = result.params[f'sigma_{k}'].value
            t = result.params[f'tau_{k}'].value
            params.append((a, mu, s, t))
            areas.append(self._emg_area(a, s, t))

        return {'r2': r2, 'params': params, 'fitted': fitted,
                'areas': areas, 'method': 'lmfit'}

    # ------------------------------------------------------------------
    @staticmethod
    def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    @staticmethod
    def _emg_area(amplitude: float, sigma: float, tau: float) -> float:
        """Analytical area of EMG: A * σ * sqrt(2π)."""
        return float(amplitude * abs(sigma) * np.sqrt(2 * np.pi))

    @staticmethod
    def _failed_result(time: np.ndarray, signal: np.ndarray) -> dict:
        return {
            'r2': 0.0,
            'params': [],
            'fitted': np.zeros_like(signal),
            'areas': [],
            'method': 'failed',
        }
