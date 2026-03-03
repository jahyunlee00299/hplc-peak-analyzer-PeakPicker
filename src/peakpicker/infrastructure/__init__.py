"""
Infrastructure Module
=====================

Concrete implementations of interfaces.
Contains adapters for external libraries and I/O operations.
"""

from .signal_processing import (
    ScipySignalProcessor,
    ScipyInterpolator,
    ScipyCurveFitter,
    ScipyIntegrator,
    create_scipy_processors,
)

from .file_readers import ChemstationReader, CSVReader, RainbowReader, RainbowChemstationReader, AutoReader, DFolderScanner

from .exporters import (
    ExcelExporter,
    CSVExporter,
    BatchExcelExporter,
    ChromatogramPlotExporter,
)

from .quantification import (
    RegexSampleNameParser,
    RTWindowPeakMatcher,
    LinearCalibrationCalculator,
    BatchQuantifier,
    ScipyStatisticalAnalyzer,
    QuantificationPlotExporter,
    QuantificationExcelExporter,
)

__all__ = [
    # Signal Processing
    'ScipySignalProcessor',
    'ScipyInterpolator',
    'ScipyCurveFitter',
    'ScipyIntegrator',
    'create_scipy_processors',
    # File Readers
    'ChemstationReader',
    'CSVReader',
    'RainbowReader',
    'RainbowChemstationReader',
    'AutoReader',
    'DFolderScanner',
    # Exporters
    'ExcelExporter',
    'CSVExporter',
    'BatchExcelExporter',
    'ChromatogramPlotExporter',
    # Quantification
    'RegexSampleNameParser',
    'RTWindowPeakMatcher',
    'LinearCalibrationCalculator',
    'BatchQuantifier',
    'ScipyStatisticalAnalyzer',
    'QuantificationPlotExporter',
    'QuantificationExcelExporter',
]
