"""
Baseline Generator
==================

Generates baseline from anchor points using selected strategy.
Single Responsibility: Coordinates baseline generation.
"""

from typing import List
import numpy as np

from ...interfaces import IBaselineGenerator, IBaselineStrategy
from ...domain import AnchorPoint
from ...config import BaselineGeneratorConfig


class BaselineGenerator(IBaselineGenerator):
    """
    Generates baseline using a pluggable strategy.

    Applies post-processing constraints to generated baseline.
    """

    def __init__(
        self,
        strategy: IBaselineStrategy,
        config: BaselineGeneratorConfig = None
    ):
        """
        Initialize generator.

        Parameters
        ----------
        strategy : IBaselineStrategy
            Baseline generation strategy
        config : BaselineGeneratorConfig, optional
            Configuration for post-processing
        """
        self.strategy = strategy
        self.config = config or BaselineGeneratorConfig()

    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint]
    ) -> np.ndarray:
        """
        Generate baseline from anchor points.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        anchors : List[AnchorPoint]
            Anchor points for baseline

        Returns
        -------
        np.ndarray
            Generated and post-processed baseline
        """
        # Generate raw baseline using strategy
        baseline = self.strategy.generate(
            time, signal, anchors,
            smooth_factor=self.config.smooth_factor
        )

        # Apply constraints
        baseline = self._apply_constraints(baseline, signal)

        return baseline

    def _apply_constraints(
        self,
        baseline: np.ndarray,
        signal: np.ndarray
    ) -> np.ndarray:
        """
        Apply constraints to baseline.

        Parameters
        ----------
        baseline : np.ndarray
            Raw baseline
        signal : np.ndarray
            Original signal

        Returns
        -------
        np.ndarray
            Constrained baseline
        """
        # Prevent negative baseline (or allow small negative)
        if self.config.allow_negative:
            baseline = np.maximum(baseline, self.config.negative_threshold)
        else:
            baseline = np.maximum(baseline, 0)

        # Clip baseline to not exceed signal
        if self.config.clip_to_signal:
            baseline = np.minimum(baseline, signal)

        return baseline


class PostProcessor:
    """
    Post-processes corrected signal.

    Handles negative values and other artifacts.
    """

    def __init__(self, config: BaselineGeneratorConfig = None):
        """
        Initialize post-processor.

        Parameters
        ----------
        config : BaselineGeneratorConfig, optional
            Configuration parameters
        """
        self.config = config or BaselineGeneratorConfig()

    def process(
        self,
        corrected_signal: np.ndarray,
        original_signal: np.ndarray = None,
        baseline: np.ndarray = None
    ) -> np.ndarray:
        """
        Post-process baseline corrected signal.

        Parameters
        ----------
        corrected_signal : np.ndarray
            Baseline corrected signal
        original_signal : np.ndarray, optional
            Original signal for reference
        baseline : np.ndarray, optional
            Applied baseline for reference

        Returns
        -------
        np.ndarray
            Post-processed signal
        """
        processed = corrected_signal.copy()

        # Intelligent negative handling
        processed = self._handle_negative_regions(processed)

        return processed

    def _handle_negative_regions(self, signal: np.ndarray) -> np.ndarray:
        """
        Intelligently handle negative regions.

        Small negative regions are clipped to zero.
        Large negative regions (possible negative peaks) are preserved.
        """
        negative_threshold = self.config.negative_threshold

        # Find negative regions
        negative_mask = signal < 0
        if not np.any(negative_mask):
            return signal

        # Find contiguous negative regions
        regions = self._find_contiguous_regions(negative_mask)

        for start, end in regions:
            region_values = signal[start:end + 1]
            min_val = np.min(region_values)
            region_size = end - start + 1

            # Small and shallow negative regions - clip to zero
            if min_val > negative_threshold and region_size < 100:
                signal[start:end + 1] = np.maximum(region_values, 0)
            # Large/deep negative regions - preserve (possible negative peaks)

        return signal

    def _find_contiguous_regions(self, mask: np.ndarray) -> List[tuple]:
        """Find contiguous True regions in boolean mask."""
        regions = []
        in_region = False
        start = 0

        for i, val in enumerate(mask):
            if val and not in_region:
                start = i
                in_region = True
            elif not val and in_region:
                regions.append((start, i - 1))
                in_region = False

        if in_region:
            regions.append((start, len(mask) - 1))

        return regions


# Import List for type hint
from typing import List
