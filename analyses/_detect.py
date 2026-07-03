"""
Shared peak-detection wrapper for per-experiment ``analyses/*.py`` scripts.
===========================================================================

WHY THIS EXISTS
---------------
Historically every ``analyses/peakpicker_*.py`` script carried its own
``detect_peaks(time, intensity, prominence=<magic>, distance_pts=<magic>)``
with hard-coded magic numbers (e.g. 300/40, 500/50). That duplicated the
detection logic ~20 times and scattered thresholds.

This module is the SINGLE entry point those scripts should call. It routes
peak detection through the canonical detector
``peakpicker.peak_analysis.TwoPassPeakDetector`` and centralises the
per-experiment thresholds.

TWO ENTRY POINTS
----------------
1. ``detect_peaks_canonical(time, intensity, **overrides)`` — RECOMMENDED for
   NEW analyses. Uses the canonical two-pass detector (MAD-of-derivative noise,
   prominence-based two-pass). Returns a list of ``(rt, height)`` tuples, the
   same shape the old ``detect_peaks`` returned.

2. ``detect_peaks_legacy_single_pass(time, intensity, prominence, distance_pts)``
   — EXACT reproduction of the old single-pass ``scipy.find_peaks`` behaviour.
   Use this when migrating an EXISTING published analysis so the printed RT
   list does not change. It is a thin, centralised shim (still one code
   location) — not a re-implementation scattered per script.

MIGRATION PATTERN (see peakpicker_260317_Xul5P_AcP_Pre.py for a worked example)
------------------------------------------------------------------------------
    from _detect import detect_peaks_legacy_single_pass   # exact repro
    peaks = detect_peaks_legacy_single_pass(time, intensity,
                                            prominence=300, distance_pts=40)

IMPORTANT (number-SSOT): peak *areas* in these scripts are computed by
window integration (``get_area``), NOT by ``detect_peaks`` — the detected
peaks feed only a printed RT summary. Migrating detection therefore does not
touch any published area/yield number. Still, prefer the legacy shim when
reproducing an already-reported figure, and the canonical path for new work.
"""
import os
import sys
from typing import List, Tuple

import numpy as np

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def detect_peaks_legacy_single_pass(
    time: np.ndarray,
    intensity: np.ndarray,
    prominence: float,
    distance_pts: int,
) -> List[Tuple[float, float]]:
    """Exact reproduction of the old per-script ``detect_peaks``.

    Returns ``[(retention_time, height), ...]``. Byte-identical to the former
    ``find_peaks(intensity, prominence=prominence, distance=distance_pts)``
    scattered across analyses scripts — centralised here so the magic numbers
    live at the call site only.
    """
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(intensity, prominence=prominence, distance=distance_pts)
    return [(float(time[p]), float(intensity[p])) for p in peaks]


def detect_peaks_canonical(
    time: np.ndarray,
    intensity: np.ndarray,
    baseline: np.ndarray = None,
    **detector_overrides,
) -> List[Tuple[float, float]]:
    """Detect peaks via the canonical ``TwoPassPeakDetector``.

    RECOMMENDED for new analyses. ``detector_overrides`` are forwarded to the
    ``TwoPassPeakDetector`` constructor (e.g. ``major_prominence_factor``,
    ``major_distance``). Returns ``[(rt, height), ...]``.

    NOTE: results differ from ``detect_peaks_legacy_single_pass`` (two-pass +
    MAD noise vs single-pass fixed prominence). Do not swap this in under an
    already-published figure without re-checking the reported RTs.
    """
    from peakpicker.peak_analysis import TwoPassPeakDetector
    from peakpicker.config import PeakDetectionConfig

    class _ScipyFindPeaks:
        def find_peaks(self, signal, prominence=None, distance=None,
                       height=None, width=None):
            from scipy.signal import find_peaks
            kw = {}
            if prominence is not None:
                kw["prominence"] = prominence
            if distance is not None:
                kw["distance"] = distance
            if height is not None:
                kw["height"] = height
            if width is not None:
                kw["width"] = width
            return find_peaks(signal, **kw)

    detector = TwoPassPeakDetector(
        signal_processor=_ScipyFindPeaks(),
        config=PeakDetectionConfig(),
        **detector_overrides,
    )
    peaks = detector.detect(np.asarray(time), np.asarray(intensity), baseline)
    return [(p.rt, p.height) for p in peaks]
