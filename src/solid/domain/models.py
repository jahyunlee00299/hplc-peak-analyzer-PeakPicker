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

from .enums import AnchorSource, PeakType, SignalQuality, BaselineMethod


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
