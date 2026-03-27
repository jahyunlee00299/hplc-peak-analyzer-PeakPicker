"""
Automatic peak boundary detection and integration for HPX-87H HPLC RID chromatograms.

Supports three integration modes:
  - 'full': complete peak with valley-to-valley baseline
  - 'left_half': left boundary to peak apex (for overlapping peaks, e.g., D-Xylose)
  - 'right_half': peak apex to right boundary (for overlapping peaks, e.g., D-Xylulose)
"""

import numpy as np
from typing import Tuple


def find_peak_boundaries(
    time: np.ndarray,
    intensity: np.ndarray,
    rt_hint: float,
    search_half_width: float = 1.2,
    threshold_ratio: float = 0.003,
) -> Tuple[int, int, int, float]:
    """
    Detect peak boundaries around rt_hint using valley detection with threshold fallback.

    Algorithm (from peak apex, scanning outward in each direction):
      1. Valley: signal decreasing then increasing = local minimum (adjacent peak boundary)
      2. Threshold: signal drops below peak_max * threshold_ratio
      3. Fallback: search window edge

    Parameters
    ----------
    time : array
        Retention time in minutes.
    intensity : array
        Detector signal (nRIU).
    rt_hint : float
        Approximate retention time of the target peak (minutes).
    search_half_width : float
        Half-width of the search window around rt_hint (minutes).
    threshold_ratio : float
        Fraction of peak maximum used as the noise floor cutoff.

    Returns
    -------
    left_idx, right_idx, peak_idx, peak_max
        Indices into the *original* time/intensity arrays, plus the peak maximum value.
    """
    # Restrict to search window
    lo_time = rt_hint - search_half_width
    hi_time = rt_hint + search_half_width
    win_mask = (time >= lo_time) & (time <= hi_time)
    win_indices = np.where(win_mask)[0]

    if len(win_indices) == 0:
        raise ValueError(f"No data points in search window [{lo_time:.2f}, {hi_time:.2f}] min")

    win_start = win_indices[0]
    win_end = win_indices[-1]

    # Find peak apex within window
    win_intensity = intensity[win_start:win_end + 1]
    local_peak = np.argmax(win_intensity)
    peak_idx = win_start + local_peak
    peak_max = intensity[peak_idx]
    threshold = peak_max * threshold_ratio

    # --- Scan LEFT from peak ---
    left_idx = peak_idx
    prev_val = intensity[peak_idx]
    for i in range(peak_idx - 1, win_start - 1, -1):
        cur_val = intensity[i]
        if cur_val > prev_val and prev_val < peak_max * 0.5:
            # Valley detected: signal was decreasing, now increasing
            left_idx = i + 1  # the minimum point
            break
        if cur_val <= threshold:
            left_idx = i
            break
        prev_val = cur_val
        left_idx = i

    # --- Scan RIGHT from peak ---
    right_idx = peak_idx
    prev_val = intensity[peak_idx]
    for i in range(peak_idx + 1, win_end + 1):
        cur_val = intensity[i]
        if cur_val > prev_val and prev_val < peak_max * 0.5:
            # Valley detected
            right_idx = i - 1  # the minimum point
            break
        if cur_val <= threshold:
            right_idx = i
            break
        prev_val = cur_val
        right_idx = i

    return left_idx, right_idx, peak_idx, peak_max


def integrate_peak(
    time: np.ndarray,
    intensity: np.ndarray,
    rt_hint: float,
    mode: str = "full",
    search_half_width: float = 1.2,
    threshold_ratio: float = 0.003,
) -> float:
    """
    Integrate a chromatographic peak with valley baseline correction.

    Parameters
    ----------
    time : array
        Retention time in minutes.
    intensity : array
        Detector signal (nRIU).
    rt_hint : float
        Approximate retention time (minutes).
    mode : str
        'full'       - integrate entire peak (left boundary to right boundary)
        'left_half'  - integrate left boundary to peak apex only
        'right_half' - integrate peak apex to right boundary only
    search_half_width : float
        Half-width of search window (minutes).
    threshold_ratio : float
        Noise floor as fraction of peak max.

    Returns
    -------
    area : float
        Integrated area in nRIU * s (time converted from min to seconds).
    """
    left_idx, right_idx, peak_idx, peak_max = find_peak_boundaries(
        time, intensity, rt_hint, search_half_width, threshold_ratio
    )

    if mode == "full":
        seg_t = time[left_idx:right_idx + 1]
        seg_i = intensity[left_idx:right_idx + 1]
        # Valley baseline: straight line from left boundary to right boundary
        baseline = np.linspace(seg_i[0], seg_i[-1], len(seg_i))
        area = np.trapezoid(seg_i - baseline, seg_t) * 60.0  # min -> s

    elif mode == "left_half":
        seg_t = time[left_idx:peak_idx + 1]
        seg_i = intensity[left_idx:peak_idx + 1]
        # Baseline: horizontal line at left boundary signal level
        baseline_val = intensity[left_idx]
        area = np.trapezoid(seg_i - baseline_val, seg_t) * 60.0

    elif mode == "right_half":
        seg_t = time[peak_idx:right_idx + 1]
        seg_i = intensity[peak_idx:right_idx + 1]
        # Baseline: horizontal line at right boundary signal level
        baseline_val = intensity[right_idx]
        area = np.trapezoid(seg_i - baseline_val, seg_t) * 60.0

    else:
        raise ValueError(f"Unknown mode '{mode}'. Use 'full', 'left_half', or 'right_half'.")

    return area


def integrate_peak_detailed(
    time: np.ndarray,
    intensity: np.ndarray,
    rt_hint: float,
    mode: str = "full",
    search_half_width: float = 1.2,
    threshold_ratio: float = 0.003,
) -> dict:
    """
    Like integrate_peak but returns a detailed result dict.

    Returns
    -------
    dict with keys:
        area, peak_rt, peak_max, rt_lo, rt_hi, mode
    """
    left_idx, right_idx, peak_idx, peak_max = find_peak_boundaries(
        time, intensity, rt_hint, search_half_width, threshold_ratio
    )
    area = integrate_peak(time, intensity, rt_hint, mode, search_half_width, threshold_ratio)

    return {
        "area": area,
        "peak_rt": time[peak_idx],
        "peak_max": peak_max,
        "rt_lo": time[left_idx],
        "rt_hi": time[right_idx],
        "mode": mode,
    }
