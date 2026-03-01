"""
HPLC Peak Analyzer
===================

A clean-architecture HPLC Peak Analyzer following SOLID principles.

This package follows:
- Single Responsibility Principle (SRP): Each class has one job
- Open/Closed Principle (OCP): Extend via new classes, not modification
- Liskov Substitution Principle (LSP): Interfaces are interchangeable
- Interface Segregation Principle (ISP): Small, focused interfaces
- Dependency Inversion Principle (DIP): Depend on abstractions

Package Structure
-----------------
- domain/: Core business models and enums
- interfaces/: Abstract interfaces (contracts)
- config/: Configuration classes (replaces magic numbers)
- baseline/: Baseline correction components
- peak_analysis/: Peak detection and deconvolution
- infrastructure/: External library adapters and I/O
- application/: High-level workflows

Quick Start
-----------
>>> from src.peakpicker.application import create_default_workflow
>>> workflow = create_default_workflow(output_dir="./results")
>>> result = workflow.analyze_file("sample.ch")
>>> print(f"Found {len(result.peaks)} peaks")

Using the Builder
-----------------
>>> from src.peakpicker.application import WorkflowBuilder
>>> workflow = (WorkflowBuilder()
...     .with_chemstation_reader()
...     .with_default_baseline()
...     .with_default_peak_detector()
...     .with_excel_exporter()
...     .build())

Custom Configuration
--------------------
>>> from src.peakpicker.config import BaselineCorrectorConfig, BaselinePresets
>>> config = BaselinePresets.noisy()  # For noisy signals
>>> workflow = (WorkflowBuilder()
...     .with_default_baseline(config)
...     .build())
"""

__version__ = "2.0.0"
__author__ = "PeakPicker Project"

# Domain exports
from .domain import (
    # Enums
    AnchorSource,
    BaselineMethod,
    PeakType,
    DeconvolutionMethod,
    ExportFormat,
    SignalQuality,
    VisualizationMode,
    StatisticalTest,
    # Models
    AnchorPoint,
    Peak,
    DeconvolvedPeak,
    BaselineResult,
    DeconvolutionResult,
    ChromatogramData,
    AnalysisResult,
    BatchResult,
    CompoundDefinition,
    SampleConditions,
    QuantifiedPeak,
    QuantificationResult,
    TukeyHSDComparison,
    StatisticalTestResult,
    StatisticalAnalysisResult,
)

# Configuration exports
from .config import (
    AnchorFinderConfig,
    BaselineGeneratorConfig,
    BaselineStrategyConfig,
    BaselineCorrectorConfig,
    BaselinePresets,
    PeakDetectionConfig,
    DeconvolutionConfig,
    PeakAnalysisConfig,
    PeakAnalysisPresets,
    QuantificationConfig,
    QuantificationPresets,
)

# Application exports
from .application import (
    AnalysisWorkflow,
    WorkflowBuilder,
    create_default_workflow,
    QuantificationWorkflow,
    QuantificationWorkflowBuilder,
    create_quantification_workflow,
)

__all__ = [
    # Version
    '__version__',
    # Enums
    'AnchorSource',
    'BaselineMethod',
    'PeakType',
    'DeconvolutionMethod',
    'ExportFormat',
    'SignalQuality',
    'VisualizationMode',
    'StatisticalTest',
    # Models
    'AnchorPoint',
    'Peak',
    'DeconvolvedPeak',
    'BaselineResult',
    'DeconvolutionResult',
    'ChromatogramData',
    'AnalysisResult',
    'BatchResult',
    'CompoundDefinition',
    'SampleConditions',
    'QuantifiedPeak',
    'QuantificationResult',
    'TukeyHSDComparison',
    'StatisticalTestResult',
    'StatisticalAnalysisResult',
    # Config
    'AnchorFinderConfig',
    'BaselineGeneratorConfig',
    'BaselineStrategyConfig',
    'BaselineCorrectorConfig',
    'BaselinePresets',
    'PeakDetectionConfig',
    'DeconvolutionConfig',
    'PeakAnalysisConfig',
    'PeakAnalysisPresets',
    'QuantificationConfig',
    'QuantificationPresets',
    # Application
    'AnalysisWorkflow',
    'WorkflowBuilder',
    'create_default_workflow',
    'QuantificationWorkflow',
    'QuantificationWorkflowBuilder',
    'create_quantification_workflow',
]
