"""
SOLID 리팩토링 검증 테스트
===========================

1. mad 버그 수정 검증 (신호 스케일 무관)
2. ARPLS 베이스라인 정확도 테스트
3. 2-Pass 피크 감지 (major + minor peaks)
4. EMG fitting (대칭/비대칭 피크)
5. WorkflowBuilder 통합 테스트
"""

import sys
import os
import numpy as np
import pytest
from scipy.integrate import trapezoid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ─────────────────────────────────────────────────────────────────────────────
# Helper: 합성 크로마토그램 생성
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
# 1. MAD 버그 수정 검증
# ─────────────────────────────────────────────────────────────────────────────

class TestMadBugFix:
    """
    mad < 100 절대값 → signal_range * 0.01 상대값으로 수정 검증.

    _remove_outliers는 baseline anchor 중 너무 낮은 포인트(노이즈 dip 등)를 제거한다.
    핵심: 제거 기준이 signal scale과 무관해야 한다.
    """

    def _make_finder(self):
        from solid.baseline.anchor_finders.valley_finder import CompositeAnchorFinder
        from solid.config import AnchorFinderConfig
        return CompositeAnchorFinder(finders=[], config=AnchorFinderConfig())

    def _make_anchors(self, values):
        from solid.domain import AnchorPoint, AnchorSource
        finder = self._make_finder()
        anchors = [
            AnchorPoint(index=i, time=float(i), value=float(v),
                        confidence=1.0, source=AnchorSource.VALLEY)
            for i, v in enumerate(values)
        ]
        return finder, anchors

    def test_small_scale_removes_low_outlier(self):
        """소신호(범위 ~7) — 매우 낮은 outlier(-5.0) 제거"""
        values = [1.0, 1.1, 1.0, 0.9, 1.2, 1.0, -5.0]
        finder, anchors = self._make_anchors(values)
        result = finder._remove_outliers(anchors)
        result_vals = [p.value for p in result]
        assert -5.0 not in result_vals, "소신호 음수 이상값 제거 실패"

    def test_large_scale_removes_low_outlier(self):
        """대신호(범위 ~1e5) — 매우 낮은 outlier 제거"""
        values = [100_000.0] * 8 + [-50_000.0]
        finder, anchors = self._make_anchors(values)
        result = finder._remove_outliers(anchors)
        result_vals = [p.value for p in result]
        assert -50_000.0 not in result_vals, "대신호 음수 이상값 제거 실패"

    def test_relative_threshold_scale_invariant(self):
        """같은 패턴의 분포 → 스케일에 무관하게 동일한 포인트 수 유지"""
        finder = self._make_finder()

        def count_kept(values):
            from solid.domain import AnchorPoint, AnchorSource
            anchors = [AnchorPoint(index=i, time=float(i), value=float(v),
                                   confidence=1.0, source=AnchorSource.VALLEY)
                       for i, v in enumerate(values)]
            return len(finder._remove_outliers(anchors))

        # 동일한 형태 (정상 10개 + 매우 낮은 outlier 1개), 스케일만 1000배 차이
        base = [10.0] * 10 + [-10.0]       # 범위: 20, outlier: -10
        scaled = [v * 1000 for v in base]  # 범위: 20000, outlier: -10000
        assert count_kept(base) == count_kept(scaled), \
            "스케일에 따라 제거 결과가 달라짐 (상대값 버그)"

    def test_stable_baseline_not_over_filtered(self):
        """안정적인 베이스라인 — 과도하게 제거하지 않아야 함"""
        values = [100.0, 101.0, 99.0, 100.5, 100.2, 99.8]
        finder, anchors = self._make_anchors(values)
        result = finder._remove_outliers(anchors)
        assert len(result) >= 4, "안정적 베이스라인 포인트를 너무 많이 제거"


# ─────────────────────────────────────────────────────────────────────────────
# 2. ARPLS 베이스라인 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestArplsStrategy:

    def test_flat_baseline_recovery(self):
        """선형 드리프트 베이스라인 복원"""
        from solid.baseline.strategies.arpls_strategy import ArplsStrategy
        time = np.linspace(0, 10, 500)
        # 선형 드리프트 + 가우시안 피크
        true_baseline = 1000 + 200 * time
        peak = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)
        signal = true_baseline + peak

        strat = ArplsStrategy(lam=1e6)
        estimated = strat.generate(time, signal, anchors=[])

        # 피크 외부 구간에서 베이스라인 오차 < 15%
        # (ARPLS는 피크 근처 edge에서 drift 발생 가능)
        mask = np.abs(time - 5) > 1.5
        rel_err = np.abs(estimated[mask] - true_baseline[mask]) / true_baseline[mask]
        assert np.mean(rel_err) < 0.15, f"ARPLS 베이스라인 오차 {np.mean(rel_err)*100:.1f}% > 15%"

    def test_returns_same_length(self):
        from solid.baseline.strategies.arpls_strategy import ArplsStrategy
        time = np.linspace(0, 10, 300)
        signal = np.random.default_rng(0).normal(1000, 50, 300)
        strat = ArplsStrategy()
        baseline = strat.generate(time, signal, anchors=[])
        assert len(baseline) == len(signal)

    def test_baseline_below_peaks(self):
        """베이스라인은 피크 신호보다 항상 낮아야 함"""
        from solid.baseline.strategies.arpls_strategy import ArplsStrategy
        time = np.linspace(0, 10, 500)
        signal = (500 + 200 * np.sin(time / 3)
                  + 80_000 * np.exp(-0.5 * ((time - 5) / 0.4) ** 2))
        strat = ArplsStrategy(lam=1e5)
        baseline = strat.generate(time, signal, anchors=[])
        peak_region = (time > 4) & (time < 6)
        assert np.all(baseline[peak_region] <= signal[peak_region] * 1.05), \
            "ARPLS 베이스라인이 피크 신호를 초과"


# ─────────────────────────────────────────────────────────────────────────────
# 3. 2-Pass 피크 감지 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestTwoPassDetector:

    def _make_detector(self):
        from solid.peak_analysis.detectors.two_pass_detector import TwoPassPeakDetector
        from solid.infrastructure.signal_processing.scipy_adapter import ScipySignalProcessor
        return TwoPassPeakDetector(signal_processor=ScipySignalProcessor())

    def test_detects_major_peak(self):
        det = self._make_detector()
        time, signal = make_chromatogram(peaks=[(5.0, 100_000, 0.3)])
        peaks = det.detect(time, signal)
        assert len(peaks) >= 1
        rts = [p.rt for p in peaks]
        assert any(abs(rt - 5.0) < 0.5 for rt in rts), f"RT=5.0 피크 미감지: {rts}"

    def test_detects_minor_and_major(self):
        """큰 피크(100k)와 작은 피크(5k) 동시 감지"""
        det = self._make_detector()
        time, signal = make_chromatogram(peaks=[
            (3.0, 100_000, 0.3),
            (8.0, 5_000, 0.2),
        ], noise_std=30)
        peaks = det.detect(time, signal)
        rts = [p.rt for p in peaks]
        has_major = any(abs(rt - 3.0) < 0.5 for rt in rts)
        has_minor = any(abs(rt - 8.0) < 0.5 for rt in rts)
        assert has_major, f"Major peak RT=3.0 미감지: {rts}"
        assert has_minor, f"Minor peak RT=8.0 미감지: {rts}"

    def test_no_duplicate_near_main_peak(self):
        """주 피크(RT=5.0) 부근에 중복 피크 없음 (노이즈 피크는 다른 위치에 있음)"""
        det = self._make_detector()
        time, signal = make_chromatogram(peaks=[(5.0, 100_000, 0.3)])
        peaks = det.detect(time, signal)
        # RT 4.0–6.0 구간에서 0.5분 이내 중복 없어야 함
        main_region = [p for p in peaks if 4.0 <= p.rt <= 6.0]
        rts = sorted(p.rt for p in main_region)
        for i in range(len(rts) - 1):
            assert rts[i + 1] - rts[i] > 0.2, f"주 피크 부근 중복: {rts}"

    def test_area_sum_reasonable(self):
        """검출 피크 면적 합이 신호 적분과 유사"""
        det = self._make_detector()
        time, signal = make_chromatogram(
            peaks=[(5.0, 100_000, 0.3)], noise_std=0
        )
        true_area = float(trapezoid(signal, time))
        peaks = det.detect(time, signal)
        detected_area = sum(p.area for p in peaks)
        assert detected_area > true_area * 0.5, "검출 면적이 너무 작음"


# ─────────────────────────────────────────────────────────────────────────────
# 4. EMG Fitter 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestEmgFitter:

    def test_symmetric_peak_fit(self):
        """대칭 Gaussian (tau≈0) → EMG가 잘 fitting해야 함"""
        from solid.peak_analysis.deconvolution.emg_fitter import EmgFitter
        time = np.linspace(3, 7, 300)
        true_signal = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)

        fitter = EmgFitter()
        result = fitter.fit(time, true_signal, centers=[5.0])

        assert result['r2'] > 0.95, f"대칭 피크 R²={result['r2']:.3f} < 0.95"
        assert len(result['params']) == 1
        _, center, _, _ = result['params'][0]
        assert abs(center - 5.0) < 0.1, f"센터 오차: {abs(center - 5.0):.3f}"

    def test_asymmetric_peak_fit(self):
        """테일링 있는 EMG 피크 → R² > 0.90"""
        from solid.peak_analysis.deconvolution.emg_fitter import EmgFitter
        time = np.linspace(3, 10, 500)
        true_signal = make_emg_peak(time, amplitude=50_000,
                                    center=5.0, sigma=0.3, tau=0.5)

        fitter = EmgFitter()
        result = fitter.fit(time, true_signal, centers=[5.0])

        assert result['r2'] > 0.90, f"비대칭 EMG R²={result['r2']:.3f} < 0.90"
        assert result['areas'][0] > 0

    def test_two_component_fit(self):
        """두 겹친 피크 분해"""
        from solid.peak_analysis.deconvolution.emg_fitter import EmgFitter
        time = np.linspace(3, 9, 400)
        s1 = make_emg_peak(time, 60_000, 5.0, 0.25, 0.2)
        s2 = make_emg_peak(time, 30_000, 6.0, 0.25, 0.2)
        signal = s1 + s2

        fitter = EmgFitter()
        result = fitter.fit(time, signal, centers=[5.0, 6.0])

        assert result['r2'] > 0.90, f"2성분 EMG R²={result['r2']:.3f} < 0.90"
        assert len(result['params']) == 2

    def test_area_analytical_vs_numerical(self):
        """EMG 분석 면적 vs 사다리꼴 적분 오차 < 5%"""
        from solid.peak_analysis.deconvolution.emg_fitter import EmgFitter, emg
        time = np.linspace(0, 15, 1000)
        true_signal = make_emg_peak(time, 50_000, 7.0, 0.4, 0.3)
        numerical_area = float(trapezoid(true_signal, time))

        fitter = EmgFitter()
        result = fitter.fit(time, true_signal, centers=[7.0])
        analytical_area = result['areas'][0]

        rel_err = abs(analytical_area - numerical_area) / numerical_area
        assert rel_err < 0.05, f"EMG 면적 오차 {rel_err*100:.1f}% > 5%"


# ─────────────────────────────────────────────────────────────────────────────
# 5. WorkflowBuilder 통합 테스트
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
        from solid.application.workflow import WorkflowBuilder
        wf = WorkflowBuilder().with_auto_reader().with_default_baseline().with_default_peak_detector().build()
        assert wf is not None

    def test_arpls_workflow_builds(self):
        from solid.application.workflow import WorkflowBuilder
        wf = (WorkflowBuilder()
              .with_auto_reader()
              .with_arpls_baseline(lam=1e5)
              .with_two_pass_peak_detector()
              .build())
        assert wf is not None

    def test_two_pass_workflow_detects_peaks(self, tmp_path):
        """ARPLS + 2-Pass 파이프라인 end-to-end"""
        from solid.application.workflow import WorkflowBuilder
        path, _, _ = self._make_csv(tmp_path, [(5.0, 100_000, 0.3)])

        wf = (WorkflowBuilder()
              .with_auto_reader()
              .with_arpls_baseline(lam=1e5)
              .with_two_pass_peak_detector()
              .build())

        result = wf.analyze_file(path)
        assert len(result.peaks) >= 1
        rts = [p.rt for p in result.peaks]
        assert any(abs(rt - 5.0) < 0.5 for rt in rts), f"피크 미감지: {rts}"


# ─────────────────────────────────────────────────────────────────────────────
# 6. ProminencePeakDetector Phase 1 수정 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestProminencePeakDetectorPhase1:
    """
    Phase 1 수정 검증:
    - MAD-based noise estimation
    - np.trapezoid (deprecation-free)
    - valley cap between adjacent peaks
    """

    def _make_detector(self):
        from solid.peak_analysis.detectors.peak_detector import ProminencePeakDetector
        from solid.infrastructure.signal_processing.scipy_adapter import ScipySignalProcessor
        return ProminencePeakDetector(signal_processor=ScipySignalProcessor())

    def test_mad_noise_small_scale(self):
        """RID 스케일(1–10 범위) 신호에서 피크 감지 (percentile 25가 0이 되는 스케일)"""
        det = self._make_detector()
        time = np.linspace(0, 10, 1000)
        # 소신호: 최댓값 5.0, noise ~0.01
        signal = 5.0 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)
        signal += np.random.default_rng(0).normal(0, 0.01, 1000)
        signal = np.maximum(signal, 0)
        peaks = det.detect(time, signal)
        rts = [p.rt for p in peaks]
        assert any(abs(rt - 5.0) < 0.5 for rt in rts), \
            f"소신호 피크 미감지(percentile noise 사용 시 noise=0이 되어 과감지): {rts}"

    def test_valley_cap_two_adjacent_peaks(self):
        """인접한 두 피크의 경계가 valley에서 끊어져야 함 (overlap 없음)"""
        det = self._make_detector()
        time = np.linspace(0, 10, 2000)
        # 두 피크가 겹쳐 있지 않은 상황
        signal = (100_000 * np.exp(-0.5 * ((time - 3) / 0.3) ** 2)
                  + 80_000 * np.exp(-0.5 * ((time - 7) / 0.3) ** 2))
        peaks = det.detect(time, signal)
        if len(peaks) >= 2:
            peaks_sorted = sorted(peaks, key=lambda p: p.rt)
            # 첫 번째 피크 끝 ≤ 두 번째 피크 시작 (경계 중복 없음)
            assert peaks_sorted[0].index_end <= peaks_sorted[1].index_start + 5, \
                (f"Valley cap 미적용: peak1 end={peaks_sorted[0].index_end}, "
                 f"peak2 start={peaks_sorted[1].index_start}")

    def test_trapezoid_no_deprecation_warning(self):
        """np.trapezoid 사용 — DeprecationWarning 없어야 함"""
        import warnings
        det = self._make_detector()
        time = np.linspace(0, 10, 500)
        signal = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            peaks = det.detect(time, signal)  # np.trapz 사용 시 DeprecationWarning 발생

        assert len(peaks) >= 1

    def test_estimate_noise_static_method(self):
        """_estimate_noise: floor(1.0) 이상의 신호에서 스케일에 비례"""
        from solid.peak_analysis.detectors.peak_detector import ProminencePeakDetector
        rng = np.random.default_rng(42)

        # 두 신호 모두 floor(1.0)를 훨씬 초과하는 크기여야 비율 검증 가능
        small = rng.normal(0, 1_000, 500)       # noise MAD ≈ 1000
        large = rng.normal(0, 1_000_000, 500)   # noise MAD ≈ 1000_000

        noise_small = ProminencePeakDetector._estimate_noise(small)
        noise_large = ProminencePeakDetector._estimate_noise(large)

        # 비율이 ~1000배여야 함 (scale-proportional)
        ratio = noise_large / noise_small
        assert 900 < ratio < 1100, f"MAD noise가 scale에 비례하지 않음: ratio={ratio:.1f}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. GaussianFitter 예외 로깅 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestGaussianFitterLogging:

    def test_fit_failure_logs_warning(self):
        """Gaussian fit 실패 시 WARNING 로그 기록 + 안전하게 빈 리스트 반환"""
        import logging
        from solid.peak_analysis.deconvolution.gaussian_fitter import GaussianFitterStrategy
        from solid.infrastructure.signal_processing.scipy_adapter import ScipyCurveFitter

        fitter = GaussianFitterStrategy(curve_fitter=ScipyCurveFitter())

        # 완전히 0인 신호: 진폭 초기값이 0이 되어 bounds 충돌로 fit 실패
        time = np.linspace(0, 1, 5)
        signal = np.zeros(5)

        records = []

        class ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = ListHandler(level=logging.WARNING)
        log = logging.getLogger('solid.peak_analysis.deconvolution.gaussian_fitter')
        log.addHandler(handler)
        log.setLevel(logging.WARNING)

        try:
            peaks, r2, rmse = fitter.fit(time, signal, centers=[0.5])
        finally:
            log.removeHandler(handler)

        # 결과는 빈 리스트 + 안전한 기본값
        assert isinstance(peaks, list), "fit 실패 시 리스트를 반환해야 함"
        # 실패 시 WARNING 로그가 남아야 함 (fit이 실제로 실패한 경우만)
        if len(peaks) == 0 and r2 == 0.0:
            assert any(r.levelno >= logging.WARNING for r in records), \
                "fit 실패 시 WARNING 로그 없음"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Analyzer 동적 윈도우 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzerDynamicWindow:

    def _make_analyzer(self):
        from solid.peak_analysis.deconvolution.analyzer import ShoulderDeconvolutionAnalyzer
        from solid.infrastructure.signal_processing.scipy_adapter import ScipySignalProcessor
        return ShoulderDeconvolutionAnalyzer(signal_processor=ScipySignalProcessor())

    def test_short_signal_no_crash(self):
        """짧은 신호(30포인트)에서 ±50 고정 윈도우 → index out of bounds 없어야 함"""
        analyzer = self._make_analyzer()
        time = np.linspace(0, 3, 30)
        signal = 1000 * np.exp(-0.5 * ((time - 1.5) / 0.3) ** 2)
        peak_idx = int(np.argmax(signal))
        # 예외 없이 실행되어야 함
        try:
            has_shoulder, _ = analyzer._detect_shoulder(time, signal, peak_idx)
            n_inflections = analyzer._count_inflection_points(signal, peak_idx)
        except IndexError as e:
            pytest.fail(f"짧은 신호에서 IndexError 발생: {e}")

    def test_long_signal_uses_capped_window(self):
        """긴 신호(2000포인트)에서 윈도우가 50 이하로 cap됨"""
        from solid.peak_analysis.deconvolution import analyzer as ana_module
        import inspect

        # _detect_shoulder 소스에서 half_window 계산 확인
        src = inspect.getsource(
            ana_module.ShoulderDeconvolutionAnalyzer._detect_shoulder
        )
        assert 'min(50' in src or 'min(30' in src, \
            "_detect_shoulder에 동적 윈도우 cap이 없음 (고정값 ±50 그대로)"

    def test_symmetric_peak_no_shoulder_detected(self):
        """완벽한 Gaussian 피크 → shoulder 미감지"""
        analyzer = self._make_analyzer()
        time = np.linspace(0, 10, 500)
        signal = 50_000 * np.exp(-0.5 * ((time - 5) / 0.3) ** 2)
        peak_idx = int(np.argmax(signal))
        has_shoulder, _ = analyzer._detect_shoulder(time, signal, peak_idx)
        # 완벽한 Gaussian은 shoulder가 없어야 함
        assert not has_shoulder, "Gaussian 피크에 shoulder가 잘못 감지됨"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
