"""
Gaussian Curve Fitter
=====================

Fits Gaussian peaks for deconvolution.
Single Responsibility: Only fits curves.
"""

from typing import List, Tuple
import numpy as np

from ...interfaces import ICurveFitterStrategy, ICurveFitter
from ...domain import DeconvolvedPeak, DeconvolutionResult
from ...config import GaussianFitConfig, DeconvolutionConfig


def gaussian(x: np.ndarray, amplitude: float, center: float, sigma: float) -> np.ndarray:
    """Gaussian peak model."""
    return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))


def multi_gaussian(x: np.ndarray, *params) -> np.ndarray:
    """Multiple Gaussian peaks."""
    n_peaks = len(params) // 3
    result = np.zeros_like(x, dtype=float)

    for i in range(n_peaks):
        amplitude = params[i * 3]
        center = params[i * 3 + 1]
        sigma = params[i * 3 + 2]
        result += gaussian(x, amplitude, center, sigma)

    return result


class GaussianFitterStrategy(ICurveFitterStrategy):
    """
    Multi-Gaussian fitting strategy for deconvolution.
    """

    def __init__(
        self,
        curve_fitter: ICurveFitter,
        config: GaussianFitConfig = None
    ):
        """
        Initialize fitter.

        Parameters
        ----------
        curve_fitter : ICurveFitter
            Curve fitting implementation
        config : GaussianFitConfig, optional
            Configuration
        """
        self.curve_fitter = curve_fitter
        self.config = config or GaussianFitConfig()

    @property
    def name(self) -> str:
        """Return strategy name."""
        return "Multi-Gaussian"

    def fit(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        centers: List[float]
    ) -> Tuple[List[DeconvolvedPeak], float, float]:
        """
        Fit Gaussian peaks to signal.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        centers : List[float]
            Initial center estimates

        Returns
        -------
        Tuple[List[DeconvolvedPeak], float, float]
            (peaks, r2_score, rmse)
        """
        n_peaks = len(centers)

        # Prepare initial parameters
        p0 = []
        bounds_lower = []
        bounds_upper = []

        for center in centers:
            center_idx = np.argmin(np.abs(time - center))
            amp = float(signal[center_idx])
            sigma = self._estimate_sigma(time, signal, center_idx)

            p0.extend([amp, center, sigma])

            # Bounds
            bounds_lower.extend([
                amp * self.config.amplitude_lower_factor,
                center - sigma * self.config.center_tolerance_sigmas,
                sigma * self.config.sigma_lower_factor
            ])
            bounds_upper.extend([
                amp * self.config.amplitude_upper_factor,
                center + sigma * self.config.center_tolerance_sigmas,
                sigma * self.config.sigma_upper_factor
            ])

        try:
            popt, pcov = self.curve_fitter.fit(
                multi_gaussian,
                time,
                signal,
                p0=p0,
                bounds=(bounds_lower, bounds_upper),
                maxfev=10000
            )

            # Calculate fit quality
            fitted = multi_gaussian(time, *popt)
            r2 = self._calculate_r2(signal, fitted)
            rmse = float(np.sqrt(np.mean((signal - fitted) ** 2)))

            # Extract peaks
            peaks = []
            total_area = 0

            for i in range(n_peaks):
                amp = float(popt[i * 3])
                center = float(popt[i * 3 + 1])
                sigma = float(popt[i * 3 + 2])

                # Calculate area
                component = gaussian(time, amp, center, sigma)
                area = float(np.sum(component))
                total_area += area

                # Find boundaries
                threshold = amp * 0.01
                above = component > threshold
                if np.any(above):
                    indices = np.where(above)[0]
                    start_rt = float(time[indices[0]])
                    end_rt = float(time[indices[-1]])
                else:
                    start_rt = center - 3 * sigma
                    end_rt = center + 3 * sigma

                # Determine if shoulder
                max_amp = max([popt[j * 3] for j in range(n_peaks)])
                is_shoulder = amp < max_amp * 0.8

                peaks.append(DeconvolvedPeak(
                    retention_time=center,
                    amplitude=amp,
                    sigma=sigma,
                    area=area,
                    area_percent=0,  # Calculate after total known
                    fit_quality=r2,
                    is_shoulder=is_shoulder,
                    asymmetry=1.0,  # Gaussian is symmetric
                    start_rt=start_rt,
                    end_rt=end_rt
                ))

            # Calculate area percentages
            for peak in peaks:
                peak.area_percent = (peak.area / total_area * 100) if total_area > 0 else 0

            # Sort by retention time
            peaks.sort(key=lambda x: x.retention_time)

            return peaks, r2, rmse

        except Exception as e:
            return [], 0.0, float('inf')

    def _estimate_sigma(self, time: np.ndarray, signal: np.ndarray, center_idx: int) -> float:
        """Estimate sigma from FWHM."""
        if center_idx < 0 or center_idx >= len(signal):
            return 0.1

        peak_height = signal[center_idx]
        half_max = peak_height / 2

        # Find left half-max
        left_idx = center_idx
        while left_idx > 0 and signal[left_idx] > half_max:
            left_idx -= 1

        # Find right half-max
        right_idx = center_idx
        while right_idx < len(signal) - 1 and signal[right_idx] > half_max:
            right_idx += 1

        fwhm = time[right_idx] - time[left_idx]
        sigma = fwhm / 2.355

        return max(sigma, 0.01)

    def _calculate_r2(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate R² coefficient."""
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

        if ss_tot < 1e-10:
            return 0.0

        return float(1 - (ss_res / ss_tot))


class PeakDeconvolver:
    """
    High-level deconvolution orchestrator.

    Composes analyzer, estimator, and fitter.
    """

    def __init__(
        self,
        analyzer: 'ShoulderDeconvolutionAnalyzer',
        center_estimator: 'PeakCenterEstimator',
        fitter: GaussianFitterStrategy,
        config: DeconvolutionConfig = None
    ):
        """
        Initialize deconvolver.

        Parameters
        ----------
        analyzer : ShoulderDeconvolutionAnalyzer
            Analyzer for deconvolution need
        center_estimator : PeakCenterEstimator
            Center estimator
        fitter : GaussianFitterStrategy
            Curve fitter
        config : DeconvolutionConfig, optional
            Configuration
        """
        self.analyzer = analyzer
        self.center_estimator = center_estimator
        self.fitter = fitter
        self.config = config or DeconvolutionConfig()

    def deconvolve(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_start_idx: int,
        peak_end_idx: int,
        initial_centers: List[float] = None,
        force: bool = False
    ) -> DeconvolutionResult:
        """
        Deconvolve peak region.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_start_idx : int
            Peak region start
        peak_end_idx : int
            Peak region end
        initial_centers : List[float], optional
            Initial center estimates
        force : bool
            Force deconvolution even if not needed

        Returns
        -------
        DeconvolutionResult
            Deconvolution result
        """
        # Extract peak region
        rt_peak = time[peak_start_idx:peak_end_idx + 1]
        signal_peak = signal[peak_start_idx:peak_end_idx + 1]

        if len(rt_peak) < 5:
            return self._failed_result(time[peak_start_idx], "Peak region too small")

        # Find main peak
        main_idx = np.argmax(signal_peak)
        main_rt = float(rt_peak[main_idx])

        # Check if deconvolution needed
        if not force:
            global_idx = peak_start_idx + main_idx
            needs, reason = self.analyzer.needs_deconvolution(time, signal, global_idx)
            if not needs:
                return self._failed_result(main_rt, f"Not needed: {reason}")

        # Estimate centers if not provided
        if initial_centers is None:
            initial_centers = self.center_estimator.estimate_centers(
                rt_peak, signal_peak, self.config.max_components
            )

        if len(initial_centers) == 0:
            return self._failed_result(main_rt, "No centers detected")

        # Try fitting with increasing components
        best_peaks = []
        best_r2 = -np.inf
        best_rmse = float('inf')
        best_n = 0

        for n in range(1, min(len(initial_centers) + 1, self.config.max_components + 1)):
            peaks, r2, rmse = self.fitter.fit(
                rt_peak, signal_peak, initial_centers[:n]
            )

            if r2 > best_r2:
                best_r2 = r2
                best_rmse = rmse
                best_peaks = peaks
                best_n = n

            if r2 > 0.95:
                break

        if best_r2 < self.config.fit_tolerance:
            return self._failed_result(main_rt, f"Poor fit: R²={best_r2:.3f}")

        return DeconvolutionResult(
            original_peak_rt=main_rt,
            n_components=best_n,
            components=best_peaks,
            total_area=sum(p.area for p in best_peaks),
            fit_quality=best_r2,
            rmse=best_rmse,
            method=f"{best_n}-Gaussian",
            success=True,
            message=f"Successfully fitted {best_n} peaks (R²={best_r2:.3f})"
        )

    def _failed_result(self, rt: float, message: str) -> DeconvolutionResult:
        """Create failed result."""
        return DeconvolutionResult(
            original_peak_rt=rt,
            n_components=0,
            components=[],
            total_area=0,
            fit_quality=0,
            rmse=0,
            method="none",
            success=False,
            message=message
        )


# Import for type hints
from .analyzer import ShoulderDeconvolutionAnalyzer, PeakCenterEstimator
