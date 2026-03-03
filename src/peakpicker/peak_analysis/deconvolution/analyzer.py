"""
Deconvolution Analyzer
======================

Analyzes peaks to determine if deconvolution is needed.
Single Responsibility: Only analyzes need for deconvolution.
"""

from typing import Tuple, List
import numpy as np

from ...interfaces import IDeconvolutionAnalyzer, ISignalProcessor
from ...config import DeconvolutionConfig


class ShoulderDeconvolutionAnalyzer(IDeconvolutionAnalyzer):
    """
    Analyzes peaks for shoulders and asymmetry.

    Uses second derivative analysis for shoulder detection.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        config: DeconvolutionConfig = None
    ):
        """
        Initialize analyzer.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation
        config : DeconvolutionConfig, optional
            Deconvolution configuration
        """
        self.signal_processor = signal_processor
        self.config = config or DeconvolutionConfig()

    def needs_deconvolution(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int
    ) -> Tuple[bool, str]:
        """
        Determine if peak needs deconvolution.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_index : int
            Index of peak maximum

        Returns
        -------
        Tuple[bool, str]
            (needs_deconvolution, reason)
        """
        # Check asymmetry
        asymmetry = self._calculate_asymmetry(time, signal, peak_index)
        if asymmetry > self.config.min_asymmetry_threshold:
            return True, f"High asymmetry: {asymmetry:.2f}"

        # Check for shoulder peaks
        has_shoulder, shoulder_info = self._detect_shoulder(time, signal, peak_index)
        if has_shoulder:
            return True, f"Shoulder detected: {shoulder_info}"

        # Check for inflection points
        n_inflections = self._count_inflection_points(signal, peak_index)
        if n_inflections >= self.config.min_inflection_points:
            return True, f"Multiple inflection points: {n_inflections}"

        return False, "Peak appears symmetric"

    def _calculate_asymmetry(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int
    ) -> float:
        """Calculate peak asymmetry factor."""
        if peak_index < 1 or peak_index >= len(signal) - 1:
            return 1.0

        peak_height = signal[peak_index]
        ten_percent = peak_height * 0.1

        # Find left point at 10% height
        left_idx = peak_index
        while left_idx > 0 and signal[left_idx] > ten_percent:
            left_idx -= 1

        # Find right point at 10% height
        right_idx = peak_index
        while right_idx < len(signal) - 1 and signal[right_idx] > ten_percent:
            right_idx += 1

        a = time[peak_index] - time[left_idx]  # Leading edge
        b = time[right_idx] - time[peak_index]  # Tailing edge

        if a < 1e-10:
            return 1.0

        return b / a

    def _detect_shoulder(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int
    ) -> Tuple[bool, str]:
        """Detect shoulder peaks using second derivative."""
        # Adaptive window: 25% of signal length, capped at 50 and floored at 10
        half_window = max(10, min(50, len(signal) // 4))
        left_idx = max(0, peak_index - half_window)
        right_idx = min(len(signal), peak_index + half_window)

        if right_idx - left_idx < 10:
            return False, ""

        signal_region = signal[left_idx:right_idx]
        time_region = time[left_idx:right_idx]

        if len(signal_region) < self.config.smooth_window:
            return False, ""

        try:
            # Calculate second derivative
            second_deriv = self.signal_processor.derivative(
                signal_region, order=2, window_length=self.config.smooth_window
            )

            # Find shoulders (concave up regions in second derivative)
            shoulder_peaks, _ = self.signal_processor.find_peaks(
                -second_deriv,
                prominence=np.max(-second_deriv) * self.config.shoulder_prominence,
                distance=5
            )

            if len(shoulder_peaks) == 0:
                return False, ""

            # Check if shoulder is significant
            main_peak_height = signal_region[peak_index - left_idx]

            for shoulder_idx in shoulder_peaks:
                shoulder_height = signal_region[shoulder_idx]
                ratio = shoulder_height / main_peak_height

                if ratio > self.config.min_shoulder_ratio and shoulder_idx != (peak_index - left_idx):
                    position = "left" if shoulder_idx < (peak_index - left_idx) else "right"
                    return True, f"{position} shoulder at RT={time_region[shoulder_idx]:.2f} ({ratio*100:.1f}%)"

        except Exception:
            pass

        return False, ""

    def _count_inflection_points(
        self,
        signal: np.ndarray,
        peak_index: int
    ) -> int:
        """Count inflection points using second derivative zero crossings."""
        # Adaptive window: 20% of signal length, capped at 30 and floored at 10
        half_window = max(10, min(30, len(signal) // 5))
        left_idx = max(0, peak_index - half_window)
        right_idx = min(len(signal), peak_index + half_window)
        signal_region = signal[left_idx:right_idx]

        if len(signal_region) < self.config.smooth_window:
            return 0

        try:
            second_deriv = self.signal_processor.derivative(
                signal_region, order=2, window_length=self.config.smooth_window
            )

            # Count zero crossings
            zero_crossings = np.where(np.diff(np.sign(second_deriv)))[0]
            return len(zero_crossings)

        except Exception:
            return 0


class PeakCenterEstimator:
    """
    Estimates peak center positions for deconvolution.

    Single Responsibility: Only estimates centers.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        config: DeconvolutionConfig = None
    ):
        """
        Initialize estimator.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation
        config : DeconvolutionConfig, optional
            Configuration
        """
        self.signal_processor = signal_processor
        self.config = config or DeconvolutionConfig()

    def estimate_centers(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        max_components: int = None
    ) -> List[float]:
        """
        Estimate peak center positions.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        max_components : int, optional
            Maximum number of components

        Returns
        -------
        List[float]
            Estimated retention times of centers
        """
        if max_components is None:
            max_components = self.config.max_components

        if len(signal) < self.config.smooth_window:
            return [time[np.argmax(signal)]]

        # Find local maxima
        peaks, properties = self.signal_processor.find_peaks(
            signal,
            prominence=np.max(signal) * 0.05,
            distance=3
        )

        if len(peaks) == 0:
            return [time[np.argmax(signal)]]

        # Sort by prominence
        if 'prominences' in properties:
            prominences = properties['prominences']
            sorted_indices = np.argsort(prominences)[::-1]
            peaks = peaks[sorted_indices]

        # Return RT values
        centers = [float(time[p]) for p in peaks[:max_components]]
        return centers
