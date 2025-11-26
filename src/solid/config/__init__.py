"""
Configuration Module
====================

Centralized configuration management for HPLC Peak Analyzer.
Replaces magic numbers throughout the codebase with
configurable, documented parameters.
"""

from .baseline_config import (
    AnchorFinderConfig,
    BaselineGeneratorConfig,
    BaselineStrategyConfig,
    BaselineCorrectorConfig,
    LinearPeakBaselineConfig,
    BaselinePresets,
)

from .peak_detection_config import (
    PeakDetectionConfig,
    AsymmetryConfig,
    DeconvolutionConfig,
    GaussianFitConfig,
    AreaCalculationConfig,
    PeakAnalysisConfig,
    PeakAnalysisPresets,
)

__all__ = [
    # Baseline configs
    'AnchorFinderConfig',
    'BaselineGeneratorConfig',
    'BaselineStrategyConfig',
    'BaselineCorrectorConfig',
    'LinearPeakBaselineConfig',
    'BaselinePresets',
    # Peak analysis configs
    'PeakDetectionConfig',
    'AsymmetryConfig',
    'DeconvolutionConfig',
    'GaussianFitConfig',
    'AreaCalculationConfig',
    'PeakAnalysisConfig',
    'PeakAnalysisPresets',
]
