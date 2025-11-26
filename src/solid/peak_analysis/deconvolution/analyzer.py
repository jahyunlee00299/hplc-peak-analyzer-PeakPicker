"""
Deconvolution Analyzer
======================

Analyzes peaks to determine if deconvolution is needed.
Single Responsibility: Only analyzes need for deconvolution.

SOLID Principles Applied:
- SRP: Each class has single responsibility
- DIP: Depends on interfaces, not concrete implementations
- LSP: All implementations can substitute their interfaces
"""

from __future__ import annotations
from typing import Tuple, List, TYPE_CHECKING
import numpy as np

from ...interfaces import (
    IDeconvolutionAnalyzer,
    ISignalProcessor,
    IPeakCenterEstimator,
    IAsymmetryCalculator,
)
from ...config import DeconvolutionConfig

if TYPE_CHECKING:
    pass  # For future type hints if needed


class AsymmetryCalculator(IAsymmetryCalculator):
    """
    Calculates peak asymmetry factor.

    Single Responsibility: Only calculates asymmetry.
    Implements IAsymmetryCalculator interface (LSP).
    """

    def __init__(self, measurement_height: float = 0.1):
        """
        Initialize calculator.

        Parameters
        ----------
        measurement_height : float
            Height fraction for measurement (default 10%)
        """
        self.measurement_height = measurement_height

    def calculate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int
    ) -> float:
        """
        Calculate peak asymmetry factor.

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
        float
            Asymmetry factor (1.0 = symmetric, >1 = tailing, <1 = fronting)
        """
        if peak_index < 1 or peak_index >= len(signal) - 1:
            return 1.0

        peak_height = signal[peak_index]
        threshold = peak_height * self.measurement_height

        # Find left point at threshold height
        left_idx = peak_index
        while left_idx > 0 and signal[left_idx] > threshold:
            left_idx -= 1

        # Find right point at threshold height
        right_idx = peak_index
        while right_idx < len(signal) - 1 and signal[right_idx] > threshold:
            right_idx += 1

        a = time[peak_index] - time[left_idx]  # Leading edge
        b = time[right_idx] - time[peak_index]  # Tailing edge

        if a < 1e-10:
            return 1.0

        return b / a


class ShoulderDetector:
    """
    Detects shoulder peaks using second derivative analysis.

    Single Responsibility: Only detects shoulders.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        smooth_window: int = 5,
        shoulder_prominence: float = 0.1,
        min_shoulder_ratio: float = 0.1
    ):
        """
        Initialize detector.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation (DIP)
        smooth_window : int
            Window size for derivative smoothing
        shoulder_prominence : float
            Prominence threshold for shoulder detection
        min_shoulder_ratio : float
            Minimum height ratio for shoulder
        """
        self.signal_processor = signal_processor
        self.smooth_window = smooth_window
        self.shoulder_prominence = shoulder_prominence
        self.min_shoulder_ratio = min_shoulder_ratio

    def detect(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int
    ) -> Tuple[bool, str]:
        """
        Detect shoulder peaks using second derivative.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_index : int
            Index of main peak

        Returns
        -------
        Tuple[bool, str]
            (has_shoulder, description)
        """
        # Get peak region
        left_idx = max(0, peak_index - 50)
        right_idx = min(len(signal), peak_index + 50)

        if right_idx - left_idx < 10:
            return False, ""

        signal_region = signal[left_idx:right_idx]
        time_region = time[left_idx:right_idx]

        if len(signal_region) < self.smooth_window:
            return False, ""

        try:
            # Calculate second derivative
            second_deriv = self.signal_processor.derivative(
                signal_region, order=2, window_length=self.smooth_window
            )

            # Find shoulders (concave up regions in second derivative)
            shoulder_peaks, _ = self.signal_processor.find_peaks(
                -second_deriv,
                prominence=np.max(-second_deriv) * self.shoulder_prominence,
                distance=5
            )

            if len(shoulder_peaks) == 0:
                return False, ""

            # Check if shoulder is significant
            main_peak_height = signal_region[peak_index - left_idx]

            for shoulder_idx in shoulder_peaks:
                shoulder_height = signal_region[shoulder_idx]
                ratio = shoulder_height / main_peak_height

                if ratio > self.min_shoulder_ratio and shoulder_idx != (peak_index - left_idx):
                    position = "left" if shoulder_idx < (peak_index - left_idx) else "right"
                    return True, f"{position} shoulder at RT={time_region[shoulder_idx]:.2f} ({ratio*100:.1f}%)"

        except Exception:
            # Shoulder detection is optional - gracefully handle failures
            pass

        return False, ""


class InflectionPointCounter:
    """
    Counts inflection points using second derivative zero crossings.

    Single Responsibility: Only counts inflection points.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        smooth_window: int = 5
    ):
        """
        Initialize counter.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation (DIP)
        smooth_window : int
            Window size for derivative smoothing
        """
        self.signal_processor = signal_processor
        self.smooth_window = smooth_window

    def count(
        self,
        signal: np.ndarray,
        peak_index: int
    ) -> int:
        """
        Count inflection points near peak.

        Parameters
        ----------
        signal : np.ndarray
            Signal intensity array
        peak_index : int
            Index of peak maximum

        Returns
        -------
        int
            Number of inflection points
        """
        left_idx = max(0, peak_index - 30)
        right_idx = min(len(signal), peak_index + 30)
        signal_region = signal[left_idx:right_idx]

        if len(signal_region) < self.smooth_window:
            return 0

        try:
            second_deriv = self.signal_processor.derivative(
                signal_region, order=2, window_length=self.smooth_window
            )

            # Count zero crossings
            zero_crossings = np.where(np.diff(np.sign(second_deriv)))[0]
            return len(zero_crossings)

        except Exception:
            return 0


class ShoulderDeconvolutionAnalyzer(IDeconvolutionAnalyzer):
    """
    Analyzes peaks for shoulders and asymmetry.

    Uses composition of specialized analyzers (SRP).
    Depends on interfaces, not implementations (DIP).
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        asymmetry_calculator: IAsymmetryCalculator = None,
        config: DeconvolutionConfig = None
    ):
        """
        Initialize analyzer.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation (DIP)
        asymmetry_calculator : IAsymmetryCalculator, optional
            Asymmetry calculation implementation (DIP)
        config : DeconvolutionConfig, optional
            Deconvolution configuration
        """
        self.signal_processor = signal_processor
        self.config = config or DeconvolutionConfig()

        # Use injected calculator or create default (DIP with default)
        self.asymmetry_calculator = asymmetry_calculator or AsymmetryCalculator()

        # Compose specialized detectors (SRP)
        self.shoulder_detector = ShoulderDetector(
            signal_processor,
            smooth_window=self.config.smooth_window,
            shoulder_prominence=self.config.shoulder_prominence,
            min_shoulder_ratio=self.config.min_shoulder_ratio
        )
        self.inflection_counter = InflectionPointCounter(
            signal_processor,
            smooth_window=self.config.smooth_window
        )

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
        asymmetry = self.asymmetry_calculator.calculate(time, signal, peak_index)
        if asymmetry > self.config.min_asymmetry_threshold:
            return True, f"High asymmetry: {asymmetry:.2f}"

        # Check for shoulder peaks
        has_shoulder, shoulder_info = self.shoulder_detector.detect(time, signal, peak_index)
        if has_shoulder:
            return True, f"Shoulder detected: {shoulder_info}"

        # Check for inflection points
        n_inflections = self.inflection_counter.count(signal, peak_index)
        if n_inflections >= self.config.min_inflection_points:
            return True, f"Multiple inflection points: {n_inflections}"

        return False, "Peak appears symmetric"


class PeakCenterEstimator(IPeakCenterEstimator):
    """
    Estimates peak center positions for deconvolution.

    Single Responsibility: Only estimates centers.
    Implements IPeakCenterEstimator interface (LSP).
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
            Signal processing implementation (DIP)
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
            return [float(time[np.argmax(signal)])]

        # Find local maxima
        peaks, properties = self.signal_processor.find_peaks(
            signal,
            prominence=np.max(signal) * 0.05,
            distance=3
        )

        if len(peaks) == 0:
            return [float(time[np.argmax(signal)])]

        # Sort by prominence
        if 'prominences' in properties:
            prominences = properties['prominences']
            sorted_indices = np.argsort(prominences)[::-1]
            peaks = peaks[sorted_indices]

        # Return RT values
        centers = [float(time[p]) for p in peaks[:max_components]]
        return centers
