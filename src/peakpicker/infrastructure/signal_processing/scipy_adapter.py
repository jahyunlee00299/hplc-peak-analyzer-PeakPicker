"""
SciPy Signal Processing Adapter
===============================

Concrete implementation of signal processing interfaces using SciPy.
Following Dependency Inversion Principle (DIP) - this adapter can be
swapped for testing or alternative implementations.
"""

from typing import Tuple, Callable, List
import numpy as np

from ...interfaces import ISignalProcessor, IInterpolator, ICurveFitter, IIntegrator


class ScipySignalProcessor(ISignalProcessor):
    """
    SciPy-based implementation of signal processing.

    Wraps scipy.signal functions with a clean interface.
    """

    def find_peaks(
        self,
        signal: np.ndarray,
        prominence: float = None,
        distance: int = None,
        height: float = None,
        width: float = None
    ) -> Tuple[np.ndarray, dict]:
        """Find peaks using scipy.signal.find_peaks."""
        from scipy.signal import find_peaks

        kwargs = {}
        if prominence is not None:
            kwargs['prominence'] = prominence
        if distance is not None:
            kwargs['distance'] = distance
        if height is not None:
            kwargs['height'] = height
        if width is not None:
            kwargs['width'] = width

        peaks, properties = find_peaks(signal, **kwargs)
        return peaks, properties

    def smooth(
        self,
        signal: np.ndarray,
        window_length: int,
        polyorder: int = 2
    ) -> np.ndarray:
        """Smooth signal using Savitzky-Golay filter."""
        from scipy.signal import savgol_filter

        # Ensure window length is odd
        if window_length % 2 == 0:
            window_length += 1

        # Ensure window length doesn't exceed signal length
        if window_length > len(signal):
            window_length = len(signal) if len(signal) % 2 == 1 else len(signal) - 1

        if window_length < 3:
            return signal.copy()

        # Ensure polyorder is less than window_length
        polyorder = min(polyorder, window_length - 1)

        return savgol_filter(signal, window_length, polyorder)

    def derivative(
        self,
        signal: np.ndarray,
        order: int = 1,
        window_length: int = 5
    ) -> np.ndarray:
        """Calculate derivative using Savitzky-Golay filter."""
        from scipy.signal import savgol_filter

        if window_length % 2 == 0:
            window_length += 1

        if window_length > len(signal):
            window_length = len(signal) if len(signal) % 2 == 1 else len(signal) - 1

        if window_length < order + 2:
            # Fallback to numpy diff
            result = signal.copy()
            for _ in range(order):
                result = np.diff(result, prepend=result[0])
            return result

        polyorder = min(order + 1, window_length - 1)

        return savgol_filter(signal, window_length, polyorder, deriv=order)


class ScipyInterpolator(IInterpolator):
    """
    SciPy-based implementation of interpolation.

    Wraps scipy.interpolate functions.
    """

    def linear(
        self,
        x: np.ndarray,
        y: np.ndarray,
        x_new: np.ndarray
    ) -> np.ndarray:
        """Linear interpolation using scipy.interpolate.interp1d."""
        from scipy.interpolate import interp1d

        f = interp1d(x, y, kind='linear', fill_value='extrapolate')
        return f(x_new)

    def spline(
        self,
        x: np.ndarray,
        y: np.ndarray,
        x_new: np.ndarray,
        smoothing: float = 0.0,
        weights: np.ndarray = None
    ) -> np.ndarray:
        """Spline interpolation using scipy.interpolate.UnivariateSpline."""
        from scipy.interpolate import UnivariateSpline, interp1d

        if len(x) < 4:
            # Fall back to linear for too few points
            return self.linear(x, y, x_new)

        try:
            # Determine spline order based on number of points
            k = min(3, len(x) - 1)

            spl = UnivariateSpline(x, y, w=weights, s=smoothing, k=k)
            return spl(x_new)
        except Exception:
            # Fallback to linear interpolation
            return self.linear(x, y, x_new)


class ScipyCurveFitter(ICurveFitter):
    """
    SciPy-based implementation of curve fitting.

    Wraps scipy.optimize.curve_fit.
    """

    def fit(
        self,
        func: Callable,
        x: np.ndarray,
        y: np.ndarray,
        p0: List[float],
        bounds: Tuple[List[float], List[float]] = None,
        maxfev: int = 5000
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Fit function using scipy.optimize.curve_fit."""
        from scipy.optimize import curve_fit
        import warnings

        kwargs = {
            'f': func,
            'xdata': x,
            'ydata': y,
            'p0': p0,
            'maxfev': maxfev,
        }

        if bounds is not None:
            kwargs['bounds'] = bounds

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Covariance of the parameters could not be estimated')
            popt, pcov = curve_fit(**kwargs)

        return popt, pcov


class ScipyIntegrator(IIntegrator):
    """
    SciPy-based implementation of numerical integration.

    Wraps scipy.integrate functions.
    """

    def trapezoid(
        self,
        y: np.ndarray,
        x: np.ndarray = None,
        dx: float = 1.0
    ) -> float:
        """Trapezoidal integration using scipy.integrate.trapezoid."""
        from scipy.integrate import trapezoid

        if x is not None:
            return float(trapezoid(y, x))
        return float(trapezoid(y, dx=dx))

    def simpson(
        self,
        y: np.ndarray,
        x: np.ndarray = None,
        dx: float = 1.0
    ) -> float:
        """Simpson's rule integration using scipy.integrate.simpson."""
        from scipy.integrate import simpson

        if x is not None:
            return float(simpson(y, x=x))
        return float(simpson(y, dx=dx))


# Factory function for easy creation
def create_scipy_processors():
    """Create a complete set of SciPy-based processors."""
    return {
        'signal': ScipySignalProcessor(),
        'interpolator': ScipyInterpolator(),
        'curve_fitter': ScipyCurveFitter(),
        'integrator': ScipyIntegrator(),
    }
