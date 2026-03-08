"""
Baseline Configuration
======================

Configuration classes for baseline correction.
Replaces magic numbers with configurable parameters.
Open/Closed Principle - extend by adding new configs.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from ..domain import BaselineMethod


@dataclass
class AnchorFinderConfig:
    """Configuration for anchor point finding."""

    # Valley detection
    valley_prominence: float = 0.01
    """Minimum prominence for valley detection (relative to signal range)."""

    valley_distance: int = 20
    """Minimum distance between valleys in data points."""

    # Local minimum detection
    local_window: Optional[int] = None
    """Window size for local minimum search. None = auto-calculate."""

    percentile: float = 2.0
    """Percentile threshold for local minimum (lower = more points)."""

    min_distance: int = 10
    """Minimum distance between any anchor points."""

    # Filtering
    outlier_removal: bool = True
    """Whether to remove outlier anchor points."""

    outlier_mad_threshold: float = 3.0
    """MAD threshold for outlier detection."""

    min_anchors: int = 3
    """Minimum number of anchors required."""


@dataclass
class BaselineGeneratorConfig:
    """Configuration for baseline generation."""

    # Spline parameters
    smooth_factor: float = 0.5
    """Smoothing factor for spline fitting."""

    spline_order: int = 3
    """Spline polynomial order (1-5)."""

    # Constraints
    allow_negative: bool = True
    """Allow slightly negative baseline values."""

    negative_threshold: float = -50.0
    """Minimum allowed baseline value."""

    clip_to_signal: bool = True
    """Clip baseline to not exceed signal."""

    # Enhanced smoothing
    enhanced_smoothing: bool = True
    """Apply additional smoothing passes."""

    smoothing_window: int = 21
    """Window size for post-smoothing."""


@dataclass
class BaselineStrategyConfig:
    """Configuration for specific baseline strategies."""

    method: BaselineMethod = BaselineMethod.WEIGHTED_SPLINE
    """Default baseline method."""

    # Weighted spline specific
    confidence_weight: float = 0.5
    """How much confidence affects weighting (0-1)."""

    # Robust fit specific
    mad_threshold: float = 3.0
    """MAD threshold for robust outlier removal."""

    # Adaptive connect specific
    curve_valleys: bool = True
    """Use curved connection between valleys."""

    mid_point_percentile: float = 5.0
    """Percentile for mid-point adjustment."""


@dataclass
class BaselineCorrectorConfig:
    """Complete configuration for baseline correction."""

    anchor_config: AnchorFinderConfig = field(default_factory=AnchorFinderConfig)
    generator_config: BaselineGeneratorConfig = field(default_factory=BaselineGeneratorConfig)
    strategy_config: BaselineStrategyConfig = field(default_factory=BaselineStrategyConfig)

    # Post-processing
    clip_negative_signal: bool = True
    """Clip negative values in corrected signal."""

    negative_clip_threshold: float = -50.0
    """Threshold for intelligent negative clipping."""

    # Optimization
    auto_optimize: bool = False
    """Automatically try multiple parameter combinations."""

    optimization_methods: List[BaselineMethod] = field(
        default_factory=lambda: [
            BaselineMethod.WEIGHTED_SPLINE,
            BaselineMethod.ROBUST_FIT,
        ]
    )


@dataclass
class LinearPeakBaselineConfig:
    """Configuration for linear baseline in peak regions."""

    enabled: bool = True
    """Apply flat baseline in peak regions."""

    height_threshold: float = 0.05
    """Peak height threshold (fraction of peak height) for boundaries."""

    expansion_margin: int = 50
    """Additional points to expand peak boundaries."""

    slope_threshold_factor: float = 0.01
    """Maximum allowed slope relative to signal range."""

    max_rt_expansion: float = 5.0
    """Maximum RT expansion in minutes."""

    rt_expansion_step: float = 0.1
    """RT expansion step size in minutes."""


# Preset configurations for common use cases
class BaselinePresets:
    """Preset configurations for common scenarios."""

    @staticmethod
    def default() -> BaselineCorrectorConfig:
        """Default configuration for general use."""
        return BaselineCorrectorConfig()

    @staticmethod
    def sensitive() -> BaselineCorrectorConfig:
        """Configuration for low-signal samples."""
        config = BaselineCorrectorConfig()
        config.anchor_config.valley_prominence = 0.005
        config.anchor_config.percentile = 5.0
        config.generator_config.smooth_factor = 0.3
        return config

    @staticmethod
    def noisy() -> BaselineCorrectorConfig:
        """Configuration for noisy signals."""
        config = BaselineCorrectorConfig()
        config.anchor_config.valley_prominence = 0.02
        config.anchor_config.min_distance = 20
        config.generator_config.smooth_factor = 1.0
        config.generator_config.enhanced_smoothing = True
        return config

    @staticmethod
    def flat_baseline() -> BaselineCorrectorConfig:
        """Configuration for samples with flat baselines."""
        config = BaselineCorrectorConfig()
        config.strategy_config.method = BaselineMethod.LINEAR
        config.generator_config.smooth_factor = 0.1
        return config
