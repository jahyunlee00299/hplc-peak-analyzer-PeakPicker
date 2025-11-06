"""
Baseline correction and peak handling module
"""

import numpy as np
from scipy import signal, interpolate
from typing import List, Tuple, Optional
from .peak_detector import Peak


class BaselineHandler:
    """Handle baseline correction and manual adjustments"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        """
        Initialize baseline handler

        Args:
            time: Time array
            intensity: Intensity array
        """
        self.time = time
        self.intensity = intensity
        self.baseline = None
        self.corrected_intensity = None

    def calculate_linear_baseline(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> np.ndarray:
        """
        Calculate linear baseline

        Args:
            start_time: Start time for baseline (uses first point if None)
            end_time: End time for baseline (uses last point if None)

        Returns:
            Baseline array
        """
        if start_time is None:
            start_idx = 0
        else:
            start_idx = np.searchsorted(self.time, start_time)

        if end_time is None:
            end_idx = len(self.time) - 1
        else:
            end_idx = np.searchsorted(self.time, end_time)

        # Linear interpolation
        baseline = np.linspace(
            self.intensity[start_idx],
            self.intensity[end_idx],
            len(self.intensity)
        )

        self.baseline = baseline
        return baseline

    def calculate_polynomial_baseline(self, degree: int = 3) -> np.ndarray:
        """
        Calculate polynomial baseline

        Args:
            degree: Polynomial degree

        Returns:
            Baseline array
        """
        # Fit polynomial
        coeffs = np.polyfit(self.time, self.intensity, degree)
        baseline = np.polyval(coeffs, self.time)

        self.baseline = baseline
        return baseline

    def calculate_als_baseline(
        self,
        lam: float = 1e6,
        p: float = 0.01,
        niter: int = 10
    ) -> np.ndarray:
        """
        Calculate baseline using Asymmetric Least Squares (ALS)

        Args:
            lam: Smoothness parameter
            p: Asymmetry parameter
            niter: Number of iterations

        Returns:
            Baseline array
        """
        L = len(self.intensity)
        D = np.diff(np.eye(L), 2, axis=0)  # Second derivative matrix
        w = np.ones(L)

        for i in range(niter):
            W = np.diag(w)
            Z = W + lam * (D.T @ D)
            z = np.linalg.solve(Z, w * self.intensity)
            w = p * (self.intensity > z) + (1 - p) * (self.intensity < z)

        self.baseline = z
        return z

    def apply_baseline_correction(self, baseline: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Apply baseline correction

        Args:
            baseline: Baseline to subtract (uses stored baseline if None)

        Returns:
            Corrected intensity array
        """
        if baseline is None:
            if self.baseline is None:
                raise ValueError("No baseline available. Calculate baseline first.")
            baseline = self.baseline

        self.corrected_intensity = self.intensity - baseline
        return self.corrected_intensity

    def manual_baseline(
        self,
        anchor_points: List[Tuple[float, float]]
    ) -> np.ndarray:
        """
        Create baseline from manual anchor points

        Args:
            anchor_points: List of (time, intensity) tuples

        Returns:
            Baseline array
        """
        if len(anchor_points) < 2:
            raise ValueError("Need at least 2 anchor points")

        # Sort anchor points by time
        anchor_points = sorted(anchor_points, key=lambda x: x[0])

        # Extract times and intensities
        anchor_times = [p[0] for p in anchor_points]
        anchor_intensities = [p[1] for p in anchor_points]

        # Interpolate
        f = interpolate.interp1d(
            anchor_times,
            anchor_intensities,
            kind='linear',
            fill_value='extrapolate'
        )

        baseline = f(self.time)
        self.baseline = baseline
        return baseline


class PeakSplitter:
    """Split overlapping peaks"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        """
        Initialize peak splitter

        Args:
            time: Time array
            intensity: Intensity array
        """
        self.time = time
        self.intensity = intensity

    def split_peak_at_minimum(
        self,
        peak: Peak,
        split_rt: Optional[float] = None
    ) -> Tuple[Peak, Peak]:
        """
        Split peak at specified retention time or local minimum

        Args:
            peak: Peak to split
            split_rt: Retention time to split at (finds minimum if None)

        Returns:
            Tuple of two Peak objects
        """
        # Extract peak region
        start_idx = peak.index_start
        end_idx = peak.index_end
        peak_time = self.time[start_idx:end_idx + 1]
        peak_intensity = self.intensity[start_idx:end_idx + 1]

        # Find split point
        if split_rt is None:
            # Find local minimum in middle third of peak
            mid_start = len(peak_intensity) // 3
            mid_end = 2 * len(peak_intensity) // 3
            local_min_idx = mid_start + np.argmin(peak_intensity[mid_start:mid_end])
            split_idx = start_idx + local_min_idx
        else:
            split_idx = np.searchsorted(self.time, split_rt)

        # Create two peaks
        # Peak 1: start to split
        peak1_time = self.time[start_idx:split_idx + 1]
        peak1_intensity = self.intensity[start_idx:split_idx + 1]
        peak1_max_idx = start_idx + np.argmax(peak1_intensity)

        # Baseline for peak 1
        baseline1 = np.linspace(
            self.intensity[start_idx],
            self.intensity[split_idx],
            len(peak1_intensity)
        )
        corrected1 = peak1_intensity - baseline1
        area1 = np.trapz(corrected1, peak1_time)

        from .peak_detector import Peak as PeakClass

        peak1 = PeakClass(
            rt=self.time[peak1_max_idx],
            rt_start=self.time[start_idx],
            rt_end=self.time[split_idx],
            height=self.intensity[peak1_max_idx] - baseline1[peak1_max_idx - start_idx],
            area=max(0.0, area1),
            width=(self.time[split_idx] - self.time[start_idx]),
            index=peak1_max_idx,
            index_start=start_idx,
            index_end=split_idx
        )

        # Peak 2: split to end
        peak2_time = self.time[split_idx:end_idx + 1]
        peak2_intensity = self.intensity[split_idx:end_idx + 1]
        peak2_max_idx = split_idx + np.argmax(peak2_intensity)

        # Baseline for peak 2
        baseline2 = np.linspace(
            self.intensity[split_idx],
            self.intensity[end_idx],
            len(peak2_intensity)
        )
        corrected2 = peak2_intensity - baseline2
        area2 = np.trapz(corrected2, peak2_time)

        peak2 = PeakClass(
            rt=self.time[peak2_max_idx],
            rt_start=self.time[split_idx],
            rt_end=self.time[end_idx],
            height=self.intensity[peak2_max_idx] - baseline2[peak2_max_idx - split_idx],
            area=max(0.0, area2),
            width=(self.time[end_idx] - self.time[split_idx]),
            index=peak2_max_idx,
            index_start=split_idx,
            index_end=end_idx
        )

        return peak1, peak2

    def detect_overlapping_peaks(
        self,
        peaks: List[Peak],
        overlap_threshold: float = 0.5
    ) -> List[Tuple[int, int]]:
        """
        Detect overlapping peaks

        Args:
            peaks: List of peaks
            overlap_threshold: Minimum overlap ratio (0-1)

        Returns:
            List of (peak1_idx, peak2_idx) tuples for overlapping peaks
        """
        overlapping = []

        for i in range(len(peaks) - 1):
            peak1 = peaks[i]
            peak2 = peaks[i + 1]

            # Check if peaks overlap
            if peak1.rt_end > peak2.rt_start:
                overlap_time = peak1.rt_end - peak2.rt_start
                min_width = min(peak1.width, peak2.width)

                if overlap_time / min_width >= overlap_threshold:
                    overlapping.append((i, i + 1))

        return overlapping
