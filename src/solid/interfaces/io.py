"""
Input/Output Interfaces
=======================

Abstract interfaces for data input and output operations.
Following Interface Segregation Principle (ISP) -
separate interfaces for different export types.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from ..domain import (
    ChromatogramData,
    Peak,
    AnalysisResult,
    BatchResult,
)


class IDataReader(ABC):
    """
    Interface for reading chromatogram data.

    Single Responsibility: Only reads data files.
    """

    @abstractmethod
    def read(self, file_path: Path) -> ChromatogramData:
        """
        Read chromatogram data from file.

        Parameters
        ----------
        file_path : Path
            Path to data file

        Returns
        -------
        ChromatogramData
            Loaded chromatogram data
        """
        pass

    @abstractmethod
    def can_read(self, file_path: Path) -> bool:
        """
        Check if this reader can handle the file.

        Parameters
        ----------
        file_path : Path
            Path to check

        Returns
        -------
        bool
            True if file can be read
        """
        pass


class IDataExporter(ABC):
    """
    Interface for exporting analysis data.

    Interface Segregation: Separate from plot exporter.
    """

    @abstractmethod
    def export(
        self,
        result: AnalysisResult,
        output_path: Path,
        **options
    ) -> Path:
        """
        Export analysis result to file.

        Parameters
        ----------
        result : AnalysisResult
            Analysis result to export
        output_path : Path
            Output file path
        **options
            Format-specific options

        Returns
        -------
        Path
            Path to created file
        """
        pass


class IPlotExporter(ABC):
    """
    Interface for exporting plots/visualizations.

    Interface Segregation: Separate from data exporter.
    """

    @abstractmethod
    def export_chromatogram(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        peaks: List[Peak],
        output_path: Path,
        title: str = None,
        **options
    ) -> Path:
        """
        Export chromatogram plot.

        Parameters
        ----------
        time : np.ndarray
            Time array
        intensity : np.ndarray
            Intensity array
        peaks : List[Peak]
            Detected peaks to annotate
        output_path : Path
            Output file path
        title : str, optional
            Plot title
        **options
            Plot options (figsize, dpi, etc.)

        Returns
        -------
        Path
            Path to created file
        """
        pass


class IReportGenerator(ABC):
    """
    Interface for generating analysis reports.

    Interface Segregation: Separate from raw data export.
    """

    @abstractmethod
    def generate(
        self,
        results: List[AnalysisResult],
        output_path: Path,
        template: str = None
    ) -> Path:
        """
        Generate analysis report.

        Parameters
        ----------
        results : List[AnalysisResult]
            Analysis results to include
        output_path : Path
            Output file path
        template : str, optional
            Report template name

        Returns
        -------
        Path
            Path to created report
        """
        pass


class IBatchExporter(ABC):
    """
    Interface for batch export operations.

    Handles exporting multiple samples at once.
    """

    @abstractmethod
    def export_batch(
        self,
        batch_result: BatchResult,
        output_dir: Path,
        filename_prefix: str = "batch"
    ) -> List[Path]:
        """
        Export batch results.

        Parameters
        ----------
        batch_result : BatchResult
            Batch processing results
        output_dir : Path
            Output directory
        filename_prefix : str
            Prefix for output files

        Returns
        -------
        List[Path]
            Paths to created files
        """
        pass


class IExcelExporter(IDataExporter):
    """
    Specialized interface for Excel export.

    Extends IDataExporter with Excel-specific methods.
    """

    @abstractmethod
    def export_with_metadata(
        self,
        result: AnalysisResult,
        output_path: Path,
        metadata: Dict[str, Any] = None
    ) -> Path:
        """
        Export with additional metadata sheet.

        Parameters
        ----------
        result : AnalysisResult
            Analysis result
        output_path : Path
            Output path
        metadata : Dict[str, Any], optional
            Additional metadata

        Returns
        -------
        Path
            Path to created Excel file
        """
        pass


class ICSVExporter(IDataExporter):
    """
    Specialized interface for CSV export.
    """

    @abstractmethod
    def export_peaks_only(
        self,
        peaks: List[Peak],
        output_path: Path,
        sample_name: str = None
    ) -> Path:
        """
        Export only peak data to CSV.

        Parameters
        ----------
        peaks : List[Peak]
            Peaks to export
        output_path : Path
            Output path
        sample_name : str, optional
            Sample name to include

        Returns
        -------
        Path
            Path to created CSV file
        """
        pass
