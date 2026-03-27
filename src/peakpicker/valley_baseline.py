"""
baseline.py — Valley drop-line baseline correction.

SRP: Only responsible for baseline correction operations.
"""
from typing import Optional

import numpy as np
from scipy.signal import savgol_filter

from .method_config_lc import SmoothingConfig, PeakDetectionConfig


class BaselineCorrector:
    """
    Valley drop-line baseline correction.

    Smooths the signal and provides the valley-based drop-line
    correction used during peak integration.
    """

    def __init__(self, smoothing: SmoothingConfig, peak_detection: PeakDetectionConfig):
        self._sw = smoothing.window
        self._sp = smoothing.poly
        self._trim_start = peak_detection.trim_rt_start
        self._trim_end = peak_detection.trim_rt_end

    def smooth(self, sig: np.ndarray) -> np.ndarray:
        """Apply Savitzky-Golay filter."""
        wl = min(self._sw, (len(sig) // 2) * 2 - 1)
        if wl >= 5:
            return savgol_filter(sig, wl, self._sp)
        return sig.copy()

    def apply_trim(self, time: np.ndarray, sig: np.ndarray) -> np.ndarray:
        """
        Zero out signal outside [trim_rt_start, trim_rt_end].
        Preserves baseline offset at boundaries.
        """
        if self._trim_start is None and self._trim_end is None:
            return sig
        masked = sig.copy()
        if self._trim_start is not None:
            masked[time < self._trim_start] = 0.0
        if self._trim_end is not None:
            masked[time > self._trim_end] = 0.0
        return masked

    @staticmethod
    def find_valley(
        time: np.ndarray,
        intensity: np.ndarray,
        rt_min: float,
        rt_max: float,
    ) -> Optional[int]:
        """Return index of minimum within [rt_min, rt_max], or None."""
        mask = (time >= rt_min) & (time <= rt_max)
        if not np.any(mask):
            return None
        idx = np.where(mask)[0]
        return int(idx[np.argmin(intensity[idx])])
