"""
Peak Analysis Module
====================

SOLID-compliant peak detection and analysis.
"""

from .detectors import ProminencePeakDetector, SimplePeakBoundaryFinder

from .deconvolution import (
    ShoulderDeconvolutionAnalyzer,
    PeakCenterEstimator,
    GaussianFitterStrategy,
    PeakDeconvolver,
    gaussian,
    multi_gaussian,
)

__all__ = [
    # Detectors
    'ProminencePeakDetector',
    'SimplePeakBoundaryFinder',
    # Deconvolution
    'ShoulderDeconvolutionAnalyzer',
    'PeakCenterEstimator',
    'GaussianFitterStrategy',
    'PeakDeconvolver',
    'gaussian',
    'multi_gaussian',
]
