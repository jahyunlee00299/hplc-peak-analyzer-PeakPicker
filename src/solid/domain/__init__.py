"""
Domain Module - Core Business Models
====================================

This module contains pure domain models that are independent
of any infrastructure or framework concerns.
"""

from .enums import (
    AnchorSource,
    BaselineMethod,
    PeakType,
    DeconvolutionMethod,
    ExportFormat,
    SignalQuality,
)

from .models import (
    AnchorPoint,
    Peak,
    DeconvolvedPeak,
    BaselineResult,
    DeconvolutionResult,
    ChromatogramData,
    AnalysisResult,
    BatchResult,
)

__all__ = [
    # Enums
    'AnchorSource',
    'BaselineMethod',
    'PeakType',
    'DeconvolutionMethod',
    'ExportFormat',
    'SignalQuality',
    # Models
    'AnchorPoint',
    'Peak',
    'DeconvolvedPeak',
    'BaselineResult',
    'DeconvolutionResult',
    'ChromatogramData',
    'AnalysisResult',
    'BatchResult',
]
