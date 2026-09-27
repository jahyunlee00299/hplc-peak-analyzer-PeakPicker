"""
Peak Boundary Anchor Finder
===========================

Uses scipy prominence's left_bases/right_bases to take the actual valley
point of each peak (positive or negative) as an anchor.

The core of a valley-to-valley baseline: a peak boundary IS the real baseline
anchor. Unlike LocalMinAnchorFinder, this never picks a point inside a peak
as an anchor.
"""

from typing import List
import numpy as np

from ...interfaces import IAnchorFinder, ISignalProcessor
from ...domain import AnchorPoint, AnchorSource
from ...config import AnchorFinderConfig


class PeakBoundaryAnchorFinder(IAnchorFinder):
    """
    Uses the left/right valleys of each peak (positive or negative) as anchor points.

    Leverages scipy find_peaks' prominence base (left_bases, right_bases),
    so it never has the problem of anchoring inside a peak.
    Negative peaks are handled with the same logic -> the baseline passes above negative peaks.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        config: AnchorFinderConfig = None
    ):
        self.signal_processor = signal_processor
        self.config = config or AnchorFinderConfig()

    def find_anchors(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> List[AnchorPoint]:
        window = min(21, len(signal) // 20)
        if window % 2 == 0:
            window += 1
        window = max(window, 5)
        smoothed = self.signal_processor.smooth(signal, window, polyorder=3)

        signal_range = np.ptp(smoothed)
        if signal_range < 1e-10:
            return []

        prominence = signal_range * self.config.valley_prominence

        anchors = []

        # --- Positive peaks ---
        pos_peaks, pos_props = self.signal_processor.find_peaks(
            smoothed,
            prominence=prominence,
            distance=self.config.valley_distance,
        )
        if len(pos_peaks) > 0 and 'left_bases' in pos_props:
            for i in range(len(pos_peaks)):
                left = int(pos_props['left_bases'][i])
                right = int(pos_props['right_bases'][i])
                anchors.append(AnchorPoint(
                    index=left,
                    time=float(time[left]),
                    value=float(signal[left]),
                    confidence=0.9,
                    source=AnchorSource.VALLEY,
                ))
                anchors.append(AnchorPoint(
                    index=right,
                    time=float(time[right]),
                    value=float(signal[right]),
                    confidence=0.9,
                    source=AnchorSource.VALLEY,
                ))

        # --- Negative peaks ---
        # Finding peaks in -smoothed finds the negative peaks of the original signal.
        # Here, left_bases/right_bases are the "shoulders" on either side of the
        # negative peak (the points where the signal rises back up).
        neg_prominence = signal_range * self.config.valley_prominence * 0.5
        neg_peaks, neg_props = self.signal_processor.find_peaks(
            -smoothed,
            prominence=neg_prominence,
            distance=self.config.valley_distance,
        )
        if len(neg_peaks) > 0 and 'left_bases' in neg_props:
            for i in range(len(neg_peaks)):
                left = int(neg_props['left_bases'][i])
                right = int(neg_props['right_bases'][i])
                # The baseline is the value at the shoulders on either side of the
                # negative peak (i.e. it must pass above the signal)
                anchors.append(AnchorPoint(
                    index=left,
                    time=float(time[left]),
                    value=float(signal[left]),
                    confidence=0.85,
                    source=AnchorSource.VALLEY,
                ))
                anchors.append(AnchorPoint(
                    index=right,
                    time=float(time[right]),
                    value=float(signal[right]),
                    confidence=0.85,
                    source=AnchorSource.VALLEY,
                ))

        return anchors
