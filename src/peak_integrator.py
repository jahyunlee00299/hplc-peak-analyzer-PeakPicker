"""
Automatic peak boundary detection and integration for HPX-87H HPLC RID chromatograms.

Supports three integration modes:
  - 'full': complete peak with valley-to-valley baseline
  - 'left_half': left boundary to peak apex (for overlapping peaks, e.g., D-Xylose)
  - 'right_half': peak apex to right boundary (for overlapping peaks, e.g., D-Xylulose)
"""

import numpy as np
from scipy.signal import savgol_coeffs, savgol_filter
from typing import Tuple

try:  # `src` on sys.path
    from peakpicker.utils.numeric import trapezoid
except ModuleNotFoundError:  # repo root on sys.path (`from src.peak_integrator import ...`)
    from src.peakpicker.utils.numeric import trapezoid


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
      2. Threshold: signal drops below baseline + (peak_max - baseline) * threshold_ratio, where
         the local baseline level is the mean of the lowest 10 % of the search window
         (so an offset or negative baseline does not move the cutoff)
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
        Cutoff as a fraction of the peak height ABOVE the local baseline (not of the absolute peak
        maximum); it is raised to 3 noise sigma (of the smoothed signal) when the data are noisier than that.

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

    # Find peak apex within window (on the lightly smoothed signal so a noise spike is not taken as the apex)
    raw_window = intensity[win_start:win_end + 1]
    smooth_window, sigma_s = _smooth_and_noise(raw_window)
    local_peak = int(np.argmax(smooth_window))
    peak_idx = win_start + local_peak
    peak_max = intensity[peak_idx]

    # Local baseline level = mean of the lowest 10 % of the smoothed window (robust to a neighbouring
    # peak inside the window, unlike the window edges). All cutoffs are measured above it.
    n_low = max(3, len(smooth_window) // 10)
    baseline_level = float(np.mean(np.sort(smooth_window)[:n_low]))
    apex_s = float(smooth_window[local_peak])
    height = max(apex_s - baseline_level, 0.0)
    # Noise-aware cutoff: never below _NOISE_K sigma of the smoothed signal above the baseline, otherwise
    # the scan would run into the noise floor and lock on its first up-tick.
    cutoff = max(height * threshold_ratio, _NOISE_K * sigma_s)
    threshold = baseline_level + cutoff
    half_level = baseline_level + height * 0.5

    def scan(step: int) -> int:
        """Walk outward from the apex on the smoothed signal; stop at the cutoff or at a valley.

        A valley is declared only when the signal has rebounded more than _NOISE_K sigma above the running
        minimum (a neighbouring peak), not on the first noise up-tick; the boundary is then the minimum."""
        stop = len(smooth_window) if step > 0 else -1
        k = local_peak + step
        run_min, run_min_k = smooth_window[local_peak], local_peak
        last = local_peak
        while k != stop:
            cur = smooth_window[k]
            if cur < run_min:
                run_min, run_min_k = cur, k
            elif run_min < half_level and cur > run_min + _NOISE_K * sigma_s:
                return win_start + run_min_k
            if cur <= threshold:
                return win_start + k
            last = k
            k += step
        return win_start + last

    return scan(-1), scan(+1), peak_idx, peak_max


# Number of noise sigmas used for the cutoff floor and the valley rebound test.
_NOISE_K = 3.0


def _smooth_and_noise(values: np.ndarray) -> Tuple[np.ndarray, float]:
    """Savitzky-Golay smoothed copy of `values` and the noise sigma of that smoothed signal.

    Raw noise sigma = MAD of first differences / sqrt(2) (peak slopes are outliers, so MAD ignores them);
    the smoothed sigma follows from the filter coefficients (sigma_raw * ||h||). Short windows are returned
    unsmoothed. The filter length is limited to a third of the apex FWHM so a narrow peak is not flattened.
    """
    n = len(values)
    if n < 7:
        return values.astype(float), 0.0
    diffs = np.diff(values)
    sigma_raw = 1.4826 * np.median(np.abs(diffs - np.median(diffs))) / np.sqrt(2.0)
    above = values > 0.5 * (values.max() + np.sort(values)[:max(3, n // 10)].mean())
    fwhm_pts = int(above.sum())
    win = int(np.clip(fwhm_pts // 3, 5, 15))
    win += (win + 1) % 2
    win = min(win, n if n % 2 else n - 1)
    smoothed = savgol_filter(values.astype(float), win, 2)
    sigma_s = sigma_raw * float(np.sqrt(np.sum(savgol_coeffs(win, 2) ** 2)))
    return smoothed, sigma_s


def _edge_level(intensity: np.ndarray, idx: int, half: int = 3) -> float:
    """Mean of the raw signal over idx +- half points: the valley-line anchor without the single-point noise."""
    lo, hi = max(idx - half, 0), min(idx + half + 1, len(intensity))
    return float(np.mean(intensity[lo:hi]))


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
        Cutoff as a fraction of the peak height ABOVE the local baseline (not of the absolute peak
        maximum); it is raised to 3 noise sigma when the data are noisier than that.

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
        baseline = np.linspace(_edge_level(intensity, left_idx), _edge_level(intensity, right_idx), len(seg_i))
        area = trapezoid(seg_i - baseline, seg_t) * 60.0  # min -> s

    elif mode == "left_half":
        seg_t = time[left_idx:peak_idx + 1]
        seg_i = intensity[left_idx:peak_idx + 1]
        # Baseline: horizontal line at left boundary signal level
        baseline_val = _edge_level(intensity, left_idx)
        area = trapezoid(seg_i - baseline_val, seg_t) * 60.0

    elif mode == "right_half":
        seg_t = time[peak_idx:right_idx + 1]
        seg_i = intensity[peak_idx:right_idx + 1]
        # Baseline: horizontal line at right boundary signal level
        baseline_val = _edge_level(intensity, right_idx)
        area = trapezoid(seg_i - baseline_val, seg_t) * 60.0

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
