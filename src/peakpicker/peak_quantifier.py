"""
peak_quantifier.py — Peak area quantification using valley drop-line baseline.

SRP: Only responsible for detecting peaks and computing areas.
DIP: Depends on BaselineCorrector (abstraction), not on a specific strategy.
"""
from typing import Optional, Tuple

import numpy as np
from scipy.signal import find_peaks
from scipy.integrate import trapezoid

from .models import CompoundMethod, QuantResult
from .method_config_lc import SmoothingConfig, PeakDetectionConfig
from .valley_baseline import BaselineCorrector


class PeakQuantifier:
    """
    Valley drop-line baseline peak quantifier.

    For each compound, finds the apex within the expected RT window,
    locates flanking valleys, draws a drop-line baseline, and integrates
    the corrected peak area.
    """

    def __init__(
        self,
        peak_detection: PeakDetectionConfig,
        smoothing: SmoothingConfig,
    ):
        self._pd = peak_detection
        self._corrector = BaselineCorrector(smoothing, peak_detection)

    def smooth(self, sig: np.ndarray) -> np.ndarray:
        return self._corrector.smooth(sig)

    def apply_trim(self, time: np.ndarray, sig: np.ndarray) -> np.ndarray:
        return self._corrector.apply_trim(time, sig)

    def quantify_compound(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        compound: CompoundMethod,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Returns (area_nRIU_s, rt_detected_min).

        Uses valley drop-line baseline; apex search within rt_window.
        """
        rt_lo, rt_hi = compound.rt_window
        margin = (rt_hi - rt_lo) * 0.5

        lv_lo, lv_hi = rt_lo - margin, rt_lo
        rv_lo, rv_hi = rt_hi, rt_hi + margin

        mask_all = (time >= lv_lo) & (time <= rv_hi)
        if not np.any(mask_all):
            return None, None

        idx_all = np.where(mask_all)[0]
        t_all = time[idx_all]
        s_all = intensity[idx_all]

        noise = np.std(np.diff(s_all)) * 1.4826
        min_prom = max(
            noise * self._pd.min_prominence_factor,
            np.ptp(s_all) * self._pd.min_height_fraction,
        )

        mask_search = (t_all >= rt_lo) & (t_all <= rt_hi)
        local_idx = np.where(mask_search)[0]
        if len(local_idx) == 0:
            return None, None

        peaks, _ = find_peaks(s_all, prominence=min_prom, distance=self._pd.distance_pts)

        peak_local: Optional[int] = None
        best_h = -np.inf
        for p in peaks:
            if mask_search[p] and s_all[p] > best_h:
                best_h = s_all[p]
                peak_local = p

        if peak_local is None:
            best_local = local_idx[np.argmax(s_all[local_idx])]
            if s_all[best_local] < noise * self._pd.min_prominence_factor:
                return None, None
            peak_local = best_local

        rt_detected = float(t_all[peak_local])
        peak_global_idx = idx_all[peak_local]

        left_v = self._corrector.find_valley(time, intensity, lv_lo, lv_hi)
        right_v = self._corrector.find_valley(time, intensity, rv_lo, rv_hi)
        if left_v is None:
            left_v = int(idx_all[0])
        if right_v is None:
            right_v = int(idx_all[-1])

        t_seg = time[left_v:right_v + 1]
        s_seg = intensity[left_v:right_v + 1]
        bl = np.interp(t_seg, [t_seg[0], t_seg[-1]], [s_seg[0], s_seg[-1]])
        corrected = s_seg - bl

        peak_rel = peak_global_idx - left_v
        if not (0 <= peak_rel < len(corrected)):
            return None, rt_detected

        peak_h = max(corrected[peak_rel], 0)
        noise2 = np.std(np.diff(s_seg)) * 0.5
        threshold = max(peak_h * 0.02, noise2 * 0.5)

        left_b = peak_rel
        while left_b > 0 and corrected[left_b] > threshold:
            left_b -= 1
        right_b = peak_rel
        while right_b < len(corrected) - 1 and corrected[right_b] > threshold:
            right_b += 1

        area = float(trapezoid(
            np.maximum(corrected[left_b:right_b + 1], 0),
            t_seg[left_b:right_b + 1] * 60,  # min → sec
        ))

        return area, rt_detected

    def area_to_conc(self, area: float, compound: CompoundMethod) -> Optional[float]:
        """Convert area to concentration using linear calibration."""
        if compound.slope is None or compound.slope == 0:
            return None
        return area * compound.slope + compound.intercept
