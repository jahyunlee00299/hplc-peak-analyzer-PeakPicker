"""
Peak Analysis Module
====================

SOLID-compliant peak detection and analysis.
"""

from .detectors import ProminencePeakDetector, SimplePeakBoundaryFinder, TwoPassPeakDetector

from .deconvolution import (
    ShoulderDeconvolutionAnalyzer,
    PeakCenterEstimator,
    GaussianFitterStrategy,
    PeakDeconvolver,
    gaussian,
    multi_gaussian,
    EmgFitter,
    emg,
    multi_emg,
)

__all__ = [
    # Detectors
    'ProminencePeakDetector',
    'SimplePeakBoundaryFinder',
    'TwoPassPeakDetector',
    # Deconvolution
    'ShoulderDeconvolutionAnalyzer',
    'PeakCenterEstimator',
    'GaussianFitterStrategy',
    'PeakDeconvolver',
    'gaussian',
    'multi_gaussian',
    'EmgFitter',
    'emg',
    'multi_emg',
]
