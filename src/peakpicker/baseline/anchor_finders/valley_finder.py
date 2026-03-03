"""
Valley Anchor Point Finder
==========================

Finds baseline anchor points using valley detection.
Single Responsibility: Only finds valley anchor points.
"""

from typing import List
import numpy as np

from ...interfaces import IAnchorFinder, ISignalProcessor
from ...domain import AnchorPoint, AnchorSource
from ...config import AnchorFinderConfig


class ValleyAnchorFinder(IAnchorFinder):
    """
    Finds anchor points by detecting valleys (inverse peaks).

    Uses prominence-based peak detection on inverted signal.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        config: AnchorFinderConfig = None
    ):
        """
        Initialize valley finder.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation (dependency injection)
        config : AnchorFinderConfig, optional
            Configuration parameters
        """
        self.signal_processor = signal_processor
        self.config = config or AnchorFinderConfig()

    def find_anchors(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> List[AnchorPoint]:
        """
        Find valley anchor points in signal.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        List[AnchorPoint]
            Detected valley anchor points
        """
        # Smooth signal first
        window = min(21, len(signal) // 20)
        if window % 2 == 0:
            window += 1
        if window < 5:
            window = 5

        smoothed = self.signal_processor.smooth(signal, window, polyorder=3)

        # Find peaks in inverted signal (valleys)
        inverted = -smoothed
        signal_range = np.ptp(smoothed)
        prominence = signal_range * self.config.valley_prominence

        valleys, _ = self.signal_processor.find_peaks(
            inverted,
            prominence=prominence,
            distance=self.config.valley_distance
        )

        # Create anchor points
        anchors = []
        for v_idx in valleys:
            anchors.append(AnchorPoint(
                index=int(v_idx),
                time=float(time[v_idx]),
                value=float(signal[v_idx]),
                confidence=1.0,  # Valleys have high confidence
                source=AnchorSource.VALLEY
            ))

        return anchors


class LocalMinAnchorFinder(IAnchorFinder):
    """
    Finds anchor points by detecting local minima.

    Searches within windows for low-percentile points.
    """

    def __init__(
        self,
        signal_processor: ISignalProcessor,
        config: AnchorFinderConfig = None
    ):
        """
        Initialize local minimum finder.

        Parameters
        ----------
        signal_processor : ISignalProcessor
            Signal processing implementation
        config : AnchorFinderConfig, optional
            Configuration parameters
        """
        self.signal_processor = signal_processor
        self.config = config or AnchorFinderConfig()

    def find_anchors(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> List[AnchorPoint]:
        """
        Find local minimum anchor points.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        List[AnchorPoint]
            Detected local minimum anchor points
        """
        local_window = self.config.local_window
        if local_window is None:
            local_window = max(20, len(signal) // 50)

        anchors = []

        # Scan signal in windows
        for win_start in range(0, len(signal), local_window // 2):
            win_end = min(win_start + local_window, len(signal))
            segment = signal[win_start:win_end]

            if len(segment) == 0:
                continue

            # Find points below percentile threshold
            threshold = np.percentile(segment, self.config.percentile)
            min_mask = segment <= threshold

            if np.any(min_mask):
                # Find the actual minimum in this segment
                local_min_idx = win_start + np.argmin(segment)

                # Calculate confidence based on local gradient
                if 0 < local_min_idx < len(signal) - 1:
                    gradient = abs(
                        signal[local_min_idx + 1] - signal[local_min_idx - 1]
                    )
                    # Flatter areas have higher confidence
                    confidence = 1.0 / (1.0 + gradient / 1000.0)
                else:
                    confidence = 0.5

                anchors.append(AnchorPoint(
                    index=int(local_min_idx),
                    time=float(time[local_min_idx]),
                    value=float(signal[local_min_idx]),
                    confidence=float(min(1.0, max(0.0, confidence))),
                    source=AnchorSource.LOCAL_MIN
                ))

        return anchors


class BoundaryAnchorFinder(IAnchorFinder):
    """
    Adds boundary anchor points at signal start and end.

    Ensures baseline is defined at signal boundaries.
    """

    def __init__(self, config: AnchorFinderConfig = None):
        """
        Initialize boundary finder.

        Parameters
        ----------
        config : AnchorFinderConfig, optional
            Configuration parameters
        """
        self.config = config or AnchorFinderConfig()

    def find_anchors(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> List[AnchorPoint]:
        """
        Add boundary anchor points.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        List[AnchorPoint]
            Boundary anchor points (start and end)
        """
        anchors = []

        # Start boundary
        anchors.append(AnchorPoint(
            index=0,
            time=float(time[0]),
            value=float(signal[0]),
            confidence=0.8,
            source=AnchorSource.BOUNDARY
        ))

        # End boundary
        anchors.append(AnchorPoint(
            index=len(signal) - 1,
            time=float(time[-1]),
            value=float(signal[-1]),
            confidence=0.8,
            source=AnchorSource.BOUNDARY
        ))

        return anchors


class CompositeAnchorFinder(IAnchorFinder):
    """
    Combines multiple anchor finders and filters results.

    Composite pattern - composes multiple IAnchorFinder implementations.
    """

    def __init__(
        self,
        finders: List[IAnchorFinder],
        config: AnchorFinderConfig = None
    ):
        """
        Initialize composite finder.

        Parameters
        ----------
        finders : List[IAnchorFinder]
            List of anchor finders to combine
        config : AnchorFinderConfig, optional
            Configuration for filtering
        """
        self.finders = finders
        self.config = config or AnchorFinderConfig()

    def find_anchors(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> List[AnchorPoint]:
        """
        Find anchors using all finders and merge results.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        List[AnchorPoint]
            Merged and filtered anchor points
        """
        all_anchors = []

        # Collect anchors from all finders
        for finder in self.finders:
            anchors = finder.find_anchors(time, signal)
            all_anchors.extend(anchors)

        # Sort by index
        all_anchors.sort(key=lambda p: p.index)

        # Remove duplicates and close points
        filtered = self._filter_close_anchors(all_anchors)

        # Remove outliers
        if self.config.outlier_removal and len(filtered) > 5:
            filtered = self._remove_outliers(filtered)

        return filtered

    def _filter_close_anchors(self, anchors: List[AnchorPoint]) -> List[AnchorPoint]:
        """Remove anchors that are too close, keeping higher confidence."""
        if len(anchors) <= 1:
            return anchors

        filtered = []
        for anchor in anchors:
            # Check if too close to existing anchor
            too_close = False
            for i, existing in enumerate(filtered):
                if abs(anchor.index - existing.index) < self.config.min_distance:
                    too_close = True
                    # Keep higher confidence
                    if anchor.confidence > existing.confidence:
                        filtered[i] = anchor
                    break

            if not too_close:
                filtered.append(anchor)

        return sorted(filtered, key=lambda p: p.index)

    def _remove_outliers(self, anchors: List[AnchorPoint]) -> List[AnchorPoint]:
        """Remove outlier anchor points using MAD."""
        values = np.array([p.value for p in anchors])
        median_value = np.median(values)
        mad = np.median(np.abs(values - median_value))

        # Signal-relative threshold (replaces hardcoded absolute 100)
        signal_range = np.ptp(values) if len(values) > 1 else 1.0
        if mad < signal_range * 0.01:
            # Stable baseline - use percentile
            threshold = np.percentile(values, 10)
        else:
            # Variable baseline - use MAD
            threshold = median_value - self.config.outlier_mad_threshold * mad

        return [p for p in anchors if p.value >= threshold]
