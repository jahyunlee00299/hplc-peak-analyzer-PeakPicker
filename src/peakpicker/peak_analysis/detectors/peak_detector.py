"""
Peak Detector
=============

Detects peaks in chromatogram signals.
Single Responsibility: Only detects peaks.
"""

from typing import List, Tuple
import numpy as np

from ...interfaces import IPeakDetector, IPeakBoundaryFinder, ISignalProcessor
from ...domain import Peak, PeakType
from ...config import PeakDetectionConfig


class ProminencePeakDetector(IPeakDetector):
    """
    Detects peaks using prominence-based detection.

    Uses scipy.signal.find_peaks with prominence filtering.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        boundary_finder: IPeakBoundaryFinder = None,
        config: PeakDetectionConfig = None
    ):
        """
        Initialize peak detector.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation
        boundary_finder : IPeakBoundaryFinder, optional
            Peak boundary finder
        config : PeakDetectionConfig, optional
            Detection configuration
        """
        self.signal_processor = signal_processor
        self.boundary_finder = boundary_finder
        self.config = config or PeakDetectionConfig()

    def detect(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        baseline: np.ndarray = None
    ) -> List[Peak]:
        """
        Detect peaks in signal.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        baseline : np.ndarray, optional
            Baseline for correction

        Returns
        -------
        List[Peak]
            Detected peaks
        """
        # Apply baseline correction if provided
        if baseline is not None:
            corrected = signal - baseline
        else:
            corrected = signal
            baseline = np.zeros_like(signal)

        # Clip negative values for detection
        corrected_positive = np.maximum(corrected, 0)

        # Estimate noise level
        noise_level = np.percentile(corrected_positive, self.config.noise_percentile)
        noise_level = max(noise_level, 1.0)  # Prevent zero noise

        # Calculate detection parameters
        signal_range = np.ptp(corrected_positive)
        min_prominence = signal_range * self.config.min_prominence_factor
        min_height = noise_level * self.config.height_multiplier

        # Find peaks
        peaks_idx, properties = self.signal_processor.find_peaks(
            corrected_positive,
            prominence=min_prominence,
            height=min_height,
            distance=self.config.min_distance,
            width=self.config.min_width
        )

        # Convert to Peak objects
        peaks = []
        for i, idx in enumerate(peaks_idx):
            # Find boundaries
            if self.boundary_finder is not None:
                start_idx, end_idx = self.boundary_finder.find_boundaries(
                    time, corrected_positive, idx, baseline
                )
            else:
                start_idx, end_idx = self._simple_boundaries(
                    corrected_positive, idx, baseline
                )

            # Calculate peak properties
            height = float(corrected_positive[idx])
            rt = float(time[idx])
            rt_start = float(time[start_idx])
            rt_end = float(time[end_idx])
            width = rt_end - rt_start

            # Calculate area (simple trapezoidal)
            peak_signal = corrected_positive[start_idx:end_idx + 1]
            peak_time = time[start_idx:end_idx + 1]
            area = float(np.trapz(peak_signal, peak_time))

            peaks.append(Peak(
                index=int(idx),
                rt=rt,
                index_start=int(start_idx),
                index_end=int(end_idx),
                rt_start=rt_start,
                rt_end=rt_end,
                height=height,
                area=area,
                width=width,
                peak_type=PeakType.MAIN
            ))

        # Calculate area percentages
        total_area = sum(p.area for p in peaks)
        if total_area > 0:
            for peak in peaks:
                peak.area_percent = (peak.area / total_area) * 100

        return peaks

    def _simple_boundaries(
        self,
        signal: np.ndarray,
        peak_idx: int,
        baseline: np.ndarray
    ) -> Tuple[int, int]:
        """Simple boundary finding based on threshold."""
        peak_height = signal[peak_idx]
        threshold = peak_height * self.config.boundary_threshold

        # Find left boundary
        left_idx = peak_idx
        while left_idx > 0 and signal[left_idx] > threshold:
            left_idx -= 1

        # Find right boundary
        right_idx = peak_idx
        while right_idx < len(signal) - 1 and signal[right_idx] > threshold:
            right_idx += 1

        return left_idx, right_idx


class SimplePeakBoundaryFinder(IPeakBoundaryFinder):
    """
    Simple peak boundary finder using threshold descent.
    """

    def __init__(self, config: PeakDetectionConfig = None):
        """
        Initialize boundary finder.

        Parameters
        ----------
        config : PeakDetectionConfig, optional
            Detection configuration
        """
        self.config = config or PeakDetectionConfig()

    def find_boundaries(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int,
        baseline: np.ndarray = None
    ) -> Tuple[int, int]:
        """
        Find peak boundaries using threshold descent.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_index : int
            Index of peak maximum
        baseline : np.ndarray, optional
            Baseline for reference

        Returns
        -------
        Tuple[int, int]
            Start and end indices
        """
        peak_height = signal[peak_index]
        if baseline is not None:
            base_height = baseline[peak_index]
        else:
            base_height = 0

        # Threshold at boundary_threshold of peak height above baseline
        threshold = base_height + (peak_height - base_height) * self.config.boundary_threshold

        # Find left boundary
        left_idx = peak_index
        while left_idx > 0 and signal[left_idx] > threshold:
            left_idx -= 1

        # Find right boundary
        right_idx = peak_index
        while right_idx < len(signal) - 1 and signal[right_idx] > threshold:
            right_idx += 1

        return left_idx, right_idx
