"""
Peak Deconvolution
==================

SOLID-compliant peak deconvolution implementations.

Architecture:
- SRP: Each class has a single responsibility
- OCP: FitterStrategyFactory allows adding new strategies
- LSP: All implementations can substitute their interfaces
- ISP: Fine-grained interfaces for each concern
- DIP: All classes depend on interfaces, not implementations

Usage:
    from src.solid.peak_analysis.deconvolution import (
        create_deconvolver,  # Factory function for easy setup
        PeakDeconvolver,     # Main orchestrator
        GaussianFitterStrategy,  # Gaussian fitting strategy
        FitterStrategyFactory,   # Strategy factory for OCP
    )

    # Easy setup with factory function
    deconvolver = create_deconvolver(signal_processor, curve_fitter)
    result = deconvolver.deconvolve(time, signal, start_idx, end_idx)

    # Or manual setup for more control (DIP)
    analyzer = ShoulderDeconvolutionAnalyzer(signal_processor)
    estimator = PeakCenterEstimator(signal_processor)
    fitter = GaussianFitterStrategy(curve_fitter)
    deconvolver = PeakDeconvolver(analyzer, estimator, fitter)
"""

# Analyzer components (SRP)
from .analyzer import (
    ShoulderDeconvolutionAnalyzer,
    PeakCenterEstimator,
    AsymmetryCalculator,
    ShoulderDetector,
    InflectionPointCounter,
)

# Fitter components (SRP, OCP, LSP)
from .gaussian_fitter import (
    GaussianFitterStrategy,
    PeakDeconvolver,
    FitterStrategyFactory,
    DeconvolutionError,
    gaussian,
    multi_gaussian,
    create_deconvolver,
)

__all__ = [
    # Analyzers
    'ShoulderDeconvolutionAnalyzer',
    'PeakCenterEstimator',
    'AsymmetryCalculator',
    'ShoulderDetector',
    'InflectionPointCounter',
    # Fitters
    'GaussianFitterStrategy',
    'PeakDeconvolver',
    'FitterStrategyFactory',
    'DeconvolutionError',
    # Functions
    'gaussian',
    'multi_gaussian',
    'create_deconvolver',
]
