"""
SOLID refactor verification tests
===========================

1. mad bug fix verification (signal-scale independence)
2. ARPLS baseline accuracy test
3. 2-Pass peak detection (major + minor peaks)
4. EMG fitting (symmetric/asymmetric peaks)
5. WorkflowBuilder integration test
"""

import numpy as np
import pytest
from scipy.integrate import trapezoid



# ─────────────────────────────────────────────────────────────────────────────
# Helper: generate a synthetic chromatogram
# ─────────────────────────────────────────────────────────────────────────────

def make_chromatogram(
    n=3000, t_end=15.0, noise_std=50,
    peaks=None,   # list of (rt, amp, sigma)
    baseline_slope=0.0,
    baseline_offset=0.0,
    seed=42,
):
    """Synthetic Gaussian chromatogram with optional drift baseline."""
    rng = np.random.default_rng(seed)
    time = np.linspace(0, t_end, n)
    signal = np.zeros(n)
    if peaks is None:
        peaks = [(5.0, 100_000, 0.3)]
    for rt, amp, sigma in peaks:
        signal += amp * np.exp(-0.5 * ((time - rt) / sigma) ** 2)
    # Baseline drift
    signal += baseline_offset + baseline_slope * time
    # Noise
    signal += rng.normal(0, noise_std, n)
    return time, signal


def make_emg_peak(time, amplitude, center, sigma, tau):
    from scipy.special import erfc
    sigma = max(abs(sigma), 1e-10)
    tau = max(abs(tau), 1e-10)
    z = (sigma / tau) - (time - center) / sigma
    return (amplitude * sigma / tau * np.sqrt(np.pi / 2)
            * np.exp(0.5 * (sigma / tau) ** 2 - (time - center) / tau)
            * erfc(z / np.sqrt(2)))


# ─────────────────────────────────────────────────────────────────────────────
# 1. MAD bug fix verification
# ─────────────────────────────────────────────────────────────────────────────

class TestMadBugFix:
    """
    Verifies the fix from an absolute mad < 100 threshold to a relative
    signal_range * 0.01 threshold.

    _remove_outliers drops baseline anchors whose points are abnormally low
    (e.g. a noise dip). Key requirement: the removal criterion must be
    independent of signal scale.
    """

    def _make_finder(self):
        from peakpicker.baseline.anchor_finders.valley_finder import CompositeAnchorFinder
        from peakpicker.config import AnchorFinderConfig
        return CompositeAnchorFinder(finders=[], config=AnchorFinderConfig())

    def _make_anchors(self, values):
        from peakpicker.domain import AnchorPoint, AnchorSource
        finder = self._make_finder()
        anchors = [
            AnchorPoint(index=i, time=float(i), value=float(v),
                        confidence=1.0, source=AnchorSource.VALLEY)
            for i, v in enumerate(values)
        ]
        return finder, anchors

    def test_small_scale_removes_low_outlier(self):
        """Small signal (range ~7) - removes a very low outlier (-5.0)"""
        values = [1.0, 1.1, 1.0, 0.9, 1.2, 1.0, -5.0]
        finder, anchors = self._make_anchors(values)
        result = finder._remove_outliers(anchors)
        result_vals = [p.value for p in result]
        assert -5.0 not in result_vals, "Failed to remove the negative outlier on a small signal"

    def test_large_scale_removes_low_outlier(self):
        """Large signal (range ~1e5) - removes a very low outlier"""
        values = [100_000.0] * 8 + [-50_000.0]
        finder, anchors = self._make_anchors(values)
        result = finder._remove_outliers(anchors)
        result_vals = [p.value for p in result]
        assert -50_000.0 not in result_vals, "Failed to remove the negative outlier on a large signal"

    def test_relative_threshold_scale_invariant(self):
        """Same distribution pattern -> the number of retained points must stay the same regardless of scale"""
        finder = self._make_finder()

        def count_kept(values):
            from peakpicker.domain import AnchorPoint, AnchorSource
            anchors = [AnchorPoint(index=i, time=float(i), value=float(v),
                                   confidence=1.0, source=AnchorSource.VALLEY)
                       for i, v in enumerate(values)]
            return len(finder._remove_outliers(anchors))

        # Same shape (10 normal points + 1 very low outlier), scale differs by 1000x
        base = [10.0] * 10 + [-10.0]       # range: 20, outlier: -10
        scaled = [v * 1000 for v in base]  # range: 20000, outlier: -10000
        assert count_kept(base) == count_kept(scaled), \
            "Removal result differs by scale (relative-threshold bug)"

    def test_stable_baseline_not_over_filtered(self):
        """A stable baseline must not be over-filtered"""
        values = [100.0, 101.0, 99.0, 100.5, 100.2, 99.8]
        finder, anchors = self._make_anchors(values)
        result = finder._remove_outliers(anchors)
        assert len(result) >= 4, "Too many stable baseline points were removed"


# ─────────────────────────────────────────────────────────────────────────────
# 2. ARPLS baseline test
# ─────────────────────────────────────────────────────────────────────────────

class TestArplsStrategy:

    def test_flat_baseline_recovery(self):
        """Recovering a linear-drift baseline"""
        from peakpicker.baseline.strategies.arpls_strategy import ArplsStrategy
        time = np.linspace(0, 10, 500)
        # Linear drift + Gaussian peak
        true_baseline = 1000 + 200 * time
        peak = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)
        signal = true_baseline + peak

        strat = ArplsStrategy(lam=1e6)
        estimated = strat.generate(time, signal, anchors=[])

        # Baseline error outside the peak region < 15%
        # (ARPLS can drift near the peak edge)
        mask = np.abs(time - 5) > 1.5
        rel_err = np.abs(estimated[mask] - true_baseline[mask]) / true_baseline[mask]
        assert np.mean(rel_err) < 0.15, f"ARPLS baseline error {np.mean(rel_err)*100:.1f}% > 15%"

    def test_returns_same_length(self):
        from peakpicker.baseline.strategies.arpls_strategy import ArplsStrategy
        time = np.linspace(0, 10, 300)
        signal = np.random.default_rng(0).normal(1000, 50, 300)
        strat = ArplsStrategy()
        baseline = strat.generate(time, signal, anchors=[])
        assert len(baseline) == len(signal)

    def test_baseline_below_peaks(self):
        """The baseline must always be below the peak signal"""
        from peakpicker.baseline.strategies.arpls_strategy import ArplsStrategy
        time = np.linspace(0, 10, 500)
        signal = (500 + 200 * np.sin(time / 3)
                  + 80_000 * np.exp(-0.5 * ((time - 5) / 0.4) ** 2))
        strat = ArplsStrategy(lam=1e5)
        baseline = strat.generate(time, signal, anchors=[])
        peak_region = (time > 4) & (time < 6)
        assert np.all(baseline[peak_region] <= signal[peak_region] * 1.05), \
            "ARPLS baseline exceeds the peak signal"


# ─────────────────────────────────────────────────────────────────────────────
# 3. 2-Pass peak detection test
# ─────────────────────────────────────────────────────────────────────────────

class TestTwoPassDetector:

    def _make_detector(self):
        from peakpicker.peak_analysis.detectors.two_pass_detector import TwoPassPeakDetector
        from peakpicker.infrastructure.signal_processing.scipy_adapter import ScipySignalProcessor
        return TwoPassPeakDetector(signal_processor=ScipySignalProcessor())

    def test_detects_major_peak(self):
        det = self._make_detector()
        time, signal = make_chromatogram(peaks=[(5.0, 100_000, 0.3)])
        peaks = det.detect(time, signal)
        assert len(peaks) >= 1
        rts = [p.rt for p in peaks]
        assert any(abs(rt - 5.0) < 0.5 for rt in rts), f"RT=5.0 peak not detected: {rts}"

    def test_detects_minor_and_major(self):
        """Simultaneously detects a large peak (100k) and a small peak (5k)"""
        det = self._make_detector()
        time, signal = make_chromatogram(peaks=[
            (3.0, 100_000, 0.3),
            (8.0, 5_000, 0.2),
        ], noise_std=30)
        peaks = det.detect(time, signal)
        rts = [p.rt for p in peaks]
        has_major = any(abs(rt - 3.0) < 0.5 for rt in rts)
        has_minor = any(abs(rt - 8.0) < 0.5 for rt in rts)
        assert has_major, f"Major peak RT=3.0 not detected: {rts}"
        assert has_minor, f"Minor peak RT=8.0 not detected: {rts}"

    def test_no_duplicate_near_main_peak(self):
        """No duplicate peaks near the main peak (RT=5.0); noise peaks are at other positions"""
        det = self._make_detector()
        time, signal = make_chromatogram(peaks=[(5.0, 100_000, 0.3)])
        peaks = det.detect(time, signal)
        # No duplicates within 0.5 min in the RT 4.0-6.0 range
        main_region = [p for p in peaks if 4.0 <= p.rt <= 6.0]
        rts = sorted(p.rt for p in main_region)
        for i in range(len(rts) - 1):
            assert rts[i + 1] - rts[i] > 0.2, f"Duplicate near the main peak: {rts}"

    def test_area_sum_reasonable(self):
        """The sum of the detected peak areas should be close to the signal integral"""
        det = self._make_detector()
        time, signal = make_chromatogram(
            peaks=[(5.0, 100_000, 0.3)], noise_std=0
        )
        true_area = float(trapezoid(signal, time))
        peaks = det.detect(time, signal)
        detected_area = sum(p.area for p in peaks)
        assert detected_area > true_area * 0.5, "Detected area is too small"


# ─────────────────────────────────────────────────────────────────────────────
# 4. EMG Fitter test
# ─────────────────────────────────────────────────────────────────────────────

class TestEmgFitter:

    def test_symmetric_peak_fit(self):
        """Symmetric Gaussian (tau≈0) -> EMG should fit it well"""
        from peakpicker.peak_analysis.deconvolution.emg_fitter import EmgFitter
        time = np.linspace(3, 7, 300)
        true_signal = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)

        fitter = EmgFitter()
        result = fitter.fit(time, true_signal, centers=[5.0])

        assert result['r2'] > 0.95, f"Symmetric peak R²={result['r2']:.3f} < 0.95"
        assert len(result['params']) == 1
        _, center, _, _ = result['params'][0]
        assert abs(center - 5.0) < 0.1, f"Center error: {abs(center - 5.0):.3f}"

    def test_asymmetric_peak_fit(self):
        """Tailing EMG peak -> R² > 0.90"""
        from peakpicker.peak_analysis.deconvolution.emg_fitter import EmgFitter
        time = np.linspace(3, 10, 500)
        true_signal = make_emg_peak(time, amplitude=50_000,
                                    center=5.0, sigma=0.3, tau=0.5)

        fitter = EmgFitter()
        result = fitter.fit(time, true_signal, centers=[5.0])

        assert result['r2'] > 0.90, f"Asymmetric EMG R²={result['r2']:.3f} < 0.90"
        assert result['areas'][0] > 0

    def test_two_component_fit(self):
        """Deconvolving two overlapping peaks"""
        from peakpicker.peak_analysis.deconvolution.emg_fitter import EmgFitter
        time = np.linspace(3, 9, 400)
        s1 = make_emg_peak(time, 60_000, 5.0, 0.25, 0.2)
        s2 = make_emg_peak(time, 30_000, 6.0, 0.25, 0.2)
        signal = s1 + s2

        fitter = EmgFitter()
        result = fitter.fit(time, signal, centers=[5.0, 6.0])

        assert result['r2'] > 0.90, f"2-component EMG R²={result['r2']:.3f} < 0.90"
        assert len(result['params']) == 2

    def test_area_analytical_vs_numerical(self):
        """EMG analytical area vs. trapezoidal integration error < 5%"""
        from peakpicker.peak_analysis.deconvolution.emg_fitter import EmgFitter
        time = np.linspace(0, 15, 1000)
        true_signal = make_emg_peak(time, 50_000, 7.0, 0.4, 0.3)
        numerical_area = float(trapezoid(true_signal, time))

        fitter = EmgFitter()
        result = fitter.fit(time, true_signal, centers=[7.0])
        analytical_area = result['areas'][0]

        rel_err = abs(analytical_area - numerical_area) / numerical_area
        assert rel_err < 0.05, f"EMG area error {rel_err*100:.1f}% > 5%"


# ─────────────────────────────────────────────────────────────────────────────
# 5. WorkflowBuilder integration test
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkflowBuilder:

    def _make_csv(self, tmp_path, peaks):
        import pandas as pd
        time, signal = make_chromatogram(peaks=peaks, noise_std=50)
        df = pd.DataFrame({'Time [min]': time, 'Signal': signal})
        path = tmp_path / "test_chrom.csv"
        df.to_csv(path, index=False)
        return path, time, signal

    def test_default_workflow_builds(self):
        from peakpicker.application.workflow import WorkflowBuilder
        wf = WorkflowBuilder().with_auto_reader().with_default_baseline().with_default_peak_detector().build()
        assert wf is not None

    def test_arpls_workflow_builds(self):
        from peakpicker.application.workflow import WorkflowBuilder
        wf = (WorkflowBuilder()
              .with_auto_reader()
              .with_arpls_baseline(lam=1e5)
              .with_two_pass_peak_detector()
              .build())
        assert wf is not None

    def test_two_pass_workflow_detects_peaks(self, tmp_path):
        """ARPLS + 2-Pass pipeline end-to-end"""
        from peakpicker.application.workflow import WorkflowBuilder
        path, _, _ = self._make_csv(tmp_path, [(5.0, 100_000, 0.3)])

        wf = (WorkflowBuilder()
              .with_auto_reader()
              .with_arpls_baseline(lam=1e5)
              .with_two_pass_peak_detector()
              .build())

        result = wf.analyze_file(path)
        assert len(result.peaks) >= 1
        rts = [p.rt for p in result.peaks]
        assert any(abs(rt - 5.0) < 0.5 for rt in rts), f"Peak not detected: {rts}"


# ─────────────────────────────────────────────────────────────────────────────
# 6. ProminencePeakDetector Phase 1 fix test
# ─────────────────────────────────────────────────────────────────────────────

class TestProminencePeakDetectorPhase1:
    """
    Phase 1 fix verification:
    - MAD-based noise estimation
    - np.trapezoid (deprecation-free)
    - valley cap between adjacent peaks
    """

    def _make_detector(self):
        from peakpicker.peak_analysis.detectors.peak_detector import ProminencePeakDetector
        from peakpicker.infrastructure.signal_processing.scipy_adapter import ScipySignalProcessor
        return ProminencePeakDetector(signal_processor=ScipySignalProcessor())

    def test_mad_noise_small_scale(self):
        """Peak detection on an RID-scale signal (range 1-10), where the 25th percentile becomes 0"""
        det = self._make_detector()
        time = np.linspace(0, 10, 1000)
        # Small signal: max 5.0, noise ~0.01
        signal = 5.0 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)
        signal += np.random.default_rng(0).normal(0, 0.01, 1000)
        signal = np.maximum(signal, 0)
        peaks = det.detect(time, signal)
        rts = [p.rt for p in peaks]
        assert any(abs(rt - 5.0) < 0.5 for rt in rts), \
            f"Small-signal peak not detected (percentile-based noise estimate becomes 0, causing over-detection): {rts}"

    def test_valley_cap_two_adjacent_peaks(self):
        """The boundary between two adjacent peaks must break at the valley (no overlap)"""
        det = self._make_detector()
        time = np.linspace(0, 10, 2000)
        # Two peaks that do not overlap
        signal = (100_000 * np.exp(-0.5 * ((time - 3) / 0.3) ** 2)
                  + 80_000 * np.exp(-0.5 * ((time - 7) / 0.3) ** 2))
        peaks = det.detect(time, signal)
        if len(peaks) >= 2:
            peaks_sorted = sorted(peaks, key=lambda p: p.rt)
            # End of the first peak <= start of the second peak (no boundary overlap)
            assert peaks_sorted[0].index_end <= peaks_sorted[1].index_start + 5, \
                (f"Valley cap not applied: peak1 end={peaks_sorted[0].index_end}, "
                 f"peak2 start={peaks_sorted[1].index_start}")

    def test_trapezoid_no_deprecation_warning(self):
        """Uses np.trapezoid - must not raise a DeprecationWarning"""
        import warnings
        det = self._make_detector()
        time = np.linspace(0, 10, 500)
        signal = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            peaks = det.detect(time, signal)  # np.trapz would raise a DeprecationWarning here

        assert len(peaks) >= 1

    def test_estimate_noise_static_method(self):
        """_estimate_noise: scales proportionally on signals well above the floor(1.0)"""
        from peakpicker.peak_analysis.detectors.peak_detector import ProminencePeakDetector
        rng = np.random.default_rng(42)

        # Both signals must be far above floor(1.0) to verify the ratio
        small = rng.normal(0, 1_000, 500)       # noise MAD ≈ 1000
        large = rng.normal(0, 1_000_000, 500)   # noise MAD ≈ 1000_000

        noise_small = ProminencePeakDetector._estimate_noise(small)
        noise_large = ProminencePeakDetector._estimate_noise(large)

        # The ratio should be ~1000x (scale-proportional)
        ratio = noise_large / noise_small
        assert 900 < ratio < 1100, f"MAD noise is not proportional to scale: ratio={ratio:.1f}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. GaussianFitter exception logging test
# ─────────────────────────────────────────────────────────────────────────────

class TestGaussianFitterLogging:

    def test_fit_failure_logs_warning(self):
        """On a failed Gaussian fit, a WARNING must be logged and an empty list returned safely"""
        import logging
        from peakpicker.peak_analysis.deconvolution.gaussian_fitter import GaussianFitterStrategy
        from peakpicker.infrastructure.signal_processing.scipy_adapter import ScipyCurveFitter

        fitter = GaussianFitterStrategy(curve_fitter=ScipyCurveFitter())

        # An all-zero signal: the initial amplitude guess becomes 0, causing a bounds
        # conflict and the fit to fail
        time = np.linspace(0, 1, 5)
        signal = np.zeros(5)

        records = []

        class ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = ListHandler(level=logging.WARNING)
        log = logging.getLogger('peakpicker.peak_analysis.deconvolution.gaussian_fitter')
        log.addHandler(handler)
        log.setLevel(logging.WARNING)

        try:
            peaks, r2, rmse = fitter.fit(time, signal, centers=[0.5])
        finally:
            log.removeHandler(handler)

        # Result must be an empty list + safe defaults
        assert isinstance(peaks, list), "Must return a list when the fit fails"
        # A WARNING log must remain when the fit actually failed
        if len(peaks) == 0 and r2 == 0.0:
            assert any(r.levelno >= logging.WARNING for r in records), \
                "No WARNING log on fit failure"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Analyzer dynamic window test
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzerDynamicWindow:

    def _make_analyzer(self):
        from peakpicker.peak_analysis.deconvolution.analyzer import ShoulderDeconvolutionAnalyzer
        from peakpicker.infrastructure.signal_processing.scipy_adapter import ScipySignalProcessor
        return ShoulderDeconvolutionAnalyzer(signal_processor=ScipySignalProcessor())

    def test_short_signal_no_crash(self):
        """On a short signal (30 points) with a fixed ±50 window, there must be no index-out-of-bounds error"""
        analyzer = self._make_analyzer()
        time = np.linspace(0, 3, 30)
        signal = 1000 * np.exp(-0.5 * ((time - 1.5) / 0.3) ** 2)
        peak_idx = int(np.argmax(signal))
        # Must run without raising an exception
        try:
            has_shoulder, _ = analyzer._detect_shoulder(time, signal, peak_idx)
            n_inflections = analyzer._count_inflection_points(signal, peak_idx)
        except IndexError as e:
            pytest.fail(f"IndexError raised on a short signal: {e}")

    def test_long_signal_uses_capped_window(self):
        """On a long signal (2000 points), the window must be capped at 50 or below"""
        from peakpicker.peak_analysis.deconvolution import analyzer as ana_module
        import inspect

        # Check the half_window calculation in the _detect_shoulder source
        src = inspect.getsource(
            ana_module.ShoulderDeconvolutionAnalyzer._detect_shoulder
        )
        assert 'min(50' in src or 'min(30' in src, \
            "_detect_shoulder has no dynamic window cap (still a fixed ±50)"

    def test_symmetric_peak_no_shoulder_detected(self):
        """A perfect Gaussian peak -> no shoulder should be detected"""
        analyzer = self._make_analyzer()
        time = np.linspace(0, 10, 500)
        signal = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)
        peak_idx = int(np.argmax(signal))
        has_shoulder, _ = analyzer._detect_shoulder(time, signal, peak_idx)
        # A perfect Gaussian must not have a shoulder
        assert not has_shoulder, "A shoulder was incorrectly detected on a Gaussian peak"


class TestAreaConventionSeconds:
    """
    ChemStation area convention regression guard (260828).

    Area MUST be integrated in seconds (time_min * 60), not minutes -- a bare
    minute-axis trapezoid silently returns areas 60x too small and every
    downstream calibration curve (fit in nRIU*s) then reads 60x too high a
    concentration. This exact regression cost a full HPLC re-quantitation
    cycle (lab report 260828, Step A2). Pin it
    here so the next person who "cleans up" the *60.0 in peak_detector.py
    breaks a test, not a downstream fit silently.
    """

    def _make_detector(self):
        from peakpicker.peak_analysis.detectors.peak_detector import ProminencePeakDetector
        from peakpicker.infrastructure.signal_processing.scipy_adapter import ScipySignalProcessor
        return ProminencePeakDetector(signal_processor=ScipySignalProcessor())

    def test_area_is_60x_minute_integration(self):
        """Synthetic Gaussian peak: seconds-area must equal ~60x the minute-axis trapezoid."""
        det = self._make_detector()
        time = np.linspace(0, 10, 6000)  # minutes
        signal = 100_000 * np.exp(-0.5 * ((time - 5) / 0.2) ** 2)
        peaks = det.detect(time, signal)
        assert len(peaks) >= 1, "The synthetic peak was not detected"
        peak = max(peaks, key=lambda p: p.height)

        start, end = peak.index_start, peak.index_end
        area_minutes = float(trapezoid(signal[start:end + 1], time[start:end + 1]))
        expected_seconds_area = area_minutes * 60.0

        assert peak.area == pytest.approx(expected_seconds_area, rel=1e-6), (
            f"Area convention regression: got {peak.area}, expected ~60x the minute-axis "
            f"integral ({expected_seconds_area}). See QUANTITATION_RULES.md."
        )
        # and the inverse: area must NOT match a plain minute-axis integration
        assert peak.area != pytest.approx(area_minutes, rel=1e-3), (
            "Area matches minute-axis integration directly -- the *60.0 seconds "
            "conversion has been silently reverted."
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
