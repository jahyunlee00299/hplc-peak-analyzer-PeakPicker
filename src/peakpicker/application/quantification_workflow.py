"""Quantification workflow orchestration for HPLC peak analysis."""

from pathlib import Path
from typing import List, Optional

from ..domain.models import (
    BatchResult,
    CompoundDefinition,
    QuantificationResult,
    StatisticalAnalysisResult,
    VisualizationMode,
)
from ..interfaces.quantification import (
    IQuantifier,
    IStatisticalAnalyzer,
    IQuantificationPlotExporter,
    IQuantificationExporter,
)
from ..config.quantification_config import QuantificationConfig


class QuantificationWorkflow:
    """Orchestrates the full quantification pipeline: quantify, analyze, export."""

    def __init__(
        self,
        quantifier: IQuantifier,
        statistical_analyzer: IStatisticalAnalyzer = None,
        plot_exporter: IQuantificationPlotExporter = None,
        data_exporter: IQuantificationExporter = None,
        config: QuantificationConfig = None,
    ):
        self._quantifier = quantifier
        self._statistical_analyzer = statistical_analyzer
        self._plot_exporter = plot_exporter
        self._data_exporter = data_exporter
        self._config = config

    def quantify(self, batch_result: BatchResult) -> QuantificationResult:
        """Run quantification on a batch of peak integration results."""
        cfg = self._config or QuantificationConfig()
        return self._quantifier.quantify(
            batch_result=batch_result,
            compounds=cfg.calibration.compounds,
            dilution_factor=cfg.calibration.dilution_factor,
        )

    def analyze_statistics(
        self, quant_result: QuantificationResult
    ) -> Optional[StatisticalAnalysisResult]:
        """Run statistical analysis on quantification results, if analyzer is available."""
        if self._statistical_analyzer is None:
            return None
        cfg = self._config or QuantificationConfig()
        return self._statistical_analyzer.analyze(
            quantification_result=quant_result,
            group_variable=cfg.statistical.group_variable,
            alpha=cfg.statistical.alpha,
        )

    def export_all(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_dir: Path,
        filename_prefix: str = "quantification",
    ) -> List[Path]:
        """Export all outputs (Excel data and plots) based on configuration.

        Returns a list of all exported file paths.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        exported_files: List[Path] = []

        # Export Excel via data exporter
        if self._data_exporter is not None:
            excel_path = output_dir / f"{filename_prefix}_results.xlsx"
            result_path = self._data_exporter.export(
                quant_result, stat_result, excel_path
            )
            if result_path is not None:
                if isinstance(result_path, list):
                    exported_files.extend(result_path)
                else:
                    exported_files.append(result_path)

        # Export plots based on visualization mode from config
        if self._plot_exporter is not None:
            mode = (
                self._config.visualization.mode
                if self._config is not None
                else VisualizationMode.ALL_CONDITIONS
            )

            plot_paths = self._export_plots(
                quant_result, stat_result, output_dir, filename_prefix, mode
            )
            exported_files.extend(plot_paths)

        return exported_files

    def _export_plots(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_dir: Path,
        filename_prefix: str,
        mode: VisualizationMode,
    ) -> List[Path]:
        """Export plots according to the specified visualization mode."""
        exported: List[Path] = []

        if mode == VisualizationMode.SINGLE_TIMEPOINT:
            exported.extend(
                self._export_bar_charts(
                    quant_result, stat_result, output_dir, filename_prefix
                )
            )
        elif mode == VisualizationMode.TIME_COURSE:
            exported.extend(
                self._export_time_course(
                    quant_result, stat_result, output_dir, filename_prefix
                )
            )
        elif mode == VisualizationMode.COMPARISON:
            exported.extend(
                self._export_comparison(
                    quant_result, stat_result, output_dir, filename_prefix
                )
            )
        elif mode == VisualizationMode.ALL_CONDITIONS:
            exported.extend(
                self._export_bar_charts(
                    quant_result, stat_result, output_dir, filename_prefix
                )
            )
            exported.extend(
                self._export_time_course(
                    quant_result, stat_result, output_dir, filename_prefix
                )
            )
            exported.extend(
                self._export_comparison(
                    quant_result, stat_result, output_dir, filename_prefix
                )
            )

        return exported

    def _export_bar_charts(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_dir: Path,
        filename_prefix: str,
    ) -> List[Path]:
        """Export bar charts per compound x enzyme x timepoint."""
        cfg = self._config or QuantificationConfig()
        exported: List[Path] = []

        enzymes = cfg.statistical.enzyme_conditions
        time_points = (
            [cfg.visualization.target_timepoint]
            if cfg.visualization.mode == VisualizationMode.SINGLE_TIMEPOINT
            else cfg.statistical.time_points
        )

        for compound in quant_result.compound_names:
            for enzyme in enzymes:
                for tp in time_points:
                    out_path = output_dir / (
                        f"{filename_prefix}_bar_{compound}_{enzyme}_{tp}.png"
                    )
                    path = self._plot_exporter.export_bar_chart(
                        quant_result, stat_result, out_path,
                        compound, enzyme, tp,
                    )
                    if path:
                        exported.append(path)
        return exported

    def _export_time_course(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_dir: Path,
        filename_prefix: str,
    ) -> List[Path]:
        """Export time course plots per compound."""
        exported: List[Path] = []

        for compound in quant_result.compound_names:
            out_path = output_dir / f"{filename_prefix}_timecourse_{compound}.png"
            path = self._plot_exporter.export_time_course(
                quant_result, out_path, compound,
            )
            if path:
                exported.append(path)
        return exported

    def _export_comparison(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_dir: Path,
        filename_prefix: str,
    ) -> List[Path]:
        """Export comparison charts per compound x timepoint."""
        cfg = self._config or QuantificationConfig()
        exported: List[Path] = []

        time_points = (
            [cfg.visualization.target_timepoint]
            if cfg.visualization.mode == VisualizationMode.SINGLE_TIMEPOINT
            else cfg.statistical.time_points
        )

        for compound in quant_result.compound_names:
            for tp in time_points:
                out_path = output_dir / (
                    f"{filename_prefix}_comparison_{compound}_{tp}.png"
                )
                path = self._plot_exporter.export_comparison_chart(
                    quant_result, out_path, compound, tp,
                )
                if path:
                    exported.append(path)
        return exported

    def run(
        self,
        batch_result: BatchResult,
        output_dir: Optional[Path] = None,
        filename_prefix: str = "quantification",
    ) -> tuple:
        """Run the full quantification workflow: quantify, analyze, and export.

        Returns:
            A tuple of (QuantificationResult, StatisticalAnalysisResult, List[Path]).
            StatisticalAnalysisResult may be None if no statistical analyzer is configured.
            List[Path] may be empty if no output_dir is provided or no exporters configured.
        """
        quant_result = self.quantify(batch_result)
        stat_result = self.analyze_statistics(quant_result)

        exported_files: List[Path] = []
        if output_dir is not None:
            exported_files = self.export_all(
                quant_result, stat_result, output_dir, filename_prefix
            )

        return (quant_result, stat_result, exported_files)


class QuantificationWorkflowBuilder:
    """Fluent builder for constructing a QuantificationWorkflow with all dependencies."""

    def __init__(self):
        self._config: Optional[QuantificationConfig] = None
        self._compounds: Optional[List[CompoundDefinition]] = None
        self._dilution_factor: Optional[float] = None
        self._quantifier: Optional[IQuantifier] = None
        self._statistical_analyzer: Optional[IStatisticalAnalyzer] = None
        self._plot_exporter: Optional[IQuantificationPlotExporter] = None
        self._data_exporter: Optional[IQuantificationExporter] = None

    def with_config(self, config: QuantificationConfig) -> "QuantificationWorkflowBuilder":
        """Set the quantification configuration."""
        self._config = config
        return self

    def with_compounds(
        self, compounds: List[CompoundDefinition]
    ) -> "QuantificationWorkflowBuilder":
        """Set the compound definitions for calibration."""
        self._compounds = compounds
        return self

    def with_dilution_factor(self, df: float) -> "QuantificationWorkflowBuilder":
        """Set the dilution factor for concentration calculations."""
        self._dilution_factor = df
        return self

    def with_default_quantifier(self) -> "QuantificationWorkflowBuilder":
        """Create and set the default quantifier pipeline.

        Assembles: RegexSampleNameParser -> RTWindowPeakMatcher ->
        LinearCalibrationCalculator -> BatchQuantifier.
        """
        from ..infrastructure.quantification import (
            RegexSampleNameParser,
            RTWindowPeakMatcher,
            LinearCalibrationCalculator,
            BatchQuantifier,
        )

        cfg = self._config or QuantificationConfig()

        parser = RegexSampleNameParser(cfg.sample_parser)
        matcher = RTWindowPeakMatcher(cfg.rt_matching)
        calculator = LinearCalibrationCalculator()
        self._quantifier = BatchQuantifier(
            parser=parser,
            matcher=matcher,
            calculator=calculator,
        )
        return self

    def with_statistics(self) -> "QuantificationWorkflowBuilder":
        """Create and set the default statistical analyzer."""
        from ..infrastructure.quantification import ScipyStatisticalAnalyzer

        cfg = self._config or QuantificationConfig()
        self._statistical_analyzer = ScipyStatisticalAnalyzer(cfg.statistical)
        return self

    def with_plot_exporter(self) -> "QuantificationWorkflowBuilder":
        """Create and set the default plot exporter."""
        from ..infrastructure.quantification import QuantificationPlotExporter

        cfg = self._config or QuantificationConfig()
        self._plot_exporter = QuantificationPlotExporter(cfg.visualization, cfg.statistical)
        return self

    def with_excel_exporter(self) -> "QuantificationWorkflowBuilder":
        """Create and set the default Excel data exporter."""
        from ..infrastructure.quantification import QuantificationExcelExporter

        cfg = self._config or QuantificationConfig()
        self._data_exporter = QuantificationExcelExporter(cfg.statistical)
        return self

    def build(self) -> QuantificationWorkflow:
        """Build and return the configured QuantificationWorkflow.

        Raises:
            ValueError: If no quantifier has been configured.
        """
        if self._quantifier is None:
            raise ValueError(
                "A quantifier is required. Call with_default_quantifier() "
                "or provide a custom IQuantifier before building."
            )

        return QuantificationWorkflow(
            quantifier=self._quantifier,
            statistical_analyzer=self._statistical_analyzer,
            plot_exporter=self._plot_exporter,
            data_exporter=self._data_exporter,
            config=self._config,
        )

    def _resolve_compounds(self) -> List[CompoundDefinition]:
        """Resolve compounds from explicit setting or config."""
        if self._compounds is not None:
            return self._compounds
        if self._config is not None:
            return self._config.calibration.compounds
        raise ValueError(
            "Compounds must be provided via with_compounds() or with_config()."
        )

    def _resolve_dilution_factor(self) -> float:
        """Resolve dilution factor from explicit setting or config."""
        if self._dilution_factor is not None:
            return self._dilution_factor
        if self._config is not None:
            return self._config.calibration.dilution_factor
        return 1.0


def create_quantification_workflow(
    compounds: List[CompoundDefinition],
    dilution_factor: float,
    config: Optional[QuantificationConfig] = None,
    with_statistics: bool = True,
    with_plots: bool = True,
    with_excel: bool = True,
) -> QuantificationWorkflow:
    """Convenience factory function to create a fully configured QuantificationWorkflow.

    Args:
        compounds: List of compound definitions for calibration.
        dilution_factor: Dilution factor for concentration calculations.
        config: Optional quantification configuration. A default is created if not provided.
        with_statistics: Whether to include statistical analysis (default True).
        with_plots: Whether to include plot exporting (default True).
        with_excel: Whether to include Excel exporting (default True).

    Returns:
        A fully configured QuantificationWorkflow instance.
    """
    builder = QuantificationWorkflowBuilder()

    if config is not None:
        builder.with_config(config)

    builder.with_compounds(compounds)
    builder.with_dilution_factor(dilution_factor)
    builder.with_default_quantifier()

    if with_statistics:
        builder.with_statistics()

    if with_plots:
        builder.with_plot_exporter()

    if with_excel:
        builder.with_excel_exporter()

    return builder.build()
