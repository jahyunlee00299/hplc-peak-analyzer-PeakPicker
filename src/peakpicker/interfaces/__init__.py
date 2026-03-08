"""
Interfaces Module - Abstract Contracts
======================================

This module defines abstract interfaces that high-level modules
depend on, following Dependency Inversion Principle (DIP).

All interfaces are designed with Interface Segregation Principle (ISP)
in mind - clients should not depend on interfaces they don't use.
"""

# Signal Processing Interfaces
from .signal_processing import (
    ISignalProcessor,
    IInterpolator,
    ICurveFitter,
    IIntegrator,
)

# Baseline Interfaces
from .baseline import (
    IAnchorFinder,
    IBaselineGenerator,
    IBaselineStrategy,
    ISignalPostProcessor,
    IBaselineEvaluator,
    IBaselineOptimizer,
    IBaselineCorrector,
)

# Peak Analysis Interfaces
from .peak_analysis import (
    IPeakDetector,
    IPeakBoundaryFinder,
    IAreaCalculator,
    IDeconvolutionAnalyzer,
    IPeakCenterEstimator,
    ICurveFitterStrategy,
    IDeconvolver,
    IAsymmetryCalculator,
)

# I/O Interfaces
from .io import (
    IDataReader,
    IDataExporter,
    IPlotExporter,
    IReportGenerator,
    IBatchExporter,
    IExcelExporter,
    ICSVExporter,
)

# Quantification Interfaces
from .quantification import (
    ISampleNameParser,
    IPeakMatcher,
    ICalibrationCalculator,
    IQuantifier,
    IStatisticalAnalyzer,
    IQuantificationPlotExporter,
    IQuantificationExporter,
)

__all__ = [
    # Signal Processing
    'ISignalProcessor',
    'IInterpolator',
    'ICurveFitter',
    'IIntegrator',
    # Baseline
    'IAnchorFinder',
    'IBaselineGenerator',
    'IBaselineStrategy',
    'ISignalPostProcessor',
    'IBaselineEvaluator',
    'IBaselineOptimizer',
    'IBaselineCorrector',
    # Peak Analysis
    'IPeakDetector',
    'IPeakBoundaryFinder',
    'IAreaCalculator',
    'IDeconvolutionAnalyzer',
    'IPeakCenterEstimator',
    'ICurveFitterStrategy',
    'IDeconvolver',
    'IAsymmetryCalculator',
    # I/O
    'IDataReader',
    'IDataExporter',
    'IPlotExporter',
    'IReportGenerator',
    'IBatchExporter',
    'IExcelExporter',
    'ICSVExporter',
    # Quantification
    'ISampleNameParser',
    'IPeakMatcher',
    'ICalibrationCalculator',
    'IQuantifier',
    'IStatisticalAnalyzer',
    'IQuantificationPlotExporter',
    'IQuantificationExporter',
]
