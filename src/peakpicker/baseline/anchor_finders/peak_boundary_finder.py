"""
Peak Boundary Anchor Finder
===========================

scipy prominence의 left_bases/right_bases를 이용해
각 피크(양수/음수 모두)의 실제 valley 지점을 앵커로 사용.

Valley-to-valley baseline의 핵심: 피크 경계 = 실제 baseline 앵커.
LocalMinAnchorFinder와 달리 피크 내부를 앵커로 잡지 않음.
"""

from typing import List
import numpy as np

from ...interfaces import IAnchorFinder, ISignalProcessor
from ...domain import AnchorPoint, AnchorSource
from ...config import AnchorFinderConfig


class PeakBoundaryAnchorFinder(IAnchorFinder):
    """
    피크(양수/음수)의 좌우 valley를 앵커 포인트로 사용.

    scipy find_peaks의 prominence base (left_bases, right_bases)를
    활용하므로 피크 내부를 앵커로 잡는 문제가 없음.
    음수 피크도 동일 로직으로 처리 → baseline이 음수 피크 위로 지나감.
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

        # --- 양수 피크 ---
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

        # --- 음수 피크 ---
        # -smoothed에서 피크를 찾으면 원래 신호의 negative peak
        # 이 때 left_bases/right_bases는 음수 피크의 좌우 "어깨" (signal이 다시 올라오는 지점)
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
                # baseline은 음수 피크 양쪽 어깨 값 (= signal 위로 지나가야 함)
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
