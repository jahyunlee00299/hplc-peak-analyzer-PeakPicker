"""
Peak Detection Configuration
============================

Configuration classes for peak detection and analysis.
Replaces magic numbers with configurable parameters.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from ..domain import DeconvolutionMethod


@dataclass
class PeakDetectionConfig:
    """Configuration for peak detection."""

    # Prominence-based detection
    min_prominence_factor: float = 0.005
    """Minimum prominence as fraction of signal range."""

    # Height-based filtering
    height_multiplier: float = 3.0
    """Height threshold as multiple of noise level."""

    noise_percentile: float = 25.0
    """Percentile for noise level estimation."""

    # Width constraints
    min_width: int = 3
    """Minimum peak width in data points."""

    max_width: int = 500
    """Maximum peak width in data points."""

    # Distance constraints
    min_distance: int = 5
    """Minimum distance between peaks in data points."""

    # Boundary detection
    boundary_threshold: float = 0.01
    """Threshold for peak boundaries (fraction of peak height)."""


@dataclass
class AsymmetryConfig:
    """Configuration for asymmetry calculation."""

    measurement_height: float = 0.1
    """Height fraction for asymmetry measurement (0.1 = 10%)."""

    min_asymmetry: float = 1.0
    """Minimum valid asymmetry value."""

    max_asymmetry: float = 10.0
    """Maximum valid asymmetry value (clip outliers)."""


@dataclass
class DeconvolutionConfig:
    """Configuration for peak deconvolution."""

    # Decision criteria
    min_asymmetry_threshold: float = 1.2
    """Minimum asymmetry to trigger deconvolution."""

    min_shoulder_ratio: float = 0.1
    """Minimum height ratio for shoulder detection."""

    min_inflection_points: int = 3
    """Minimum inflection points to suggest deconvolution."""

    # Fitting parameters
    max_components: int = 4
    """Maximum number of peak components to fit."""

    fit_tolerance: float = 0.85
    """Minimum R² to accept fit."""

    max_iterations: int = 10000
    """Maximum iterations for curve fitting."""

    # Derivative analysis
    smooth_window: int = 5
    """Window size for derivative smoothing."""

    shoulder_prominence: float = 0.1
    """Prominence threshold for shoulder detection."""


@dataclass
class GaussianFitConfig:
    """Configuration for Gaussian fitting."""

    method: DeconvolutionMethod = DeconvolutionMethod.MULTI_GAUSSIAN
    """Fitting method to use."""

    # Amplitude bounds
    amplitude_lower_factor: float = 0.1
    """Lower bound as fraction of estimated amplitude."""

    amplitude_upper_factor: float = 2.0
    """Upper bound as fraction of estimated amplitude."""

    # Center bounds
    center_tolerance_sigmas: float = 3.0
    """Center bounds as multiple of sigma."""

    # Width bounds
    sigma_lower_factor: float = 0.1
    """Lower bound as fraction of estimated sigma."""

    sigma_upper_factor: float = 5.0
    """Upper bound as fraction of estimated sigma."""


@dataclass
class AreaCalculationConfig:
    """Configuration for area calculation."""

    method: str = "trapezoid"
    """Integration method: 'trapezoid', 'simpson', or 'sum'."""

    baseline_subtraction: bool = True
    """Subtract baseline from area calculation."""

    extend_to_baseline: bool = True
    """Extend integration to where peak meets baseline."""


@dataclass
class PeakAnalysisConfig:
    """Complete configuration for peak analysis."""

    detection: PeakDetectionConfig = field(default_factory=PeakDetectionConfig)
    asymmetry: AsymmetryConfig = field(default_factory=AsymmetryConfig)
    deconvolution: DeconvolutionConfig = field(default_factory=DeconvolutionConfig)
    gaussian_fit: GaussianFitConfig = field(default_factory=GaussianFitConfig)
    area: AreaCalculationConfig = field(default_factory=AreaCalculationConfig)


# Preset configurations
class PeakAnalysisPresets:
    """Preset configurations for common scenarios."""

    @staticmethod
    def default() -> PeakAnalysisConfig:
        """Default configuration."""
        return PeakAnalysisConfig()

    @staticmethod
    def high_resolution() -> PeakAnalysisConfig:
        """Configuration for high-resolution separations."""
        config = PeakAnalysisConfig()
        config.detection.min_prominence_factor = 0.002
        config.detection.min_distance = 3
        config.deconvolution.min_asymmetry_threshold = 1.1
        return config

    @staticmethod
    def overlapping_peaks() -> PeakAnalysisConfig:
        """Configuration for samples with overlapping peaks."""
        config = PeakAnalysisConfig()
        config.deconvolution.max_components = 6
        config.deconvolution.min_asymmetry_threshold = 1.15
        config.deconvolution.fit_tolerance = 0.90
        return config

    @staticmethod
    def quantitative() -> PeakAnalysisConfig:
        """Configuration optimized for quantitative analysis."""
        config = PeakAnalysisConfig()
        config.area.method = "trapezoid"
        config.area.baseline_subtraction = True
        config.detection.boundary_threshold = 0.005
        return config
