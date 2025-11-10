"""
Peak Deconvolution Module for HPLC Analysis
===========================================

This module provides advanced peak deconvolution capabilities including:
- Automatic shoulder peak detection
- Multi-component Gaussian fitting
- Overlapping peak separation
- Peak asymmetry analysis

Author: PeakPicker Project
Date: 2025-11-10
"""

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, savgol_filter
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import warnings

from src.peak_models import (
    gaussian, multi_gaussian, estimate_peak_width,
    calculate_peak_asymmetry
)


@dataclass
class DeconvolvedPeak:
    """Represents a single deconvolved peak component."""
    retention_time: float  # Peak center (RT)
    amplitude: float  # Peak height
    sigma: float  # Peak width parameter
    area: float  # Integrated peak area
    area_percent: float  # Percentage of total area
    fit_quality: float  # R² value for this component
    is_shoulder: bool  # True if detected as shoulder peak
    asymmetry: float  # Asymmetry factor
    start_rt: float  # Peak start time
    end_rt: float  # Peak end time


@dataclass
class DeconvolutionResult:
    """Result of peak deconvolution analysis."""
    original_peak_rt: float  # Original peak center
    n_components: int  # Number of detected components
    components: List[DeconvolvedPeak]  # Individual peak components
    total_area: float  # Total integrated area
    fit_quality: float  # Overall R² value
    rmse: float  # Root mean square error
    method: str  # Deconvolution method used
    success: bool  # Whether deconvolution succeeded
    message: str  # Status or error message


class PeakDeconvolution:
    """
    Advanced peak deconvolution for HPLC chromatography.

    This class detects and separates overlapping peaks using Gaussian
    fitting and sophisticated shoulder peak detection algorithms.
    """

    def __init__(
        self,
        min_asymmetry: float = 1.2,
        min_shoulder_ratio: float = 0.1,
        max_components: int = 4,
        smooth_window: int = 5,
        fit_tolerance: float = 0.85
    ):
        """
        Initialize peak deconvolution analyzer.

        Parameters
        ----------
        min_asymmetry : float, default=1.2
            Minimum asymmetry factor to trigger deconvolution
            (1.0 = symmetric, >1.2 suggests overlapping peaks)
        min_shoulder_ratio : float, default=0.1
            Minimum height ratio for shoulder peak detection
            (shoulder must be at least 10% of main peak)
        max_components : int, default=4
            Maximum number of peak components to fit
        smooth_window : int, default=5
            Window size for derivative smoothing
        fit_tolerance : float, default=0.85
            Minimum R² value to accept fit (0-1)
        """
        self.min_asymmetry = min_asymmetry
        self.min_shoulder_ratio = min_shoulder_ratio
        self.max_components = max_components
        self.smooth_window = smooth_window
        self.fit_tolerance = fit_tolerance

    def needs_deconvolution(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        peak_idx: int
    ) -> Tuple[bool, str]:
        """
        Determine if a peak needs deconvolution.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        peak_idx : int
            Index of peak maximum

        Returns
        -------
        needs_decon : bool
            True if peak should be deconvolved
        reason : str
            Reason for decision
        """
        # Calculate asymmetry
        asymmetry = calculate_peak_asymmetry(rt, signal, peak_idx)

        # Check for high asymmetry
        if asymmetry > self.min_asymmetry:
            return True, f"High asymmetry: {asymmetry:.2f}"

        # Check for shoulder peaks using second derivative
        has_shoulder, shoulder_info = self._detect_shoulder(rt, signal, peak_idx)
        if has_shoulder:
            return True, f"Shoulder detected: {shoulder_info}"

        # Check for inflection points
        n_inflections = self._count_inflection_points(rt, signal, peak_idx)
        if n_inflections >= 3:
            return True, f"Multiple inflection points: {n_inflections}"

        return False, "Peak appears symmetric"

    def _detect_shoulder(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        peak_idx: int
    ) -> Tuple[bool, str]:
        """
        Detect shoulder peaks using second derivative analysis.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        peak_idx : int
            Index of main peak

        Returns
        -------
        has_shoulder : bool
            True if shoulder detected
        info : str
            Description of shoulder location
        """
        # Get peak region (extend both sides)
        left_idx = max(0, peak_idx - 50)
        right_idx = min(len(signal), peak_idx + 50)

        if right_idx - left_idx < 10:
            return False, ""

        # Extract region
        rt_region = rt[left_idx:right_idx]
        signal_region = signal[left_idx:right_idx]

        # Smooth and calculate second derivative
        if len(signal_region) < self.smooth_window:
            return False, ""

        try:
            # Use Savitzky-Golay filter for smooth derivatives
            second_deriv = savgol_filter(
                signal_region,
                window_length=self.smooth_window,
                polyorder=2,
                deriv=2
            )

            # Find local maxima in second derivative (concave up regions)
            # These indicate potential shoulders
            shoulder_peaks, properties = find_peaks(
                -second_deriv,  # Negative for concave up
                prominence=np.max(-second_deriv) * 0.1,
                distance=5
            )

            if len(shoulder_peaks) == 0:
                return False, ""

            # Check if shoulder is significant relative to main peak
            main_peak_height = signal_region[peak_idx - left_idx]

            for shoulder_idx in shoulder_peaks:
                shoulder_height = signal_region[shoulder_idx]
                ratio = shoulder_height / main_peak_height

                if ratio > self.min_shoulder_ratio and shoulder_idx != (peak_idx - left_idx):
                    position = "left" if shoulder_idx < (peak_idx - left_idx) else "right"
                    return True, f"{position} shoulder at RT={rt_region[shoulder_idx]:.2f} ({ratio*100:.1f}%)"

        except Exception as e:
            warnings.warn(f"Shoulder detection failed: {e}")
            return False, ""

        return False, ""

    def _count_inflection_points(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        peak_idx: int
    ) -> int:
        """
        Count inflection points in peak using second derivative.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        peak_idx : int
            Index of main peak

        Returns
        -------
        int
            Number of inflection points
        """
        # Get peak region
        left_idx = max(0, peak_idx - 30)
        right_idx = min(len(signal), peak_idx + 30)
        signal_region = signal[left_idx:right_idx]

        if len(signal_region) < self.smooth_window:
            return 0

        try:
            # Calculate second derivative
            second_deriv = savgol_filter(
                signal_region,
                window_length=self.smooth_window,
                polyorder=2,
                deriv=2
            )

            # Count zero crossings (inflection points)
            zero_crossings = np.where(np.diff(np.sign(second_deriv)))[0]
            return len(zero_crossings)

        except Exception:
            return 0

    def deconvolve_peak(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        peak_start_idx: int,
        peak_end_idx: int,
        initial_centers: Optional[List[float]] = None
    ) -> DeconvolutionResult:
        """
        Deconvolve a peak into multiple Gaussian components.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        peak_start_idx : int
            Index of peak start
        peak_end_idx : int
            Index of peak end
        initial_centers : List[float], optional
            Initial guesses for peak centers
            If None, automatically detected

        Returns
        -------
        DeconvolutionResult
            Result containing all deconvolved components
        """
        # Extract peak region
        rt_peak = rt[peak_start_idx:peak_end_idx + 1]
        signal_peak = signal[peak_start_idx:peak_end_idx + 1]

        if len(rt_peak) < 5:
            return self._create_failed_result(
                rt[peak_start_idx],
                "Peak region too small"
            )

        # Find main peak
        main_peak_idx = np.argmax(signal_peak)
        main_peak_rt = rt_peak[main_peak_idx]

        # Auto-detect peak centers if not provided
        if initial_centers is None:
            initial_centers = self._estimate_peak_centers(rt_peak, signal_peak)

        if len(initial_centers) == 0:
            return self._create_failed_result(
                main_peak_rt,
                "No peak centers detected"
            )

        # Try fitting with increasing number of components
        best_result = None
        best_r2 = -np.inf

        for n_peaks in range(1, min(len(initial_centers) + 1, self.max_components + 1)):
            result = self._fit_n_gaussians(
                rt_peak,
                signal_peak,
                initial_centers[:n_peaks],
                main_peak_rt
            )

            if result.success and result.fit_quality > best_r2:
                best_r2 = result.fit_quality
                best_result = result

            # Stop if fit is good enough
            if result.success and result.fit_quality > 0.95:
                break

        if best_result is None:
            return self._create_failed_result(
                main_peak_rt,
                "All fitting attempts failed"
            )

        return best_result

    def _estimate_peak_centers(
        self,
        rt: np.ndarray,
        signal: np.ndarray
    ) -> List[float]:
        """
        Automatically estimate positions of peak centers.

        Uses first derivative analysis and local maxima detection.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        List[float]
            Estimated retention times of peak centers
        """
        if len(signal) < self.smooth_window:
            # Just return the maximum
            return [rt[np.argmax(signal)]]

        # Find local maxima
        peaks, properties = find_peaks(
            signal,
            prominence=np.max(signal) * 0.05,
            distance=3
        )

        if len(peaks) == 0:
            # No peaks found, return global maximum
            return [rt[np.argmax(signal)]]

        # Sort by prominence
        prominences = properties['prominences']
        sorted_indices = np.argsort(prominences)[::-1]
        peaks = peaks[sorted_indices]

        # Return RT values of peaks
        centers = [rt[p] for p in peaks[:self.max_components]]

        return centers

    def _fit_n_gaussians(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        centers: List[float],
        original_rt: float
    ) -> DeconvolutionResult:
        """
        Fit N Gaussian peaks to data.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        centers : List[float]
            Initial guesses for peak centers
        original_rt : float
            Original peak center RT

        Returns
        -------
        DeconvolutionResult
            Fitting result
        """
        n_peaks = len(centers)

        # Prepare initial parameters: [amp1, center1, sigma1, amp2, center2, sigma2, ...]
        p0 = []
        bounds_lower = []
        bounds_upper = []

        for center in centers:
            # Find closest index
            center_idx = np.argmin(np.abs(rt - center))

            # Estimate amplitude
            amp = signal[center_idx]

            # Estimate sigma
            sigma = estimate_peak_width(rt, signal, center_idx)

            p0.extend([amp, center, sigma])

            # Bounds
            bounds_lower.extend([amp * 0.1, center - sigma * 3, sigma * 0.1])
            bounds_upper.extend([amp * 2.0, center + sigma * 3, sigma * 5.0])

        try:
            # Perform curve fitting
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='Covariance of the parameters could not be estimated')

                popt, pcov = curve_fit(
                    multi_gaussian,
                    rt,
                    signal,
                    p0=p0,
                    bounds=(bounds_lower, bounds_upper),
                    maxfev=10000
                )

            # Calculate fit quality
            fitted_signal = multi_gaussian(rt, *popt)
            r2 = self._calculate_r2(signal, fitted_signal)
            rmse = np.sqrt(np.mean((signal - fitted_signal) ** 2))

            # Check if fit is acceptable
            if r2 < self.fit_tolerance:
                return self._create_failed_result(
                    original_rt,
                    f"Poor fit quality: R²={r2:.3f}"
                )

            # Extract individual components
            components = []
            total_area = 0

            for i in range(n_peaks):
                amp = popt[i * 3]
                center = popt[i * 3 + 1]
                sigma = popt[i * 3 + 2]

                # Calculate area: integral of Gaussian = amplitude * sigma * sqrt(2*pi)
                area = amp * sigma * np.sqrt(2 * np.pi)
                total_area += area

                # Find peak boundaries (at 1% of peak height)
                threshold = amp * 0.01
                peak_signal = gaussian(rt, amp, center, sigma)
                above_threshold = peak_signal > threshold
                if np.any(above_threshold):
                    indices = np.where(above_threshold)[0]
                    start_rt = rt[indices[0]]
                    end_rt = rt[indices[-1]]
                else:
                    start_rt = center - 3 * sigma
                    end_rt = center + 3 * sigma

                # Determine if this is a shoulder peak
                # (not the tallest peak and significantly smaller)
                is_shoulder = amp < max([popt[j * 3] for j in range(n_peaks)]) * 0.8

                # Calculate asymmetry for this component
                center_idx = np.argmin(np.abs(rt - center))
                component_signal = gaussian(rt, amp, center, sigma)
                asymmetry = calculate_peak_asymmetry(rt, component_signal, center_idx)

                components.append(DeconvolvedPeak(
                    retention_time=center,
                    amplitude=amp,
                    sigma=sigma,
                    area=area,
                    area_percent=0,  # Will be calculated after total known
                    fit_quality=r2,
                    is_shoulder=is_shoulder,
                    asymmetry=asymmetry,
                    start_rt=start_rt,
                    end_rt=end_rt
                ))

            # Calculate area percentages
            for comp in components:
                comp.area_percent = (comp.area / total_area) * 100

            # Sort components by retention time
            components.sort(key=lambda x: x.retention_time)

            return DeconvolutionResult(
                original_peak_rt=original_rt,
                n_components=n_peaks,
                components=components,
                total_area=total_area,
                fit_quality=r2,
                rmse=rmse,
                method=f"{n_peaks}-Gaussian",
                success=True,
                message=f"Successfully fitted {n_peaks} Gaussian peaks (R²={r2:.3f})"
            )

        except Exception as e:
            return self._create_failed_result(
                original_rt,
                f"Fitting error: {str(e)}"
            )

    def _calculate_r2(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Calculate R² (coefficient of determination).

        Parameters
        ----------
        y_true : np.ndarray
            True values
        y_pred : np.ndarray
            Predicted values

        Returns
        -------
        float
            R² value (1.0 = perfect fit)
        """
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

        if ss_tot < 1e-10:
            return 0.0

        return 1 - (ss_res / ss_tot)

    def _create_failed_result(
        self,
        original_rt: float,
        message: str
    ) -> DeconvolutionResult:
        """Create a failed deconvolution result."""
        return DeconvolutionResult(
            original_peak_rt=original_rt,
            n_components=0,
            components=[],
            total_area=0,
            fit_quality=0,
            rmse=0,
            method="none",
            success=False,
            message=message
        )

    def analyze_peak(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        peak_start_idx: int,
        peak_end_idx: int,
        force_deconvolution: bool = False
    ) -> Optional[DeconvolutionResult]:
        """
        Analyze a peak and perform deconvolution if needed.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        peak_start_idx : int
            Index of peak start
        peak_end_idx : int
            Index of peak end
        force_deconvolution : bool, default=False
            If True, always attempt deconvolution
            If False, only deconvolve if peak appears asymmetric

        Returns
        -------
        DeconvolutionResult or None
            Result if deconvolution was performed, None otherwise
        """
        # Find peak maximum
        peak_signal = signal[peak_start_idx:peak_end_idx + 1]
        peak_idx = peak_start_idx + np.argmax(peak_signal)

        # Check if deconvolution is needed
        if not force_deconvolution:
            needs_decon, reason = self.needs_deconvolution(rt, signal, peak_idx)
            if not needs_decon:
                return None

        # Perform deconvolution
        result = self.deconvolve_peak(rt, signal, peak_start_idx, peak_end_idx)

        return result


if __name__ == "__main__":
    # Test deconvolution with synthetic data
    import matplotlib.pyplot as plt

    # Create test data: two overlapping Gaussian peaks
    rt = np.linspace(0, 10, 1000)
    peak1 = gaussian(rt, amplitude=100, center=4.5, sigma=0.3)
    peak2 = gaussian(rt, amplitude=70, center=5.2, sigma=0.35)
    signal = peak1 + peak2 + np.random.normal(0, 2, len(rt))

    # Initialize deconvolution
    decon = PeakDeconvolution(min_asymmetry=1.15)

    # Find peak boundaries
    peak_max_idx = np.argmax(signal)
    threshold = np.max(signal) * 0.01
    above_threshold = signal > threshold
    indices = np.where(above_threshold)[0]
    peak_start_idx = indices[0]
    peak_end_idx = indices[-1]

    # Perform deconvolution
    result = decon.analyze_peak(rt, signal, peak_start_idx, peak_end_idx, force_deconvolution=True)

    if result and result.success:
        print(f"Deconvolution successful!")
        print(f"Method: {result.method}")
        print(f"Fit quality (R²): {result.fit_quality:.4f}")
        print(f"RMSE: {result.rmse:.4f}")
        print(f"\nFound {result.n_components} components:")

        for i, comp in enumerate(result.components, 1):
            print(f"\nComponent {i}:")
            print(f"  RT: {comp.retention_time:.3f} min")
            print(f"  Amplitude: {comp.amplitude:.1f}")
            print(f"  Sigma: {comp.sigma:.4f}")
            print(f"  Area: {comp.area:.1f} ({comp.area_percent:.1f}%)")
            print(f"  Shoulder: {comp.is_shoulder}")
            print(f"  Asymmetry: {comp.asymmetry:.2f}")

        # Visualize results
        plt.figure(figsize=(12, 8))

        # Plot 1: Original vs Fitted
        plt.subplot(2, 1, 1)
        plt.plot(rt, signal, 'b-', linewidth=2, label='Original Signal', alpha=0.7)

        # Plot fitted signal
        fitted_signal = np.zeros_like(rt)
        for comp in result.components:
            fitted_signal += gaussian(rt, comp.amplitude, comp.retention_time, comp.sigma)
        plt.plot(rt, fitted_signal, 'r-', linewidth=2, label='Fitted Signal')

        plt.xlabel('Retention Time (min)')
        plt.ylabel('Intensity')
        plt.title(f'Peak Deconvolution: {result.method} (R²={result.fit_quality:.4f})')
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Plot 2: Individual components
        plt.subplot(2, 1, 2)
        plt.plot(rt, signal, 'gray', linewidth=1, label='Original', alpha=0.5)

        colors = ['red', 'green', 'blue', 'orange', 'purple']
        for i, comp in enumerate(result.components):
            component_signal = gaussian(rt, comp.amplitude, comp.retention_time, comp.sigma)
            label = f'Peak {i+1}: RT={comp.retention_time:.2f}, Area={comp.area_percent:.1f}%'
            if comp.is_shoulder:
                label += ' (shoulder)'
            plt.plot(rt, component_signal, color=colors[i % len(colors)],
                    linewidth=2, linestyle='--', label=label)

        plt.xlabel('Retention Time (min)')
        plt.ylabel('Intensity')
        plt.title('Individual Peak Components')
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('deconvolution_test.png', dpi=150)
        print("\nDeconvolution test plot saved to 'deconvolution_test.png'")
    else:
        print(f"Deconvolution failed: {result.message if result else 'No result'}")
