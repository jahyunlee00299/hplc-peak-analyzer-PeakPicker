"""
Domain Models for HPLC Peak Analyzer
====================================

Core data classes representing domain concepts.
These models are independent of infrastructure concerns.
Following Single Responsibility Principle (SRP).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np

from .enums import AnchorSource, PeakType, SignalQuality, BaselineMethod, VisualizationMode


@dataclass
class AnchorPoint:
    """
    Represents a baseline anchor point.

    Unified model replacing BaselinePoint and BaselineAnchor.
    Supports Liskov Substitution - all anchor implementations
    can be used interchangeably.
    """
    index: int
    time: float
    value: float
    confidence: float  # 0.0 to 1.0
    source: AnchorSource

    def __post_init__(self):
        """Validate anchor point data."""
        if not 0.0 <= self.confidence <= 1.0:
            self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class Peak:
    """
    Represents a detected chromatographic peak.

    Single unified Peak model for the entire application.
    """
    # Core identification
    index: int              # Index of peak maximum
    rt: float               # Retention time at peak maximum

    # Boundaries
    index_start: int        # Start index
    index_end: int          # End index
    rt_start: float         # Start retention time
    rt_end: float           # End retention time

    # Measurements
    height: float           # Peak height (baseline corrected)
    area: float             # Integrated area
    width: float            # Peak width (FWHM or base width)

    # Classification
    peak_type: PeakType = PeakType.MAIN

    # Optional metadata
    asymmetry: float = 1.0  # Asymmetry factor
    resolution: float = 0.0  # Resolution from previous peak
    plates: int = 0         # Theoretical plates

    @property
    def area_percent(self) -> float:
        """Calculate area percentage (needs to be set externally)."""
        return getattr(self, '_area_percent', 0.0)

    @area_percent.setter
    def area_percent(self, value: float):
        self._area_percent = value


@dataclass
class DeconvolvedPeak:
    """
    Represents a single deconvolved peak component.

    Result of peak deconvolution analysis.
    """
    retention_time: float
    amplitude: float
    sigma: float            # Width parameter
    area: float
    area_percent: float
    fit_quality: float      # R² for this component
    is_shoulder: bool
    asymmetry: float
    start_rt: float
    end_rt: float


@dataclass
class BaselineResult:
    """
    Result of baseline correction operation.

    Contains all information needed to reproduce and validate
    the baseline correction.
    """
    baseline: np.ndarray
    anchors: List[AnchorPoint]
    method: BaselineMethod
    quality_score: float    # Overall quality metric
    negative_ratio: float   # Percentage of negative values after correction
    smoothness: float       # Baseline smoothness metric
    params: Dict[str, Any] = field(default_factory=dict)

    @property
    def quality(self) -> SignalQuality:
        """Convert quality score to SignalQuality enum."""
        if self.quality_score > 0.99:
            return SignalQuality.EXCELLENT
        elif self.quality_score > 0.95:
            return SignalQuality.GOOD
        elif self.quality_score > 0.90:
            return SignalQuality.ACCEPTABLE
        elif self.quality_score > 0.80:
            return SignalQuality.POOR
        return SignalQuality.FAILED


@dataclass
class DeconvolutionResult:
    """
    Complete result of peak deconvolution analysis.
    """
    original_peak_rt: float
    n_components: int
    components: List[DeconvolvedPeak]
    total_area: float
    fit_quality: float      # Overall R²
    rmse: float             # Root mean square error
    method: str
    success: bool
    message: str


@dataclass
class ChromatogramData:
    """
    Raw chromatogram data container.

    Encapsulates time and intensity arrays with metadata.
    """
    time: np.ndarray
    intensity: np.ndarray
    sample_name: str = "Unknown"
    detector_type: str = "Signal"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate data arrays."""
        if len(self.time) != len(self.intensity):
            raise ValueError("Time and intensity arrays must have same length")

    @property
    def num_points(self) -> int:
        return len(self.time)

    @property
    def time_range(self) -> tuple:
        return (float(self.time[0]), float(self.time[-1]))

    @property
    def intensity_range(self) -> tuple:
        return (float(np.min(self.intensity)), float(np.max(self.intensity)))


@dataclass
class AnalysisResult:
    """
    Complete analysis result for a chromatogram.

    Aggregates all analysis components for export.
    """
    chromatogram: ChromatogramData
    baseline_result: Optional[BaselineResult]
    peaks: List[Peak]
    deconvolution_results: List[DeconvolutionResult] = field(default_factory=list)

    @property
    def total_area(self) -> float:
        return sum(p.area for p in self.peaks)

    @property
    def num_peaks(self) -> int:
        return len(self.peaks)


@dataclass
class BatchResult:
    """
    Results from batch processing multiple samples.
    """
    results: List[AnalysisResult]

    @property
    def sample_names(self) -> List[str]:
        return [r.chromatogram.sample_name for r in self.results]

    @property
    def total_samples(self) -> int:
        return len(self.results)


# ===== Quantification Models =====

@dataclass
class CompoundDefinition:
    """Target compound for RT-based peak matching with calibration parameters."""
    name: str
    rt_window_start: float
    rt_window_end: float
    calibration_intercept: float  # y0 in Area = y0 + a * C
    calibration_slope: float      # a in Area = y0 + a * C
    unit: str = "g/L"


@dataclass
class SampleConditions:
    """Experimental conditions extracted from sample name."""
    sample_name: str
    cofactor_dose: str = ""
    enzyme: str = ""
    replicate: str = ""
    time_h: str = ""
    is_negative_control: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuantifiedPeak:
    """A peak matched to a compound and quantified."""
    peak: Peak
    compound: CompoundDefinition
    sample_conditions: SampleConditions
    area: float
    concentration_diluted: float
    concentration_original: float
    dilution_factor: float


@dataclass
class QuantificationResult:
    """Complete quantification result for a batch of samples."""
    quantified_peaks: List['QuantifiedPeak']
    compounds: List[CompoundDefinition]
    dilution_factor: float

    @property
    def compound_names(self) -> List[str]:
        return list(dict.fromkeys(qp.compound.name for qp in self.quantified_peaks))

    @property
    def sample_names(self) -> List[str]:
        return list(dict.fromkeys(qp.sample_conditions.sample_name for qp in self.quantified_peaks))

    def get_by_compound(self, compound_name: str) -> List['QuantifiedPeak']:
        return [qp for qp in self.quantified_peaks if qp.compound.name == compound_name]

    def get_by_conditions(
        self,
        compound_name: str = None,
        enzyme: str = None,
        time_h: str = None,
        cofactor_dose: str = None,
    ) -> List['QuantifiedPeak']:
        result = self.quantified_peaks
        if compound_name:
            result = [qp for qp in result if qp.compound.name == compound_name]
        if enzyme:
            result = [qp for qp in result if qp.sample_conditions.enzyme == enzyme]
        if time_h:
            result = [qp for qp in result if qp.sample_conditions.time_h == time_h]
        if cofactor_dose:
            result = [qp for qp in result if qp.sample_conditions.cofactor_dose == cofactor_dose]
        return result

    def get_nc_mean(self, compound_name: str) -> float:
        """Return mean concentration of NC samples for a compound.

        Returns 0.0 if NC sample exists but no peak was detected
        (below detection limit).
        """
        nc_peaks = [qp for qp in self.quantified_peaks
                    if qp.compound.name == compound_name
                    and qp.sample_conditions.is_negative_control]
        if not nc_peaks:
            return 0.0
        import numpy as np
        return float(np.mean([qp.concentration_original for qp in nc_peaks]))


@dataclass
class TukeyHSDComparison:
    """Single pairwise comparison from Tukey HSD test."""
    group1_name: str
    group2_name: str
    mean_difference: float
    mean_group1: float
    mean_group2: float
    q_statistic: float
    p_adjusted: float
    significance: str  # "***", "**", "*", "ns"


@dataclass
class StatisticalTestResult:
    """Statistical analysis result for one compound/condition."""
    compound_name: str
    enzyme: str
    time_h: str
    group_variable: str
    anova_f_statistic: float
    anova_p_value: float
    anova_significance: str
    pairwise_comparisons: List[TukeyHSDComparison]
    group_means: Dict[str, float]
    group_stds: Dict[str, float]
    group_ns: Dict[str, int]


@dataclass
class StatisticalAnalysisResult:
    """Collection of all statistical test results."""
    test_results: List[StatisticalTestResult]
    alpha: float = 0.05

    def get_result(
        self, compound_name: str, enzyme: str, time_h: str
    ) -> Optional[StatisticalTestResult]:
        for r in self.test_results:
            if (r.compound_name == compound_name and
                    r.enzyme == enzyme and r.time_h == time_h):
                return r
        return None

    def get_significant_pairs(
        self, compound_name: str, enzyme: str, time_h: str
    ) -> List[TukeyHSDComparison]:
        result = self.get_result(compound_name, enzyme, time_h)
        if result is None:
            return []
        return [c for c in result.pairwise_comparisons if c.significance != "ns"]
