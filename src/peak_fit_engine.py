"""
Fast bounded least-squares engine for sums of Gaussian / EMG peaks
==================================================================

Drop-in replacement for ``scipy.optimize.curve_fit(multi_gaussian | multi_emg, ...)`` as used by
``peak_deconvolution``.  It calls the same ``least_squares`` (trf, '2-point' finite differences, same
bounds and ``max_nfev``) on the same residual function, so the optimiser takes the same steps.  The
difference is how the residual is evaluated:

* The 2-point Jacobian perturbs ONE parameter at a time.  Only the component that owns that parameter
  changes, so the other components' contributions are reused from the base point: the model sum is
  rebuilt from cached partial sums in the original summation order (components added 0, 1, 2, ...).
  Floating-point results are therefore bit-identical to evaluating the full model.
* The EMG component evaluates ``erfcx`` only where ``b >= 0`` and ``erfc`` only where ``b < 0``
  instead of both branches over the whole array (element-wise results are unchanged).
* The covariance matrix that ``curve_fit`` computes and the caller discards is not computed.

``curve_fit`` raises ``RuntimeError`` when ``least_squares`` does not report success (including the
``max_nfev`` cap); ``fit_peak_sum`` raises the same exception, so callers keep their failure paths.
"""

from typing import List, Sequence

import numpy as np
from scipy.optimize import least_squares
from scipy.special import erfc, erfcx

from src.peak_models import exponentially_modified_gaussian as _emg_reference

_SQRT2 = np.sqrt(2.0)
_SQRT2PI = np.sqrt(2 * np.pi)


def gaussian_component(x, amplitude, center, sigma):
    """One Gaussian peak; same expression as ``peak_models.gaussian``."""
    return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))


def emg_component(x, amplitude, center, sigma, tau):
    """One EMG peak; element-wise identical to ``peak_models.exponentially_modified_gaussian``."""
    if not tau >= 1e-10:  # tau ~ 0 (pure Gaussian), negative (mirror) or NaN: use the reference model
        return _emg_reference(x, amplitude, center, sigma, tau)
    u = x - center
    b = (sigma / tau - u / sigma) / _SQRT2
    prefactor = amplitude * sigma * _SQRT2PI / (2 * tau)
    nonneg = b >= 0
    with np.errstate(over='ignore', invalid='ignore'):
        if nonneg.all():
            out = np.exp(-u ** 2 / (2 * sigma ** 2)) * erfcx(b)
        elif not nonneg.any():
            out = np.exp(sigma ** 2 / (2 * tau ** 2) - u / tau) * erfc(b)
        else:
            out = np.empty_like(u)
            uf, bf = u[nonneg], b[nonneg]
            out[nonneg] = np.exp(-uf ** 2 / (2 * sigma ** 2)) * erfcx(bf)
            neg = ~nonneg
            ut, bt = u[neg], b[neg]
            out[neg] = np.exp(sigma ** 2 / (2 * tau ** 2) - ut / tau) * erfc(bt)
    return prefactor * out


_COMPONENTS = {'gaussian': (3, gaussian_component), 'emg': (4, emg_component)}


class _Base:
    __slots__ = ('params', 'parts', 'prefix', 'total')

    def __init__(self, params, parts, prefix, total):
        self.params, self.parts, self.prefix, self.total = params, parts, prefix, total


class IncrementalSum:
    """Sum of peak components that re-evaluates only the component whose parameters changed.

    Every returned array equals what ``result = zeros; for comp: result += comp(...)`` gives.
    """

    def __init__(self, x: np.ndarray, kind: str, keep: int = 4):
        self.x = x
        self.width, self.component = _COMPONENTS[kind]
        self.keep = keep
        self.bases: List[_Base] = []

    def _full(self, params: np.ndarray) -> np.ndarray:
        w, comp, x = self.width, self.component, self.x
        total = np.zeros_like(x, dtype=float)
        parts, prefix = [], []
        for i in range(len(params) // w):
            part = comp(x, *params[i * w:(i + 1) * w])
            parts.append(part)
            prefix.append(total.copy())
            total += part
        self.bases.insert(0, _Base(params.copy(), parts, prefix, total))
        del self.bases[self.keep:]
        return total

    def __call__(self, params: np.ndarray) -> np.ndarray:
        w = self.width
        for base in self.bases:
            changed = np.flatnonzero(params != base.params)
            if changed.size == 0:
                return base.total.copy()
            block = changed[0] // w
            if changed[-1] // w != block:
                continue
            part = self.component(self.x, *params[block * w:(block + 1) * w])
            total = base.prefix[block] + part  # prefix[block] is zeros for block 0: 0.0 + part, as in the original
            for later in base.parts[block + 1:]:
                total += later
            return total
        return self._full(params)


def fit_peak_sum(x, y, p0: Sequence[float], lower: Sequence[float], upper: Sequence[float],
                 kind: str, max_nfev: int) -> np.ndarray:
    """Bounded fit of a sum of ``kind`` ('gaussian' | 'emg') peaks; returns ``popt``.

    Equivalent to ``curve_fit(multi_<kind>, x, y, p0=p0, bounds=(lower, upper), maxfev=max_nfev)[0]``
    including its exceptions (``ValueError`` for infeasible p0 / non-finite data, ``RuntimeError``
    when the optimiser does not converge within ``max_nfev``).
    """
    x = np.asarray_chkfinite(x, float)
    y = np.asarray_chkfinite(y, float)
    if y.size == 0:
        raise ValueError("`ydata` must not be empty!")
    model = IncrementalSum(x, kind)

    def residual(params):
        return model(params) - y

    res = least_squares(residual, np.atleast_1d(p0), jac='2-point', bounds=(lower, upper),
                        method='trf', max_nfev=max_nfev)
    if not res.success:
        raise RuntimeError("Optimal parameters not found: " + res.message)
    return res.x
