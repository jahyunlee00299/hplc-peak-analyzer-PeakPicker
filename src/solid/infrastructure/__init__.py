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

from .file_readers import ChemstationReader, CSVReader

from .exporters import (
    ExcelExporter,
    CSVExporter,
    BatchExcelExporter,
    ChromatogramPlotExporter,
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
    # Exporters
    'ExcelExporter',
    'CSVExporter',
    'BatchExcelExporter',
    'ChromatogramPlotExporter',
]
