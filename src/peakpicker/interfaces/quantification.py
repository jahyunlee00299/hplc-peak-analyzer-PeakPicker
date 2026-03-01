"""
Quantification Interfaces
==========================

Abstract interfaces for quantification, statistical analysis, and visualization.
Following Interface Segregation Principle (ISP).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from ..domain.models import (
    Peak,
    BatchResult,
    CompoundDefinition,
    SampleConditions,
    QuantifiedPeak,
    QuantificationResult,
    StatisticalAnalysisResult,
)


class ISampleNameParser(ABC):
    """Parses experimental conditions from sample names."""

    @abstractmethod
    def parse(self, sample_name: str) -> SampleConditions:
        pass


class IPeakMatcher(ABC):
    """Matches detected peaks to known compounds by retention time."""

    @abstractmethod
    def match(
        self, peaks: List[Peak], compounds: List[CompoundDefinition]
    ) -> Dict[str, Optional[Peak]]:
        """Returns {compound_name: matched Peak or None}."""
        pass


class ICalibrationCalculator(ABC):
    """Calculates concentration from peak area using calibration curve."""

    @abstractmethod
    def calculate_concentration(
        self, area: float, compound: CompoundDefinition, dilution_factor: float
    ) -> Tuple[float, float]:
        """Returns (concentration_diluted, concentration_original)."""
        pass


class IQuantifier(ABC):
    """Orchestrates batch quantification: parsing + matching + calibration."""

    @abstractmethod
    def quantify(
        self,
        batch_result: BatchResult,
        compounds: List[CompoundDefinition],
        dilution_factor: float,
    ) -> QuantificationResult:
        pass


class IStatisticalAnalyzer(ABC):
    """Performs statistical analysis (ANOVA + post-hoc) on quantification results."""

    @abstractmethod
    def analyze(
        self,
        quantification_result: QuantificationResult,
        group_variable: str,
        alpha: float,
    ) -> StatisticalAnalysisResult:
        pass


class IQuantificationPlotExporter(ABC):
    """Exports quantification visualizations."""

    @abstractmethod
    def export_bar_chart(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_path: Path,
        compound_name: str,
        enzyme: str,
        time_h: str,
    ) -> Path:
        pass

    @abstractmethod
    def export_time_course(
        self,
        quant_result: QuantificationResult,
        output_path: Path,
        compound_name: str,
    ) -> Path:
        pass

    @abstractmethod
    def export_comparison_chart(
        self,
        quant_result: QuantificationResult,
        output_path: Path,
        compound_name: str,
        time_h: str,
    ) -> Path:
        pass


class IQuantificationExporter(ABC):
    """Exports quantification results to data files."""

    @abstractmethod
    def export(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_path: Path,
    ) -> Path:
        pass
