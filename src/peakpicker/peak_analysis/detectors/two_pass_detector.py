"""
Two-Pass Adaptive Peak Detector
=================================

Pass 1: Major peaks  — high prominence, strict distance
Pass 2: Minor peaks  — low prominence, relaxed distance
Result: Deduplicated union of both passes

This strategy reliably catches both large dominant peaks and
small satellite / impurity peaks without false positives.
"""

import logging
from typing import List, Tuple

import numpy as np

from ...interfaces import IPeakDetector, IPeakBoundaryFinder, ISignalProcessor
from ...domain import Peak, PeakType
from ...config import PeakDetectionConfig

logger = logging.getLogger(__name__)


class TwoPassPeakDetector(IPeakDetector):
    """
    Detects peaks in two passes with different sensitivity settings.

    Pass 1 (major): prominence = signal_range * major_factor,
                    distance  = major_distance
    Pass 2 (minor): prominence = noise_level * minor_multiplier,
                    distance  = minor_distance

    Peaks within dedup_distance points of a major peak are dropped.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        boundary_finder: IPeakBoundaryFinder = None,
        config: PeakDetectionConfig = None,
        major_prominence_factor: float = 0.005,
        major_distance: int = 20,
        minor_noise_multiplier: float = 2.0,
        minor_distance: int = 5,
        dedup_distance: int = 10,
    ):
        self.signal_processor = signal_processor
        self.boundary_finder = boundary_finder
        self.config = config or PeakDetectionConfig()
        self.major_prominence_factor = major_prominence_factor
        self.major_distance = major_distance
        self.minor_noise_multiplier = minor_noise_multiplier
        self.minor_distance = minor_distance
        self.dedup_distance = dedup_distance

    def detect(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        baseline: np.ndarray = None,
    ) -> List[Peak]:
        if baseline is not None:
            corrected = signal - baseline
        else:
            corrected = signal
            baseline = np.zeros_like(signal)

        corrected = np.maximum(corrected, 0)

        noise_level = self._estimate_noise(corrected)
        signal_range = np.ptp(corrected)

        # Pass 1 — major peaks
        major_indices = self._find_peaks(
            corrected,
            prominence=max(signal_range * self.major_prominence_factor,
                           noise_level * 3),
            height=noise_level * 3,
            distance=self.major_distance,
            width=self.config.min_width,
        )

        # Pass 2 — minor peaks
        minor_indices = self._find_peaks(
            corrected,
            prominence=noise_level * self.minor_noise_multiplier,
            height=noise_level * self.minor_noise_multiplier,
            distance=self.minor_distance,
            width=max(2, self.config.min_width - 1),
        )

        # Merge — drop minor if too close to a major
        combined = self._merge(major_indices, minor_indices)
        combined.sort()

        logger.debug(
            "TwoPassDetector: %d major + %d minor → %d combined",
            len(major_indices), len(minor_indices), len(combined),
        )

        # Build Peak objects
        peaks = []
        for i, idx in enumerate(combined):
            start_idx, end_idx = self._get_boundaries(
                corrected, idx, combined, i
            )
            apex = int(idx)
            rt = float(time[apex])
            rt_start = float(time[start_idx])
            rt_end = float(time[end_idx])
            height = float(corrected[apex])
            # Integrate in seconds (time is in minutes) to match Chemstation units
            area = float(np.trapezoid(
                corrected[start_idx:end_idx + 1],
                time[start_idx:end_idx + 1] * 60.0,
            ))
            left_area = float(np.trapezoid(
                corrected[start_idx:apex + 1],
                time[start_idx:apex + 1] * 60.0,
            ))
            right_area = float(np.trapezoid(
                corrected[apex:end_idx + 1],
                time[apex:end_idx + 1] * 60.0,
            ))
            peaks.append(Peak(
                index=apex,
                rt=rt,
                index_start=int(start_idx),
                index_end=int(end_idx),
                rt_start=rt_start,
                rt_end=rt_end,
                height=height,
                area=area,
                width=rt_end - rt_start,
                peak_type=PeakType.MAIN,
                left_area=left_area,
                right_area=right_area,
            ))

        total_area = sum(p.area for p in peaks)
        if total_area > 0:
            for p in peaks:
                p.area_percent = p.area / total_area * 100

        return peaks

    def _estimate_noise(self, signal: np.ndarray) -> float:
        """MAD-based noise estimation (robust vs. standard deviation)."""
        if len(signal) < 2:
            return 1.0
        deriv = np.diff(signal)
        mad = np.median(np.abs(deriv - np.median(deriv)))
        noise = mad * 1.4826
        return max(float(noise), 1.0)

    def _find_peaks(
        self,
        signal: np.ndarray,
        prominence: float,
        height: float,
        distance: int,
        width: int,
    ) -> List[int]:
        indices, _ = self.signal_processor.find_peaks(
            signal,
            prominence=prominence,
            height=height,
            distance=distance,
            width=width,
        )
        return list(map(int, indices))

    def _merge(self, major: List[int], minor: List[int]) -> List[int]:
        """Keep minor peaks not within dedup_distance of any major peak."""
        if not major:
            return list(minor)
        result = list(major)
        for m in minor:
            if all(abs(m - maj) >= self.dedup_distance for maj in major):
                result.append(m)
        return result

    def _get_boundaries(
        self,
        signal: np.ndarray,
        peak_idx: int,
        all_peaks: List[int],
        peak_pos: int,
    ) -> Tuple[int, int]:
        """1% threshold descent, capped at adjacent valley."""
        peak_height = signal[peak_idx]
        threshold = peak_height * self.config.boundary_threshold

        left = peak_idx
        while left > 0 and signal[left] > threshold:
            left -= 1

        right = peak_idx
        while right < len(signal) - 1 and signal[right] > threshold:
            right += 1

        # Cap at valley between adjacent peaks
        if peak_pos > 0:
            prev_idx = all_peaks[peak_pos - 1]
            region = signal[prev_idx:peak_idx]
            if len(region) > 0:
                left = max(left, prev_idx + int(np.argmin(region)))

        if peak_pos < len(all_peaks) - 1:
            next_idx = all_peaks[peak_pos + 1]
            region = signal[peak_idx:next_idx]
            if len(region) > 0:
                right = min(right, peak_idx + int(np.argmin(region)))

        return left, right
