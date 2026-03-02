"""
Peak Detectors
==============

Implementations for peak detection.
"""

from .peak_detector import ProminencePeakDetector, SimplePeakBoundaryFinder
from .two_pass_detector import TwoPassPeakDetector

__all__ = ['ProminencePeakDetector', 'SimplePeakBoundaryFinder', 'TwoPassPeakDetector']
