"""
Quantification Configuration
=============================

Configuration for quantification, statistical analysis, and visualization.
"""

from dataclasses import dataclass, field
from typing import List, Dict

from ..domain.enums import VisualizationMode
from ..domain.models import CompoundDefinition


@dataclass
class SampleNameParserConfig:
    """Configuration for parsing experimental conditions from sample names."""
    cofactor_dose_pattern: str = r'_(D\d+)_'
    enzyme_pattern: str = r'_(RO|RS)_'
    replicate_pattern: str = r'GO_(\d+)_'
    time_pattern: str = r'_(\d+H)\.D$'
    negative_control_marker: str = 'NC_GO'
    nc_time_label: str = '0H'


@dataclass
class CalibrationConfig:
    """Calibration curve configuration. Compounds and DF must be user-provided."""
    compounds: List[CompoundDefinition] = field(default_factory=list)
    dilution_factor: float = 1.0


@dataclass
class RTMatchingConfig:
    """RT window peak matching configuration."""
    rt_tolerance: float = 0.0
    require_single_match: bool = True
    prefer_largest_area: bool = True


@dataclass
class StatisticalConfig:
    """Statistical analysis configuration."""
    alpha: float = 0.05
    min_replicates: int = 2
    bonferroni_correction: bool = True
    exclude_negative_controls: bool = True
    group_variable: str = "cofactor_dose"
    dose_order: List[str] = field(default_factory=lambda: ['D1', 'D2', 'D3', 'D4', 'D5'])
    enzyme_conditions: List[str] = field(default_factory=lambda: ['RO', 'RS'])
    time_points: List[str] = field(default_factory=lambda: ['6H', '12H', '24H'])


@dataclass
class VisualizationConfig:
    """Quantification visualization configuration."""
    mode: VisualizationMode = VisualizationMode.SINGLE_TIMEPOINT
    target_timepoint: str = "24H"
    figsize: tuple = (16, 13)
    dpi: int = 200
    show_individual_points: bool = True
    show_significance_brackets: bool = True
    max_significance_brackets: int = 6
    show_mean_labels: bool = True
    error_bar_capsize: int = 6
    jitter_width: float = 0.12
    show_nc_reference_line: bool = True
    nc_line_style: str = '--'
    nc_line_color: str = '#808080'
    nc_line_width: float = 2.0
    nc_label: str = 'NC (t=0)'
    dose_colors: Dict[str, str] = field(default_factory=lambda: {
        'D1': '#E53935', 'D2': '#FF7043', 'D3': '#66BB6A',
        'D4': '#42A5F5', 'D5': '#AB47BC',
    })
    time_colors: Dict[str, str] = field(default_factory=lambda: {
        '6H': '#66BB6A', '12H': '#42A5F5', '24H': '#FFA726',
    })
    enzyme_colors: Dict[str, str] = field(default_factory=lambda: {
        'RO': '#42A5F5', 'RS': '#EF5350',
    })
    time_numeric_map: Dict[str, float] = field(default_factory=lambda: {
        '0H': 0.0, '6H': 6.0, '12H': 12.0, '24H': 24.0,
    })
    title_fontsize: int = 14
    label_fontsize: int = 12
    tick_fontsize: int = 11


@dataclass
class QuantificationConfig:
    """Complete configuration for quantification pipeline."""
    sample_parser: SampleNameParserConfig = field(default_factory=SampleNameParserConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    rt_matching: RTMatchingConfig = field(default_factory=RTMatchingConfig)
    statistical: StatisticalConfig = field(default_factory=StatisticalConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)


class QuantificationPresets:
    """Preset configurations for common quantification scenarios."""

    @staticmethod
    def default() -> QuantificationConfig:
        return QuantificationConfig()

    @staticmethod
    def cofactor_m2_nad(dilution_factor: float = 66.666666) -> QuantificationConfig:
        """Module 2 Cofactor (NAD) experiment preset."""
        config = QuantificationConfig()
        config.calibration.dilution_factor = dilution_factor
        config.calibration.compounds = [
            CompoundDefinition(
                name="Tagatose", rt_window_start=10.5, rt_window_end=11.2,
                calibration_intercept=1220.254, calibration_slope=64498.76,
            ),
            CompoundDefinition(
                name="Formate", rt_window_start=11.3, rt_window_end=12.0,
                calibration_intercept=10.4596, calibration_slope=5440.724,
            ),
        ]
        return config

    @staticmethod
    def time_course_analysis(dilution_factor: float = 1.0) -> QuantificationConfig:
        """Configuration for time course visualization."""
        config = QuantificationConfig()
        config.calibration.dilution_factor = dilution_factor
        config.visualization.mode = VisualizationMode.TIME_COURSE
        config.visualization.figsize = (16, 6)
        return config
