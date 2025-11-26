"""
Unit Tests for SOLID Deconvolution Implementation
=================================================

Tests verify:
- SRP: Each class has single responsibility
- OCP: New strategies can be added via factory
- LSP: Implementations can substitute interfaces
- DIP: Dependencies are injected via interfaces
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock

# Import interfaces
from src.solid.interfaces import (
    ISignalProcessor,
    ICurveFitter,
    IDeconvolutionAnalyzer,
    IPeakCenterEstimator,
    ICurveFitterStrategy,
    IDeconvolver,
    IAsymmetryCalculator,
)

# Import implementations
from src.solid.peak_analysis.deconvolution import (
    AsymmetryCalculator,
    ShoulderDetector,
    InflectionPointCounter,
    ShoulderDeconvolutionAnalyzer,
    PeakCenterEstimator,
    GaussianFitterStrategy,
    PeakDeconvolver,
    FitterStrategyFactory,
    gaussian,
    multi_gaussian,
    create_deconvolver,
)

from src.solid.config import DeconvolutionConfig, GaussianFitConfig
from src.solid.domain import DeconvolvedPeak, DeconvolutionResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_signal_processor():
    """Create mock signal processor for DIP testing."""
    mock = Mock(spec=ISignalProcessor)
    mock.find_peaks.return_value = (np.array([50]), {'prominences': np.array([100.0])})
    mock.derivative.return_value = np.zeros(100)
    mock.smooth.return_value = np.zeros(100)
    return mock


@pytest.fixture
def mock_curve_fitter():
    """Create mock curve fitter for DIP testing."""
    mock = Mock(spec=ICurveFitter)
    # Return fitted parameters: amplitude, center, sigma
    mock.fit.return_value = (np.array([100.0, 5.0, 0.3]), np.eye(3))
    return mock


@pytest.fixture
def sample_data():
    """Create sample chromatogram data."""
    time = np.linspace(0, 10, 1000)
    # Two overlapping Gaussian peaks
    peak1 = gaussian(time, 100, 4.5, 0.3)
    peak2 = gaussian(time, 70, 5.2, 0.35)
    signal = peak1 + peak2 + np.random.normal(0, 1, len(time))
    return time, signal


# =============================================================================
# LSP Tests - Liskov Substitution Principle
# =============================================================================

class TestLSP:
    """Test that implementations can substitute their interfaces."""

    def test_asymmetry_calculator_implements_interface(self):
        """AsymmetryCalculator should implement IAsymmetryCalculator."""
        calc = AsymmetryCalculator()
        assert isinstance(calc, IAsymmetryCalculator)

    def test_peak_center_estimator_implements_interface(self, mock_signal_processor):
        """PeakCenterEstimator should implement IPeakCenterEstimator."""
        estimator = PeakCenterEstimator(mock_signal_processor)
        assert isinstance(estimator, IPeakCenterEstimator)

    def test_shoulder_analyzer_implements_interface(self, mock_signal_processor):
        """ShoulderDeconvolutionAnalyzer should implement IDeconvolutionAnalyzer."""
        analyzer = ShoulderDeconvolutionAnalyzer(mock_signal_processor)
        assert isinstance(analyzer, IDeconvolutionAnalyzer)

    def test_gaussian_fitter_implements_interface(self, mock_curve_fitter):
        """GaussianFitterStrategy should implement ICurveFitterStrategy."""
        fitter = GaussianFitterStrategy(mock_curve_fitter)
        assert isinstance(fitter, ICurveFitterStrategy)

    def test_peak_deconvolver_implements_interface(
        self, mock_signal_processor, mock_curve_fitter
    ):
        """PeakDeconvolver should implement IDeconvolver."""
        analyzer = ShoulderDeconvolutionAnalyzer(mock_signal_processor)
        estimator = PeakCenterEstimator(mock_signal_processor)
        fitter = GaussianFitterStrategy(mock_curve_fitter)

        deconvolver = PeakDeconvolver(analyzer, estimator, fitter)
        assert isinstance(deconvolver, IDeconvolver)


# =============================================================================
# DIP Tests - Dependency Inversion Principle
# =============================================================================

class TestDIP:
    """Test that classes depend on interfaces, not implementations."""

    def test_analyzer_accepts_any_signal_processor(self):
        """Analyzer should accept any ISignalProcessor implementation."""
        mock_processor = Mock(spec=ISignalProcessor)
        mock_processor.derivative.return_value = np.zeros(100)
        mock_processor.find_peaks.return_value = (np.array([]), {})

        # Should not raise
        analyzer = ShoulderDeconvolutionAnalyzer(mock_processor)
        assert analyzer.signal_processor == mock_processor

    def test_analyzer_accepts_any_asymmetry_calculator(self, mock_signal_processor):
        """Analyzer should accept any IAsymmetryCalculator implementation."""
        mock_calculator = Mock(spec=IAsymmetryCalculator)
        mock_calculator.calculate.return_value = 1.0

        analyzer = ShoulderDeconvolutionAnalyzer(
            mock_signal_processor,
            asymmetry_calculator=mock_calculator
        )
        assert analyzer.asymmetry_calculator == mock_calculator

    def test_fitter_accepts_any_curve_fitter(self):
        """GaussianFitterStrategy should accept any ICurveFitter implementation."""
        mock_fitter = Mock(spec=ICurveFitter)

        strategy = GaussianFitterStrategy(mock_fitter)
        assert strategy.curve_fitter == mock_fitter

    def test_deconvolver_accepts_any_analyzer(self, mock_curve_fitter):
        """PeakDeconvolver should accept any IDeconvolutionAnalyzer."""
        mock_analyzer = Mock(spec=IDeconvolutionAnalyzer)
        mock_estimator = Mock(spec=IPeakCenterEstimator)
        mock_fitter_strategy = Mock(spec=ICurveFitterStrategy)

        deconvolver = PeakDeconvolver(mock_analyzer, mock_estimator, mock_fitter_strategy)
        assert deconvolver.analyzer == mock_analyzer
        assert deconvolver.center_estimator == mock_estimator
        assert deconvolver.fitter == mock_fitter_strategy


# =============================================================================
# SRP Tests - Single Responsibility Principle
# =============================================================================

class TestSRP:
    """Test that each class has a single responsibility."""

    def test_asymmetry_calculator_only_calculates_asymmetry(self):
        """AsymmetryCalculator should only have calculate method."""
        calc = AsymmetryCalculator()
        public_methods = [m for m in dir(calc) if not m.startswith('_')]
        assert 'calculate' in public_methods
        # Should not have detect, fit, or estimate methods
        assert 'detect' not in public_methods
        assert 'fit' not in public_methods
        assert 'estimate' not in public_methods

    def test_shoulder_detector_only_detects_shoulders(self, mock_signal_processor):
        """ShoulderDetector should only have detect method."""
        detector = ShoulderDetector(mock_signal_processor)
        public_methods = [m for m in dir(detector) if not m.startswith('_')]
        assert 'detect' in public_methods
        assert 'calculate' not in public_methods
        assert 'fit' not in public_methods

    def test_inflection_counter_only_counts(self, mock_signal_processor):
        """InflectionPointCounter should only have count method."""
        counter = InflectionPointCounter(mock_signal_processor)
        public_methods = [m for m in dir(counter) if not m.startswith('_')]
        assert 'count' in public_methods
        assert 'detect' not in public_methods
        assert 'fit' not in public_methods

    def test_center_estimator_only_estimates(self, mock_signal_processor):
        """PeakCenterEstimator should only have estimate_centers method."""
        estimator = PeakCenterEstimator(mock_signal_processor)
        public_methods = [m for m in dir(estimator) if not m.startswith('_')]
        assert 'estimate_centers' in public_methods
        assert 'fit' not in public_methods
        assert 'deconvolve' not in public_methods

    def test_fitter_strategy_only_fits(self, mock_curve_fitter):
        """GaussianFitterStrategy should only have fit method and name property."""
        fitter = GaussianFitterStrategy(mock_curve_fitter)
        public_methods = [m for m in dir(fitter) if not m.startswith('_')]
        assert 'fit' in public_methods
        assert 'name' in public_methods
        assert 'deconvolve' not in public_methods
        assert 'estimate' not in public_methods


# =============================================================================
# OCP Tests - Open/Closed Principle
# =============================================================================

class TestOCP:
    """Test that system is open for extension, closed for modification."""

    def test_factory_can_register_new_strategies(self, mock_curve_fitter):
        """New strategies can be registered without modifying existing code."""
        # Create a custom strategy
        class CustomFitterStrategy(ICurveFitterStrategy):
            def __init__(self, curve_fitter, config=None):
                self.curve_fitter = curve_fitter

            @property
            def name(self) -> str:
                return "Custom"

            def fit(self, time, signal, centers):
                return [], 0.0, float('inf')

        # Register it
        FitterStrategyFactory.register("custom", CustomFitterStrategy)

        # Create instance via factory
        strategy = FitterStrategyFactory.create("custom", mock_curve_fitter)
        assert isinstance(strategy, CustomFitterStrategy)
        assert strategy.name == "Custom"

    def test_factory_lists_available_strategies(self):
        """Factory should list all registered strategies."""
        strategies = FitterStrategyFactory.available_strategies()
        assert "gaussian" in strategies
        assert "multi-gaussian" in strategies

    def test_factory_raises_for_unknown_strategy(self, mock_curve_fitter):
        """Factory should raise ValueError for unknown strategies."""
        with pytest.raises(ValueError) as exc_info:
            FitterStrategyFactory.create("nonexistent", mock_curve_fitter)
        assert "nonexistent" in str(exc_info.value)


# =============================================================================
# Functional Tests
# =============================================================================

class TestFunctional:
    """Test actual functionality of deconvolution."""

    def test_gaussian_function(self):
        """Test gaussian function produces correct shape."""
        x = np.linspace(0, 10, 100)
        y = gaussian(x, amplitude=100, center=5, sigma=0.5)

        # Peak should be at center
        max_idx = np.argmax(y)
        assert abs(x[max_idx] - 5) < 0.1

        # Maximum should equal amplitude
        assert abs(y.max() - 100) < 0.1

    def test_multi_gaussian_function(self):
        """Test multi_gaussian produces sum of gaussians."""
        x = np.linspace(0, 10, 100)
        # Two peaks: amp=100, center=3, sigma=0.3 and amp=50, center=7, sigma=0.4
        y = multi_gaussian(x, 100, 3, 0.3, 50, 7, 0.4)

        # Should have two peaks
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(y, prominence=10)
        assert len(peaks) >= 2

    def test_asymmetry_calculator_symmetric_peak(self):
        """Symmetric peak should have asymmetry ~1.0."""
        calc = AsymmetryCalculator()
        time = np.linspace(0, 10, 1000)
        signal = gaussian(time, 100, 5, 0.3)
        peak_idx = np.argmax(signal)

        asymmetry = calc.calculate(time, signal, peak_idx)
        assert 0.9 < asymmetry < 1.1

    def test_center_estimator_finds_peaks(self, mock_signal_processor, sample_data):
        """Center estimator should find peak positions."""
        time, signal = sample_data

        # Setup mock to return actual peaks
        from scipy.signal import find_peaks as scipy_find_peaks
        peaks, props = scipy_find_peaks(signal, prominence=10, distance=10)
        mock_signal_processor.find_peaks.return_value = (peaks, props)

        estimator = PeakCenterEstimator(mock_signal_processor)
        centers = estimator.estimate_centers(time, signal, max_components=4)

        assert len(centers) > 0
        # Centers should be within time range
        for c in centers:
            assert time[0] <= c <= time[-1]

    def test_create_deconvolver_factory_function(self, mock_signal_processor, mock_curve_fitter):
        """Factory function should create fully configured deconvolver."""
        deconvolver = create_deconvolver(
            mock_signal_processor,
            mock_curve_fitter,
            strategy_name="gaussian"
        )

        assert isinstance(deconvolver, PeakDeconvolver)
        assert isinstance(deconvolver, IDeconvolver)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests with real scipy implementations."""

    def test_full_deconvolution_workflow(self):
        """Test complete deconvolution workflow with real data."""
        # Import real implementations
        from src.solid.infrastructure.signal_processing.scipy_adapter import (
            ScipySignalProcessor,
            ScipyCurveFitter,
        )

        # Create test data
        time = np.linspace(0, 10, 500)
        peak1 = gaussian(time, 100, 4.5, 0.3)
        peak2 = gaussian(time, 70, 5.0, 0.25)
        signal = peak1 + peak2

        # Create deconvolver with real implementations
        signal_processor = ScipySignalProcessor()
        curve_fitter = ScipyCurveFitter()

        deconvolver = create_deconvolver(
            signal_processor,
            curve_fitter,
            strategy_name="gaussian"
        )

        # Find peak region
        threshold = signal.max() * 0.01
        above = signal > threshold
        indices = np.where(above)[0]
        start_idx = indices[0]
        end_idx = indices[-1]

        # Deconvolve
        result = deconvolver.deconvolve(
            time, signal, start_idx, end_idx, force=True
        )

        # Verify result structure
        assert isinstance(result, DeconvolutionResult)
        assert result.original_peak_rt > 0
        assert result.method != "none" or not result.success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
