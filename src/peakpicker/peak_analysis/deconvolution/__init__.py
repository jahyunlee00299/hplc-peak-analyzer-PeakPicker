"""
Peak Deconvolution
==================

SOLID-compliant peak deconvolution implementations.
"""

from .analyzer import ShoulderDeconvolutionAnalyzer, PeakCenterEstimator
from .gaussian_fitter import GaussianFitterStrategy, PeakDeconvolver, gaussian, multi_gaussian
from .emg_fitter import EmgFitter, emg, multi_emg

__all__ = [
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
