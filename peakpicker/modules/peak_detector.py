"""
Peak Detection and Integration for HPLC Chromatograms
Enhanced version for PeakPicker GUI
"""

import numpy as np
from scipy import signal
from scipy.integrate import trapezoid
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class Peak:
    """Data class to store peak information"""
    rt: float  # Retention time at peak maximum
    rt_start: float  # Start of peak
    rt_end: float  # End of peak
    height: float  # Peak height
    area: float  # Integrated peak area
    width: float  # Peak width at half height
    index: int  # Index in the data array
    index_start: int  # Start index
    index_end: int  # End index
    percent_area: float = 0.0  # Percentage of total area

    def to_dict(self) -> Dict:
        """Convert peak to dictionary"""
        return asdict(self)


class PeakDetector:
    """Detect and integrate peaks in chromatogram data"""

    def __init__(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        prominence: Optional[float] = None,
        min_height: Optional[float] = None,
        min_width: float = 0.01,  # minutes
        rel_height: float = 0.5,  # for width calculation (0.5 = FWHM)
        auto_threshold: bool = True,
    ):
        """
        Initialize peak detector

        Args:
            time: Time array (minutes)
            intensity: Intensity/signal array
            prominence: Minimum peak prominence (auto if None)
            min_height: Minimum peak height (auto if None)
            min_width: Minimum peak width in minutes
            rel_height: Relative height for width calculation (0.5 = FWHM)
            auto_threshold: Auto-calculate thresholds based on data
        """
        self.time = time
        self.intensity = intensity
        self.min_width = min_width
        self.rel_height = rel_height
        self.peaks: List[Peak] = []

        # Calculate automatic thresholds if requested
        if auto_threshold:
            intensity_range = np.ptp(self.intensity)
            intensity_mean = np.mean(self.intensity)
            intensity_std = np.std(self.intensity)

            if prominence is None:
                # Use 5% of intensity range or 2*std, whichever is larger
                self.prominence = max(intensity_range * 0.05, 2 * intensity_std)
            else:
                self.prominence = prominence

            if min_height is None:
                # Use mean + 1*std as minimum height
                self.min_height = intensity_mean + intensity_std
            else:
                self.min_height = min_height
        else:
            self.prominence = prominence if prominence is not None else 0
            self.min_height = min_height if min_height is not None else 0

    def detect_peaks(self) -> List[Peak]:
        """
        Detect peaks in the chromatogram

        Returns:
            List of Peak objects
        """
        # Convert min_width from time to samples
        time_per_sample = np.mean(np.diff(self.time))
        min_width_samples = max(1, int(self.min_width / time_per_sample))

        # Smooth the data slightly to reduce noise
        window_size = max(3, min_width_samples // 2)
        if window_size % 2 == 0:
            window_size += 1

        # Only smooth if we have enough points
        if len(self.intensity) >= window_size:
            smoothed = signal.savgol_filter(self.intensity, window_size, 2)
        else:
            smoothed = self.intensity.copy()

        # Find peaks using scipy
        peak_indices, properties = signal.find_peaks(
            smoothed,
            prominence=self.prominence,
            height=self.min_height,
            width=min_width_samples,
            rel_height=self.rel_height,
        )

        # Extract peak boundaries and calculate areas
        self.peaks = []
        for i, peak_idx in enumerate(peak_indices):
            # Get peak boundaries
            left_base = int(properties['left_bases'][i])
            right_base = int(properties['right_bases'][i])

            # Calculate peak area using trapezoidal integration
            peak_time = self.time[left_base:right_base + 1]
            peak_intensity = self.intensity[left_base:right_base + 1]

            # Baseline correction (linear)
            baseline = np.linspace(
                self.intensity[left_base],
                self.intensity[right_base],
                len(peak_intensity)
            )
            corrected_intensity = peak_intensity - baseline

            # Integrate
            area = trapezoid(corrected_intensity, peak_time)

            # Create Peak object
            peak = Peak(
                rt=self.time[peak_idx],
                rt_start=self.time[left_base],
                rt_end=self.time[right_base],
                height=self.intensity[peak_idx] - baseline[peak_idx - left_base],
                area=max(0.0, area),  # Ensure non-negative
                width=properties['widths'][i] * time_per_sample,
                index=peak_idx,
                index_start=left_base,
                index_end=right_base,
            )
            self.peaks.append(peak)

        # Calculate percent areas
        total_area = sum(p.area for p in self.peaks)
        if total_area > 0:
            for peak in self.peaks:
                peak.percent_area = (peak.area / total_area) * 100.0

        return self.peaks

    def get_peak_at_rt(
        self,
        target_rt: float,
        tolerance: float = 0.1
    ) -> Optional[Peak]:
        """
        Get peak closest to target retention time

        Args:
            target_rt: Target retention time
            tolerance: Maximum allowed deviation in minutes

        Returns:
            Peak object or None if no peak found within tolerance
        """
        if not self.peaks:
            self.detect_peaks()

        closest_peak = None
        min_distance = float('inf')

        for peak in self.peaks:
            distance = abs(peak.rt - target_rt)
            if distance < min_distance and distance <= tolerance:
                min_distance = distance
                closest_peak = peak

        return closest_peak

    def get_peaks_in_range(
        self,
        rt_start: float,
        rt_end: float
    ) -> List[Peak]:
        """
        Get all peaks within a retention time range

        Args:
            rt_start: Start of retention time range
            rt_end: End of retention time range

        Returns:
            List of Peak objects
        """
        if not self.peaks:
            self.detect_peaks()

        return [
            peak for peak in self.peaks
            if rt_start <= peak.rt <= rt_end
        ]

    def integrate_range(
        self,
        rt_start: float,
        rt_end: float,
        baseline_correct: bool = True
    ) -> float:
        """
        Integrate a specific retention time range

        Args:
            rt_start: Start of integration range
            rt_end: End of integration range
            baseline_correct: Whether to apply baseline correction

        Returns:
            Integrated area
        """
        # Find indices corresponding to retention time range
        start_idx = np.searchsorted(self.time, rt_start)
        end_idx = np.searchsorted(self.time, rt_end)

        if start_idx >= end_idx:
            return 0.0

        # Extract data
        time_range = self.time[start_idx:end_idx + 1]
        intensity_range = self.intensity[start_idx:end_idx + 1]

        if baseline_correct:
            # Linear baseline correction
            baseline = np.linspace(
                intensity_range[0],
                intensity_range[-1],
                len(intensity_range)
            )
            intensity_range = intensity_range - baseline

        # Integrate
        area = trapezoid(intensity_range, time_range)

        return max(0.0, area)  # Ensure non-negative

    def get_summary(self) -> Dict:
        """
        Get summary statistics of detected peaks

        Returns:
            Dictionary with summary statistics
        """
        if not self.peaks:
            self.detect_peaks()

        if not self.peaks:
            return {
                'num_peaks': 0,
                'total_area': 0.0,
                'avg_peak_width': 0.0,
                'avg_peak_height': 0.0,
                'retention_times': [],
                'areas': [],
            }

        return {
            'num_peaks': len(self.peaks),
            'total_area': sum(p.area for p in self.peaks),
            'avg_peak_width': float(np.mean([p.width for p in self.peaks])),
            'avg_peak_height': float(np.mean([p.height for p in self.peaks])),
            'retention_times': [float(p.rt) for p in self.peaks],
            'areas': [float(p.area) for p in self.peaks],
            'heights': [float(p.height) for p in self.peaks],
        }

    def get_baseline(self) -> np.ndarray:
        """
        Get baseline for the entire chromatogram

        Returns:
            Baseline array
        """
        # Simple linear baseline from start to end
        baseline = np.linspace(
            self.intensity[0],
            self.intensity[-1],
            len(self.intensity)
        )
        return baseline


def detect_and_integrate_peaks(
    time: np.ndarray,
    intensity: np.ndarray,
    **kwargs
) -> Tuple[List[Peak], Dict]:
    """
    Convenience function to detect and integrate peaks

    Args:
        time: Time array
        intensity: Intensity array
        **kwargs: Additional arguments passed to PeakDetector

    Returns:
        Tuple of (peaks_list, summary_dict)
    """
    detector = PeakDetector(time, intensity, **kwargs)
    peaks = detector.detect_peaks()
    summary = detector.get_summary()
    return peaks, summary
