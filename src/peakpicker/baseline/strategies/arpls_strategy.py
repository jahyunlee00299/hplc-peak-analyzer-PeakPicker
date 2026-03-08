"""
ARPLS / airPLS Baseline Strategies
====================================

Asymmetrically Reweighted Penalized Least Squares (ARPLS) and
Adaptive Iteratively Reweighted PLS (airPLS) baseline correction.

Reference:
  Baek et al. (2015) Analyst 140, 250-257. DOI:10.1039/C4AN01061B
  Zhang et al. (2010) Analyst 135, 1138-1146.

These methods work WITHOUT anchor points — the entire signal is
passed to the optimizer which iteratively assigns low weight to
peak regions and fits a smooth baseline to the background.
"""

import logging
from typing import List

import numpy as np

from ...interfaces import IBaselineStrategy
from ...domain import AnchorPoint, BaselineMethod

logger = logging.getLogger(__name__)

try:
    from pybaselines import Baseline as PyBaseline
    _PYBASELINES_AVAILABLE = True
except ImportError:
    _PYBASELINES_AVAILABLE = False
    logger.warning(
        "pybaselines not installed. ARPLS/airPLS strategies unavailable. "
        "Install with: pip install pybaselines"
    )


def _arpls_numpy(y: np.ndarray, lam: float = 1e5, p: float = 0.01,
                 max_iter: int = 50) -> np.ndarray:
    """
    Pure-NumPy ARPLS fallback (no pybaselines dependency).

    Baek et al. (2015) Analyst.
    """
    from scipy.sparse import diags, eye
    from scipy.sparse.linalg import spsolve

    n = len(y)
    D = diags([1, -2, 1], [0, 1, 2], shape=(n - 2, n)).toarray()
    D = np.dot(D.T, D)
    w = np.ones(n)
    for _ in range(max_iter):
        W = diags(w, 0)
        Z = W + lam * D
        z = np.linalg.solve(Z, w * y)
        residuals = y - z
        neg = residuals[residuals < 0]
        if len(neg) == 0:
            break
        m = np.mean(neg)
        s = np.std(neg)
        w_new = p * np.exp(-2 * (residuals - (2 * s - m)) / s)
        w_new = np.clip(w_new, 1e-9, 1.0)
        w_new[residuals >= 0] = p
        if np.allclose(w, w_new, atol=1e-6):
            break
        w = w_new
    return z


class ArplsStrategy(IBaselineStrategy):
    """
    ARPLS baseline strategy.

    Ignores anchor points — computes baseline directly from signal
    using iterative asymmetric reweighting.
    Works well for:
    - Broad, slowly varying baselines
    - Fluorescence backgrounds
    - UV-Vis baselines with drift
    """

    def __init__(self, lam: float = 1e5, p: float = 0.01, max_iter: int = 50):
        """
        Parameters
        ----------
        lam : float
            Smoothness penalty (larger = smoother baseline).
            Typical range: 1e3 – 1e8.
        p : float
            Asymmetry parameter (fraction of signal classified as background).
            Typical: 0.001 – 0.1.
        max_iter : int
            Maximum iterations.
        """
        self._lam = lam
        self._p = p
        self._max_iter = max_iter

    @property
    def method(self) -> BaselineMethod:
        return BaselineMethod.ARPLS

    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint],
        **kwargs
    ) -> np.ndarray:
        """Generate ARPLS baseline (anchors ignored)."""
        lam = kwargs.get('lam', self._lam)
        p = kwargs.get('p', self._p)

        if _PYBASELINES_AVAILABLE:
            try:
                fitter = PyBaseline(x_data=time)
                # pybaselines arpls does not expose `p` — uses lam only
                baseline, _ = fitter.arpls(signal, lam=lam,
                                           max_iter=self._max_iter)
                return baseline
            except Exception as e:
                logger.warning("pybaselines ARPLS failed (%s), falling back to NumPy.", e)

        return _arpls_numpy(signal, lam=lam, p=p, max_iter=self._max_iter)


class AirplsStrategy(IBaselineStrategy):
    """
    airPLS (Adaptive Iteratively Reweighted PLS) baseline strategy.

    Compared to ARPLS:
    - Faster convergence on sharp baselines
    - Better at preserving narrow peaks
    Zhang et al. (2010) Analyst.
    """

    def __init__(self, lam: float = 1e5, max_iter: int = 50):
        """
        Parameters
        ----------
        lam : float
            Smoothness penalty.
        max_iter : int
            Maximum iterations.
        """
        self._lam = lam
        self._max_iter = max_iter

    @property
    def method(self) -> BaselineMethod:
        return BaselineMethod.AIRPLS

    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint],
        **kwargs
    ) -> np.ndarray:
        """Generate airPLS baseline (anchors ignored)."""
        lam = kwargs.get('lam', self._lam)

        if _PYBASELINES_AVAILABLE:
            try:
                fitter = PyBaseline(x_data=time)
                baseline, _ = fitter.airpls(signal, lam=lam,
                                            max_iter=self._max_iter)
                return baseline
            except Exception as e:
                logger.warning("pybaselines airPLS failed (%s), using ARPLS fallback.", e)

        # Fallback: ARPLS NumPy with default p
        return _arpls_numpy(signal, lam=lam, max_iter=self._max_iter)
