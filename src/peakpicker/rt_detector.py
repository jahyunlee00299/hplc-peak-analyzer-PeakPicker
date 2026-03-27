"""
rt_detector.py — Automatic RT peak detection utility.

SRP: Only responsible for detecting retention time peaks in a signal file.
     Used during method development, not in the main quantification pipeline.
"""
from pathlib import Path
from typing import List, Tuple

import numpy as np
from scipy.signal import savgol_filter, find_peaks
from scipy.integrate import trapezoid

from .chromatogram_io import ChromatogramParser


class RtAutoDetector:
    """
    Detect top-N peaks in a chromatogram for method development.

    Usage:
        detector = RtAutoDetector()
        peaks = detector.detect("path/to/RID1A.ch", n_peaks=10)
        # returns [(rt_min, height, rough_area), ...]
    """

    def detect(
        self,
        ch_path: str,
        n_peaks: int = 10,
    ) -> List[Tuple[float, float, float]]:
        """
        Returns list of (rt_min, height, rough_area) sorted by height descending.
        """
        time, raw_sig = ChromatogramParser.load(Path(ch_path))

        wl = min(11, (len(raw_sig) // 2) * 2 - 1)
        sig = savgol_filter(raw_sig, max(wl, 5), 3) if wl >= 5 else raw_sig.copy()

        noise = np.std(np.diff(sig)) * 1.4826
        min_prom = max(noise * 3.0, np.ptp(sig) * 0.005)

        peaks, _ = find_peaks(
            sig,
            prominence=min_prom,
            distance=10,
            height=np.median(sig) + noise,
        )

        results: List[Tuple[float, float, float]] = []
        for p in peaks:
            rt = float(time[p])
            height = float(sig[p])
            mask = (time >= rt - 0.3) & (time <= rt + 0.3)
            area_rough = float(
                trapezoid(np.maximum(sig[mask] - noise, 0), time[mask] * 60)
            ) if np.any(mask) else 0.0
            results.append((rt, height, area_rough))

        results.sort(key=lambda x: x[1], reverse=True)
        top = results[:n_peaks]

        print(f"\n[RtAutoDetector] {Path(ch_path).name} — top {len(top)} peaks:")
        print(f"  {'RT(min)':>8}  {'Height':>12}  {'Area(rough)':>14}")
        for rt, h, a in sorted(top, key=lambda x: x[0]):
            print(f"  {rt:>8.3f}  {h:>12.1f}  {a:>14.1f}")

        return top
