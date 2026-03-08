"""
Weighted Spline Baseline Strategy
=================================

Generates baseline using confidence-weighted spline fitting.
Open/Closed Principle: New strategies can be added without modifying existing ones.
"""

from typing import List
import numpy as np

from ...interfaces import IBaselineStrategy, IInterpolator
from ...domain import AnchorPoint, BaselineMethod
from ...config import BaselineStrategyConfig


class WeightedSplineStrategy(IBaselineStrategy):
    """
    Generates baseline using confidence-weighted spline interpolation.

    Uses anchor point confidence as spline weights.
    """

    def __init__(
        self,
        interpolator: IInterpolator,
        config: BaselineStrategyConfig = None
    ):
        """
        Initialize weighted spline strategy.

        Parameters
        ----------
        interpolator : IInterpolator
            Interpolation implementation (dependency injection)
        config : BaselineStrategyConfig, optional
            Strategy configuration
        """
        self.interpolator = interpolator
        self.config = config or BaselineStrategyConfig()

    @property
    def method(self) -> BaselineMethod:
        """Return the baseline method enum."""
        return BaselineMethod.WEIGHTED_SPLINE

    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint],
        **kwargs
    ) -> np.ndarray:
        """
        Generate baseline using weighted spline.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        anchors : List[AnchorPoint]
            Anchor points with confidence scores
        **kwargs
            Additional parameters:
            - smooth_factor: Override default smoothing

        Returns
        -------
        np.ndarray
            Generated baseline
        """
        if len(anchors) == 0:
            return np.zeros_like(signal)

        # Extract anchor data
        indices = np.array([p.index for p in anchors])
        values = np.array([p.value for p in anchors])
        confidences = np.array([p.confidence for p in anchors])

        # Generate full index array
        x_new = np.arange(len(signal))

        # Calculate smoothing factor
        smooth_factor = kwargs.get('smooth_factor', self.config.confidence_weight)
        mean_confidence = np.mean(confidences)

        # Adaptive smoothing based on confidence
        # Higher confidence = less smoothing needed
        smoothing = len(indices) * smooth_factor * 0.5 * (1 - mean_confidence * 0.5)

        # Use spline interpolation with confidence weights
        if len(indices) > 3:
            baseline = self.interpolator.spline(
                indices.astype(float),
                values,
                x_new.astype(float),
                smoothing=smoothing,
                weights=confidences
            )
        else:
            # Fall back to linear for few points
            baseline = self.interpolator.linear(
                indices.astype(float),
                values,
                x_new.astype(float)
            )

        return baseline


class RobustFitStrategy(IBaselineStrategy):
    """
    Generates baseline using robust (outlier-resistant) fitting.

    Removes outlier anchor points before fitting.
    """

    def __init__(
        self,
        interpolator: IInterpolator,
        config: BaselineStrategyConfig = None
    ):
        """
        Initialize robust fit strategy.

        Parameters
        ----------
        interpolator : IInterpolator
            Interpolation implementation
        config : BaselineStrategyConfig, optional
            Strategy configuration
        """
        self.interpolator = interpolator
        self.config = config or BaselineStrategyConfig()

    @property
    def method(self) -> BaselineMethod:
        """Return the baseline method enum."""
        return BaselineMethod.ROBUST_FIT

    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint],
        **kwargs
    ) -> np.ndarray:
        """
        Generate baseline using robust fitting.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        anchors : List[AnchorPoint]
            Anchor points
        **kwargs
            Additional parameters

        Returns
        -------
        np.ndarray
            Generated baseline
        """
        if len(anchors) == 0:
            return np.zeros_like(signal)

        indices = np.array([p.index for p in anchors])
        values = np.array([p.value for p in anchors])
        confidences = np.array([p.confidence for p in anchors])

        # Remove outliers using MAD
        if len(values) > 5:
            median = np.median(values)
            mad = np.median(np.abs(values - median))
            threshold = median + self.config.mad_threshold * mad

            mask = values < threshold
            if np.sum(mask) >= 3:
                indices = indices[mask]
                values = values[mask]
                confidences = confidences[mask]

        x_new = np.arange(len(signal))
        smooth_factor = kwargs.get('smooth_factor', 0.5)

        if len(indices) > 3:
            smoothing = len(indices) * smooth_factor * 0.5
            baseline = self.interpolator.spline(
                indices.astype(float),
                values,
                x_new.astype(float),
                smoothing=smoothing,
                weights=confidences
            )
        else:
            baseline = self.interpolator.linear(
                indices.astype(float),
                values,
                x_new.astype(float)
            )

        return baseline


class AdaptiveConnectStrategy(IBaselineStrategy):
    """
    Generates baseline using adaptive connection between anchors.

    Uses different interpolation methods based on anchor types.
    """

    def __init__(
        self,
        interpolator: IInterpolator,
        config: BaselineStrategyConfig = None
    ):
        """
        Initialize adaptive connect strategy.

        Parameters
        ----------
        interpolator : IInterpolator
            Interpolation implementation
        config : BaselineStrategyConfig, optional
            Strategy configuration
        """
        self.interpolator = interpolator
        self.config = config or BaselineStrategyConfig()

    @property
    def method(self) -> BaselineMethod:
        """Return the baseline method enum."""
        return BaselineMethod.ADAPTIVE_CONNECT

    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint],
        **kwargs
    ) -> np.ndarray:
        """
        Generate baseline using adaptive connection.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        anchors : List[AnchorPoint]
            Anchor points
        **kwargs
            Additional parameters

        Returns
        -------
        np.ndarray
            Generated baseline
        """
        if len(anchors) == 0:
            return np.zeros_like(signal)

        baseline = np.zeros_like(signal, dtype=float)

        # Sort anchors by index
        sorted_anchors = sorted(anchors, key=lambda p: p.index)

        from ...domain import AnchorSource

        for i in range(len(sorted_anchors) - 1):
            start_anchor = sorted_anchors[i]
            end_anchor = sorted_anchors[i + 1]

            start_idx = start_anchor.index
            end_idx = end_anchor.index

            if end_idx <= start_idx:
                continue

            # Determine connection type based on anchor sources
            both_valleys = (
                start_anchor.source == AnchorSource.VALLEY and
                end_anchor.source == AnchorSource.VALLEY
            )

            if both_valleys and self.config.curve_valleys:
                # Curved connection between valleys
                baseline[start_idx:end_idx + 1] = self._curved_connection(
                    signal, start_anchor, end_anchor
                )
            else:
                # Linear connection
                baseline[start_idx:end_idx + 1] = np.linspace(
                    start_anchor.value,
                    end_anchor.value,
                    end_idx - start_idx + 1
                )

        return baseline

    def _curved_connection(
        self,
        signal: np.ndarray,
        start: AnchorPoint,
        end: AnchorPoint
    ) -> np.ndarray:
        """Create curved connection between valley anchors."""
        start_idx = start.index
        end_idx = end.index

        # Calculate mid-point
        mid_idx = (start_idx + end_idx) // 2
        segment = signal[start_idx:end_idx + 1]

        # Mid-point value based on segment minimum
        mid_value = min(
            (start.value + end.value) / 2,
            np.percentile(segment, self.config.mid_point_percentile)
        )

        # Create three-point spline
        x = np.array([start_idx, mid_idx, end_idx], dtype=float)
        y = np.array([start.value, mid_value, end.value])
        x_new = np.arange(start_idx, end_idx + 1, dtype=float)

        # Quadratic interpolation
        return self.interpolator.spline(x, y, x_new, smoothing=0)


class LinearStrategy(IBaselineStrategy):
    """
    Simple linear baseline strategy.

    Connects anchors with straight lines.
    """

    def __init__(self, interpolator: IInterpolator):
        """
        Initialize linear strategy.

        Parameters
        ----------
        interpolator : IInterpolator
            Interpolation implementation
        """
        self.interpolator = interpolator

    @property
    def method(self) -> BaselineMethod:
        """Return the baseline method enum."""
        return BaselineMethod.LINEAR

    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint],
        **kwargs
    ) -> np.ndarray:
        """
        Generate linear baseline.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        anchors : List[AnchorPoint]
            Anchor points
        **kwargs
            Unused

        Returns
        -------
        np.ndarray
            Linear baseline
        """
        if len(anchors) == 0:
            return np.zeros_like(signal)

        indices = np.array([p.index for p in anchors])
        values = np.array([p.value for p in anchors])
        x_new = np.arange(len(signal))

        return self.interpolator.linear(
            indices.astype(float),
            values,
            x_new.astype(float)
        )
