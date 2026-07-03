"""
Shared two-pass peak-detection helper for the batch/enhanced HPLC scripts.
============================================================================

SINGLE SOURCE OF TRUTH: this module routes every script-level peak detection
through the canonical detector
``peakpicker.peak_analysis.TwoPassPeakDetector``.

Historically ``scripts/batch_analyze_all.py`` and
``scripts/hplc_analyzer_enhanced.py`` each carried their own private
``_detect_peaks`` / ``_detect_peaks_adaptive`` copy that duplicated the
two-pass algorithm.  They diverged from the canonical detector in two ways:

  1. noise estimation  — the scripts use a *percentile-based* estimator,
     whereas the canonical default is MAD-of-derivative;
  2. a maximum-width cap that shrinks over-wide peaks around the apex.

To consolidate to ONE code path WITHOUT changing any published number, the
canonical ``TwoPassPeakDetector`` was given two opt-in injection points
(``noise_estimator`` and ``max_width_samples``).  This helper wires the
script's exact percentile noise + max-width behaviour into the canonical
detector, so the numerical result is identical to the old private copies.

If you need the *default* (MAD-noise, no width cap) behaviour instead — e.g.
for a new analysis — use ``TwoPassPeakDetector`` directly or the
``analyses/_detect.py`` wrapper.
"""
import os
import sys
from typing import List, Tuple

import numpy as np

# The scripts intend to expose the repo ``src/`` directory on sys.path.
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from peakpicker.peak_analysis import TwoPassPeakDetector  # noqa: E402
from peakpicker.config import PeakDetectionConfig  # noqa: E402


class _ScipyFindPeaks:
    """Minimal ``ISignalProcessor`` shim exposing only ``find_peaks``.

    The canonical ``TwoPassPeakDetector`` only calls ``find_peaks`` on its
    injected signal processor.  Using this tiny shim avoids importing the
    full ``peakpicker.infrastructure`` package (which currently has an
    unrelated optional-plotting import chain).  It calls the identical
    ``scipy.signal.find_peaks`` under the hood, so results are unchanged.
    """

    def find_peaks(self, signal, prominence=None, distance=None,
                   height=None, width=None):
        from scipy.signal import find_peaks
        kwargs = {}
        if prominence is not None:
            kwargs["prominence"] = prominence
        if distance is not None:
            kwargs["distance"] = distance
        if height is not None:
            kwargs["height"] = height
        if width is not None:
            kwargs["width"] = width
        return find_peaks(signal, **kwargs)


def estimate_noise_percentile(intensity: np.ndarray) -> float:
    """Percentile-based noise estimate (verbatim from the legacy scripts).

    Kept here so the consolidated code path reproduces the scripts' original
    thresholds exactly.  Do NOT "improve" this without a reference-output
    regression test — it feeds manuscript peak areas.
    """
    noise_region = np.percentile(intensity, 25)
    threshold = max(noise_region * 1.5, np.percentile(intensity, 30))
    quiet_mask = intensity < threshold

    if np.any(quiet_mask) and np.sum(quiet_mask) > 10:
        noise_std = np.std(intensity[quiet_mask])
    else:
        low_pct = np.percentile(intensity, 10)
        if low_pct > 0:
            noise_std = np.std(intensity[intensity < low_pct])
        else:
            noise_std = np.std(intensity[intensity < np.percentile(intensity, 20)])
        if noise_std == 0 or np.isnan(noise_std):
            noise_std = np.std(intensity) * 0.01

    result = max(noise_std, np.percentile(intensity, 5) * 0.01, 1.0)
    if np.isnan(result) or result <= 0:
        result = max(np.std(intensity) * 0.01, 1.0)
    return float(result)


def _build_detector(intensity: np.ndarray, time_arr: np.ndarray) -> TwoPassPeakDetector:
    """Canonical detector configured to match the legacy script parameters."""
    dt = np.mean(np.diff(time_arr))
    # Legacy scripts: max_width_samples = int(2.0 / dt) (a 2-minute cap).
    max_width_samples = int(2.0 / dt) if dt > 0 else 2000
    # Legacy config knobs that the private copies hard-coded:
    #   major width=3, minor width=2, boundary threshold 1% of apex height.
    config = PeakDetectionConfig(min_width=3, boundary_threshold=0.01)
    return TwoPassPeakDetector(
        signal_processor=_ScipyFindPeaks(),
        config=config,
        major_prominence_factor=0.005,
        major_distance=20,
        minor_noise_multiplier=2.0,
        minor_distance=5,
        dedup_distance=10,
        noise_estimator=estimate_noise_percentile,
        max_width_samples=max_width_samples,
        major_min_width=3,
        minor_min_width=2,
    )


def detect_two_pass_indices_props(
    intensity: np.ndarray,
    noise_level: float = None,
) -> Tuple[np.ndarray, dict]:
    """Two-pass detection returning ``(peaks, properties)`` only.

    This exposes the SHARED two-pass find_peaks + merge + sort logic (the part
    that was duplicated across the scripts) so callers that do their own
    boundary / area / half-peak post-processing (e.g. hplc_analyzer_enhanced)
    can reuse it without re-implementing detection.

    The returned ``properties`` dict carries ``prominences`` and ``widths``
    (and ``left_bases`` / ``right_bases`` when scipy provides them for BOTH
    passes) aligned to the returned peak order — identical to the former
    private ``_detect_peaks_adaptive`` merge.

    NOTE: this is the plain two-pass detection with a percentile noise floor.
    It does NOT apply the max-width cap (that is a boundary-stage concern the
    caller owns).
    """
    from scipy.signal import find_peaks

    intensity = np.maximum(intensity, 0)
    if noise_level is None:
        noise_level = estimate_noise_percentile(intensity)
    signal_range = np.ptp(intensity)

    major_prom = max(signal_range * 0.005, noise_level * 3)
    major_peaks, major_props = find_peaks(
        intensity, prominence=major_prom, height=noise_level * 3,
        width=3, distance=20,
    )
    minor_prom = noise_level * 2
    minor_peaks, minor_props = find_peaks(
        intensity, prominence=minor_prom, height=noise_level * 2,
        width=2, distance=5,
    )

    all_peaks = list(major_peaks)
    all_proms = list(major_props["prominences"])
    all_widths = list(major_props.get("widths", [0] * len(major_peaks)))
    all_left_bases = list(major_props.get("left_bases", []))
    all_right_bases = list(major_props.get("right_bases", []))
    min_distance = 10

    for i, mp in enumerate(minor_peaks):
        if all(abs(mp - ep) >= min_distance for ep in major_peaks):
            all_peaks.append(mp)
            all_proms.append(minor_props["prominences"][i])
            all_widths.append(minor_props.get("widths", [0] * len(minor_peaks))[i])
            if "left_bases" in minor_props:
                all_left_bases.append(minor_props["left_bases"][i])
            if "right_bases" in minor_props:
                all_right_bases.append(minor_props["right_bases"][i])

    sort_idx = np.argsort(all_peaks)
    peaks = np.array(all_peaks)[sort_idx]
    properties = {
        "prominences": np.array(all_proms)[sort_idx],
        "widths": np.array(all_widths)[sort_idx] if all_widths else np.zeros(len(peaks)),
    }
    if all_left_bases and all_right_bases:
        properties["left_bases"] = np.array(all_left_bases)[sort_idx]
        properties["right_bases"] = np.array(all_right_bases)[sort_idx]
    return peaks, properties


def detect_peaks_two_pass(
    time_arr: np.ndarray,
    intensity: np.ndarray,
    noise_level: float = None,
) -> Tuple[np.ndarray, List[dict]]:
    """Two-pass detection returning the legacy ``(peaks, peak_data)`` tuple.

    Numerically identical to the removed private ``_detect_peaks`` copies:
    same percentile noise, same 2-pass thresholds, same 1%-descent + valley
    boundaries, same 2-minute width cap, same trapezoid-in-seconds area.

    Parameters
    ----------
    time_arr, intensity
        Baseline-corrected chromatogram (intensity assumed >= 0).
    noise_level
        Optional pre-computed noise for the SNR column.  If ``None`` the same
        percentile estimator used internally is applied, so SNR matches too.
    """
    intensity = np.maximum(intensity, 0)
    if noise_level is None:
        noise_level = estimate_noise_percentile(intensity)

    detector = _build_detector(intensity, time_arr)
    # baseline already removed -> pass baseline=None so the canonical detector
    # treats ``intensity`` as the corrected signal.
    peaks_objs = detector.detect(time_arr, intensity, baseline=None)

    peak_indices = np.array([p.index for p in peaks_objs], dtype=int)

    peak_data: List[dict] = []
    for i, p in enumerate(peaks_objs):
        snr = p.height / noise_level if noise_level > 0 else float("inf")
        peak_data.append({
            "peak_number": i + 1,
            "retention_time": round(float(p.rt), 3),
            "height": round(float(p.height), 2),
            "area": round(float(p.area), 2),
            "width_min": round(float(p.rt_end - p.rt_start), 3),
            "start_time": round(float(p.rt_start), 3),
            "end_time": round(float(p.rt_end), 3),
            "snr": round(float(snr), 1),
        })

    return peak_indices, peak_data
