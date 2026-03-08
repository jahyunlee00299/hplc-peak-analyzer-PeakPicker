"""
Analysis Workflow
=================

High-level workflow orchestrator for HPLC analysis.
Composes all components following Dependency Inversion.
"""

from pathlib import Path
from typing import List, Optional

from ..domain import (
    ChromatogramData,
    AnalysisResult,
    BatchResult,
    Peak,
    BaselineResult,
)

from ..interfaces import (
    IDataReader,
    IBaselineCorrector,
    IPeakDetector,
    IDataExporter,
    IPlotExporter,
)

from ..config import (
    BaselineCorrectorConfig,
    PeakAnalysisConfig,
)


class AnalysisWorkflow:
    """
    Complete HPLC analysis workflow.

    Orchestrates data reading, baseline correction, peak detection,
    and result export. All dependencies are injected.
    """

    def __init__(
        self,
        reader: IDataReader,
        baseline_corrector: IBaselineCorrector,
        peak_detector: IPeakDetector,
        data_exporter: IDataExporter = None,
        plot_exporter: IPlotExporter = None
    ):
        """
        Initialize workflow.

        Parameters
        ----------
        reader : IDataReader
            Data reader implementation
        baseline_corrector : IBaselineCorrector
            Baseline corrector implementation
        peak_detector : IPeakDetector
            Peak detector implementation
        data_exporter : IDataExporter, optional
            Data exporter (Excel, CSV)
        plot_exporter : IPlotExporter, optional
            Plot exporter
        """
        self.reader = reader
        self.baseline_corrector = baseline_corrector
        self.peak_detector = peak_detector
        self.data_exporter = data_exporter
        self.plot_exporter = plot_exporter

    def analyze_file(self, file_path: Path) -> AnalysisResult:
        """
        Analyze a single chromatogram file.

        Parameters
        ----------
        file_path : Path
            Path to chromatogram file

        Returns
        -------
        AnalysisResult
            Complete analysis result
        """
        # 1. Read data
        chromatogram = self.reader.read(Path(file_path))

        # 2. Correct baseline
        baseline_result = self.baseline_corrector.correct(
            chromatogram.time,
            chromatogram.intensity
        )

        # 3. Detect peaks
        peaks = self.peak_detector.detect(
            chromatogram.time,
            chromatogram.intensity,
            baseline_result.baseline
        )

        return AnalysisResult(
            chromatogram=chromatogram,
            baseline_result=baseline_result,
            peaks=peaks
        )

    def analyze_and_export(
        self,
        file_path: Path,
        output_dir: Path,
        export_plot: bool = True,
        export_data: bool = True
    ) -> AnalysisResult:
        """
        Analyze file and export results.

        Parameters
        ----------
        file_path : Path
            Input file path
        output_dir : Path
            Output directory
        export_plot : bool
            Export chromatogram plot
        export_data : bool
            Export peak data

        Returns
        -------
        AnalysisResult
            Analysis result
        """
        result = self.analyze_file(file_path)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = result.chromatogram.sample_name

        # Export data
        if export_data and self.data_exporter:
            data_path = output_dir / f"{base_name}_peaks.xlsx"
            self.data_exporter.export(result, data_path)

        # Export plot
        if export_plot and self.plot_exporter:
            plot_path = output_dir / f"{base_name}_chromatogram.png"
            self.plot_exporter.export_chromatogram(
                result.chromatogram.time,
                result.chromatogram.intensity,
                result.peaks,
                plot_path,
                title=f"HPLC Chromatogram: {base_name}"
            )

        return result

    def analyze_batch(self, file_paths: List[Path]) -> BatchResult:
        """
        Analyze multiple files.

        Parameters
        ----------
        file_paths : List[Path]
            List of input files

        Returns
        -------
        BatchResult
            Batch analysis results
        """
        results = []
        for path in file_paths:
            try:
                result = self.analyze_file(path)
                results.append(result)
            except Exception as e:
                print(f"Error analyzing {path}: {e}")

        return BatchResult(results=results)


class WorkflowBuilder:
    """
    Builder for constructing analysis workflows.

    Simplifies dependency injection setup.
    """

    def __init__(self):
        """Initialize builder with default settings."""
        self._reader = None
        self._baseline_corrector = None
        self._peak_detector = None
        self._data_exporter = None
        self._plot_exporter = None

    def with_chemstation_reader(self) -> 'WorkflowBuilder':
        """Use Chemstation file reader."""
        from ..infrastructure import ChemstationReader
        self._reader = ChemstationReader()
        return self

    def with_csv_reader(self) -> 'WorkflowBuilder':
        """Use CSV file reader."""
        from ..infrastructure import CSVReader
        self._reader = CSVReader()
        return self

    def with_rainbow_reader(
        self, preferred_detector: str = None
    ) -> 'WorkflowBuilder':
        """Use Rainbow .D folder reader."""
        from ..infrastructure import RainbowReader
        self._reader = RainbowReader(preferred_detector=preferred_detector)
        return self

    def with_rainbow_chemstation_reader(self) -> 'WorkflowBuilder':
        """Use rainbow-api based Chemstation .ch reader (fixes delta decompression)."""
        from ..infrastructure import RainbowChemstationReader
        self._reader = RainbowChemstationReader()
        return self

    def with_auto_reader(
        self, preferred_detector: str = None
    ) -> 'WorkflowBuilder':
        """
        Use auto-detecting reader that picks the right reader
        based on the input file type (.D, .ch, or .csv).
        """
        from ..infrastructure import RainbowReader, CSVReader, ChemstationReader
        from ..infrastructure import AutoReader
        self._reader = AutoReader(readers=[
            RainbowReader(preferred_detector=preferred_detector),
            CSVReader(),
            ChemstationReader(),
        ])
        return self

    def with_default_baseline(
        self,
        config: BaselineCorrectorConfig = None
    ) -> 'WorkflowBuilder':
        """Configure default baseline correction."""
        from ..infrastructure import ScipySignalProcessor, ScipyInterpolator
        from ..baseline import (
            BaselineCorrector,
            CompositeAnchorFinder,
            BoundaryAnchorFinder,
            PeakBoundaryAnchorFinder,
            WeightedSplineStrategy,
            BaselineQualityEvaluator,
        )

        config = config or BaselineCorrectorConfig()

        # 음수 피크(negative peak) 위로 baseline이 지나갈 수 있도록 clip 해제
        config.generator_config.clip_to_signal = False

        signal_processor = ScipySignalProcessor()
        interpolator = ScipyInterpolator()

        anchor_config = config.anchor_config

        # PeakBoundaryAnchorFinder: scipy prominence의 left/right bases를
        # anchor로 사용 → 피크 내부를 anchor로 잡지 않음, 음수 피크도 처리
        anchor_finder = CompositeAnchorFinder([
            PeakBoundaryAnchorFinder(signal_processor, anchor_config),
            BoundaryAnchorFinder(anchor_config),
        ], anchor_config)

        strategy = WeightedSplineStrategy(interpolator, config.strategy_config)
        evaluator = BaselineQualityEvaluator(signal_processor)

        self._baseline_corrector = BaselineCorrector(
            anchor_finder=anchor_finder,
            strategy=strategy,
            evaluator=evaluator,
            config=config
        )

        return self

    def with_arpls_baseline(
        self,
        lam: float = 1e5,
        p: float = 0.01,
        config: 'BaselineCorrectorConfig' = None,
    ) -> 'WorkflowBuilder':
        """
        Configure ARPLS baseline correction.

        Preferred for samples with broad fluorescence/UV backgrounds
        or significant baseline drift. Works without anchor points.

        Parameters
        ----------
        lam : float
            Smoothness penalty (1e3–1e8). Larger = smoother.
        p : float
            Asymmetry weight for background (0.001–0.1).
        """
        from ..baseline import ArplsStrategy, BaselineCorrector, BoundaryAnchorFinder
        from ..infrastructure import ScipySignalProcessor, ScipyInterpolator

        config = config or BaselineCorrectorConfig()
        config.generator_config.clip_to_signal = False

        strategy = ArplsStrategy(lam=lam, p=p)
        anchor_finder = BoundaryAnchorFinder(config.anchor_config)

        self._baseline_corrector = BaselineCorrector(
            anchor_finder=anchor_finder,
            strategy=strategy,
            config=config,
        )
        return self

    def with_default_peak_detector(
        self,
        config: PeakAnalysisConfig = None
    ) -> 'WorkflowBuilder':
        """Configure default (single-pass) peak detection."""
        from ..infrastructure import ScipySignalProcessor
        from ..peak_analysis import ProminencePeakDetector, SimplePeakBoundaryFinder

        config = config or PeakAnalysisConfig()

        signal_processor = ScipySignalProcessor()
        boundary_finder = SimplePeakBoundaryFinder(config.detection)

        self._peak_detector = ProminencePeakDetector(
            signal_processor=signal_processor,
            boundary_finder=boundary_finder,
            config=config.detection
        )

        return self

    def with_two_pass_peak_detector(
        self,
        config: PeakAnalysisConfig = None,
        major_prominence_factor: float = 0.005,
        major_distance: int = 20,
        minor_noise_multiplier: float = 2.0,
        minor_distance: int = 5,
        dedup_distance: int = 10,
    ) -> 'WorkflowBuilder':
        """
        Configure two-pass adaptive peak detection.

        Better than single-pass for samples with both large dominant peaks
        and small satellite / impurity peaks.

        Parameters
        ----------
        major_prominence_factor : float
            Prominence threshold for major peaks (fraction of signal range).
        major_distance : int
            Minimum point distance between major peaks.
        minor_noise_multiplier : float
            Prominence for minor peaks as multiple of noise level.
        minor_distance : int
            Minimum point distance between minor peaks.
        dedup_distance : int
            Minor peaks within this distance of a major peak are dropped.
        """
        from ..infrastructure import ScipySignalProcessor
        from ..peak_analysis import TwoPassPeakDetector

        config = config or PeakAnalysisConfig()
        signal_processor = ScipySignalProcessor()

        self._peak_detector = TwoPassPeakDetector(
            signal_processor=signal_processor,
            config=config.detection,
            major_prominence_factor=major_prominence_factor,
            major_distance=major_distance,
            minor_noise_multiplier=minor_noise_multiplier,
            minor_distance=minor_distance,
            dedup_distance=dedup_distance,
        )
        return self

    def with_excel_exporter(self, output_dir: Path = None) -> 'WorkflowBuilder':
        """Add Excel exporter."""
        from ..infrastructure import ExcelExporter
        self._data_exporter = ExcelExporter(output_dir)
        return self

    def with_csv_exporter(self, output_dir: Path = None) -> 'WorkflowBuilder':
        """Add CSV exporter."""
        from ..infrastructure import CSVExporter
        self._data_exporter = CSVExporter(output_dir)
        return self

    def with_plot_exporter(self, output_dir: Path = None) -> 'WorkflowBuilder':
        """Add plot exporter."""
        from ..infrastructure import ChromatogramPlotExporter
        self._plot_exporter = ChromatogramPlotExporter(output_dir)
        return self

    def build(self) -> AnalysisWorkflow:
        """
        Build the workflow.

        Returns
        -------
        AnalysisWorkflow
            Configured workflow
        """
        if self._reader is None:
            self.with_chemstation_reader()

        if self._baseline_corrector is None:
            self.with_default_baseline()

        if self._peak_detector is None:
            self.with_default_peak_detector()

        return AnalysisWorkflow(
            reader=self._reader,
            baseline_corrector=self._baseline_corrector,
            peak_detector=self._peak_detector,
            data_exporter=self._data_exporter,
            plot_exporter=self._plot_exporter
        )


def create_default_workflow(output_dir: Path = None) -> AnalysisWorkflow:
    """
    Create a fully configured default workflow.

    Parameters
    ----------
    output_dir : Path, optional
        Output directory for exports

    Returns
    -------
    AnalysisWorkflow
        Ready-to-use workflow
    """
    builder = WorkflowBuilder()
    builder.with_chemstation_reader()
    builder.with_default_baseline()
    builder.with_default_peak_detector()

    if output_dir:
        builder.with_excel_exporter(output_dir)
        builder.with_plot_exporter(output_dir)

    return builder.build()
