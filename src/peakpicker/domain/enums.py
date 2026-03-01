"""
Domain Enums for HPLC Peak Analyzer
===================================

Defines enumeration types used throughout the application.
Following SOLID principles - these are pure domain concepts.
"""

from enum import Enum, auto


class AnchorSource(Enum):
    """Source type for baseline anchor points."""
    VALLEY = auto()      # Detected as valley between peaks
    LOCAL_MIN = auto()   # Local minimum in signal
    BOUNDARY = auto()    # Start/end boundary point
    USER_DEFINED = auto()  # Manually specified by user


class BaselineMethod(Enum):
    """Available baseline generation methods."""
    WEIGHTED_SPLINE = "weighted_spline"
    ADAPTIVE_CONNECT = "adaptive_connect"
    ROBUST_FIT = "robust_fit"
    LINEAR = "linear"


class PeakType(Enum):
    """Classification of detected peaks."""
    MAIN = auto()        # Primary peak
    SHOULDER = auto()    # Shoulder on main peak
    IMPURITY = auto()    # Small impurity peak
    SOLVENT = auto()     # Solvent front peak
    UNKNOWN = auto()     # Unclassified


class DeconvolutionMethod(Enum):
    """Methods for peak deconvolution."""
    GAUSSIAN = "gaussian"
    MULTI_GAUSSIAN = "multi_gaussian"
    VOIGT = "voigt"
    EMG = "emg"  # Exponentially Modified Gaussian


class ExportFormat(Enum):
    """Supported export formats."""
    EXCEL = "xlsx"
    CSV = "csv"
    JSON = "json"
    PNG = "png"
    PDF = "pdf"


class SignalQuality(Enum):
    """Quality assessment of signal/baseline."""
    EXCELLENT = auto()   # R² > 0.99
    GOOD = auto()        # R² > 0.95
    ACCEPTABLE = auto()  # R² > 0.90
    POOR = auto()        # R² > 0.80
    FAILED = auto()      # R² <= 0.80


class VisualizationMode(Enum):
    """Visualization mode for quantification results."""
    TIME_COURSE = auto()         # Line plot across all time points
    SINGLE_TIMEPOINT = auto()    # Bar chart for one specific time point
    COMPARISON = auto()          # Side-by-side comparison (e.g. RO vs RS)
    ALL_CONDITIONS = auto()      # Full grouped bar chart


class StatisticalTest(Enum):
    """Type of statistical test to perform."""
    ANOVA_ONEWAY = "anova_oneway"
    TUKEY_HSD = "tukey_hsd"
