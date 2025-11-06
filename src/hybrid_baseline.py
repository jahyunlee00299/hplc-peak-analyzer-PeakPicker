"""
Hybrid Baseline Correction
Valley points와 Local Minimum을 결합한 고급 베이스라인 보정
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import interp1d, UnivariateSpline
from scipy.integrate import trapezoid
from typing import List, Tuple, Dict
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class BaselinePoint:
    """베이스라인 앵커 포인트"""
    index: int
    value: float
    type: str  # 'valley', 'local_min', 'boundary'
    confidence: float  # 0-1, 높을수록 신뢰도 높음


class HybridBaselineCorrector:
    """Valley와 Local Minimum을 결합한 하이브리드 베이스라인 보정"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        self.time = time
        self.intensity = intensity
        self.baseline_points = []

    def find_baseline_anchor_points(
        self,
        valley_prominence: float = 0.01,
        local_window: int = None,
        percentile: float = 10,
        min_distance: int = 10
    ) -> List[BaselinePoint]:
        """
        Valley와 Local Minimum을 결합하여 최적의 베이스라인 앵커 포인트 찾기
        """
        baseline_points = []

        # 1. Valley points 찾기
        valleys = self._find_valleys(valley_prominence)
        for v_idx in valleys:
            baseline_points.append(BaselinePoint(
                index=v_idx,
                value=self.intensity[v_idx],
                type='valley',
                confidence=1.0  # Valley는 높은 신뢰도
            ))

        # 2. Local minimum points 찾기 (valley 사이 구간에서)
        if local_window is None:
            local_window = max(20, len(self.intensity) // 50)

        # Valley 사이 각 구간에서 local minimum 찾기
        valleys_extended = np.concatenate(([0], valleys, [len(self.intensity)-1]))

        for i in range(len(valleys_extended) - 1):
            start = valleys_extended[i]
            end = valleys_extended[i + 1]

            if end - start > local_window:
                # 이 구간을 작은 윈도우로 나누어 local minima 찾기
                for win_start in range(start, end, local_window // 2):
                    win_end = min(win_start + local_window, end)
                    segment = self.intensity[win_start:win_end]

                    if len(segment) > 0:
                        # 구간 내 하위 percentile 점들
                        threshold = np.percentile(segment, percentile)
                        min_mask = segment <= threshold

                        if np.any(min_mask):
                            # 가장 낮은 점 선택
                            local_min_idx = win_start + np.argmin(segment)

                            # Valley와 너무 가까우면 스킵
                            if all(abs(local_min_idx - v) > min_distance for v in valleys):
                                # 신뢰도는 주변 기울기로 계산 (평평할수록 높음)
                                if local_min_idx > 0 and local_min_idx < len(self.intensity) - 1:
                                    gradient = abs(self.intensity[local_min_idx + 1] -
                                                 self.intensity[local_min_idx - 1])
                                    confidence = 1.0 / (1.0 + gradient)
                                else:
                                    confidence = 0.5

                                baseline_points.append(BaselinePoint(
                                    index=local_min_idx,
                                    value=self.intensity[local_min_idx],
                                    type='local_min',
                                    confidence=confidence
                                ))

        # 3. 시작과 끝 점 추가
        if 0 not in [p.index for p in baseline_points]:
            baseline_points.append(BaselinePoint(
                index=0,
                value=self.intensity[0],
                type='boundary',
                confidence=0.8
            ))

        if len(self.intensity) - 1 not in [p.index for p in baseline_points]:
            baseline_points.append(BaselinePoint(
                index=len(self.intensity) - 1,
                value=self.intensity[-1],
                type='boundary',
                confidence=0.8
            ))

        # 인덱스로 정렬
        baseline_points.sort(key=lambda p: p.index)

        # 중복 제거 (가까운 점들 중 confidence 높은 것 선택)
        filtered_points = []
        for point in baseline_points:
            too_close = False
            for existing in filtered_points:
                if abs(point.index - existing.index) < min_distance:
                    too_close = True
                    # 더 높은 confidence를 가진 점으로 교체
                    if point.confidence > existing.confidence:
                        filtered_points.remove(existing)
                        filtered_points.append(point)
                    break

            if not too_close:
                filtered_points.append(point)

        filtered_points.sort(key=lambda p: p.index)
        self.baseline_points = filtered_points
        return filtered_points

    def _find_valleys(self, prominence_factor: float = 0.01) -> np.ndarray:
        """Valley (골짜기) 지점 찾기"""
        # 스무딩
        window = min(21, len(self.intensity) // 20)
        if window % 2 == 0:
            window += 1

        if len(self.intensity) > window:
            smoothed = signal.savgol_filter(self.intensity, window, 3)
        else:
            smoothed = self.intensity.copy()

        # 역 피크 찾기 (valleys)
        inverted = -smoothed
        valleys, _ = signal.find_peaks(
            inverted,
            prominence=np.ptp(smoothed) * prominence_factor,
            distance=window
        )

        return valleys

    def generate_hybrid_baseline(
        self,
        method: str = 'weighted_spline',
        smooth_factor: float = 0.5
    ) -> np.ndarray:
        """
        앵커 포인트들로부터 베이스라인 생성

        Methods:
        - weighted_spline: confidence 가중치를 적용한 스플라인
        - adaptive_connect: 구간별 적응형 연결
        - robust_fit: outlier에 강한 피팅
        """
        if len(self.baseline_points) == 0:
            self.find_baseline_anchor_points()

        indices = np.array([p.index for p in self.baseline_points])
        values = np.array([p.value for p in self.baseline_points])
        confidences = np.array([p.confidence for p in self.baseline_points])
        types = [p.type for p in self.baseline_points]

        baseline = np.zeros_like(self.intensity)

        if method == 'weighted_spline':
            # Confidence를 가중치로 사용한 스플라인 피팅
            if len(indices) > 3:
                # 가중치 기반 스무싱 팩터
                weights = confidences
                s = len(indices) * smooth_factor * (1 - np.mean(confidences) * 0.5)

                try:
                    spl = UnivariateSpline(indices, values, w=weights, s=s, k=3)
                    baseline = spl(np.arange(len(self.intensity)))
                except:
                    # Fallback to linear
                    f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
                    baseline = f(np.arange(len(self.intensity)))
            else:
                f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
                baseline = f(np.arange(len(self.intensity)))

        elif method == 'adaptive_connect':
            # 구간별로 다른 연결 방법 사용
            for i in range(len(indices) - 1):
                start_idx = indices[i]
                end_idx = indices[i + 1]

                # 양 끝점의 타입에 따라 연결 방법 결정
                if types[i] == 'valley' and types[i + 1] == 'valley':
                    # Valley to valley: 곡선 연결
                    x = [start_idx, (start_idx + end_idx) // 2, end_idx]
                    y = [values[i], (values[i] + values[i + 1]) / 2, values[i + 1]]

                    # 중간 지점을 구간 최소값으로 조정
                    mid_segment = self.intensity[start_idx:end_idx + 1]
                    y[1] = min(y[1], np.percentile(mid_segment, 5))

                    if len(x) >= 3:
                        f = interp1d(x, y, kind='quadratic', fill_value='extrapolate')
                        baseline[start_idx:end_idx + 1] = f(np.arange(start_idx, end_idx + 1))
                else:
                    # 그 외: 선형 연결
                    baseline[start_idx:end_idx + 1] = np.linspace(
                        values[i], values[i + 1], end_idx - start_idx + 1
                    )

        elif method == 'robust_fit':
            # RANSAC 스타일의 robust fitting
            # Outlier 앵커 포인트 제거
            if len(values) > 5:
                # MAD (Median Absolute Deviation) 계산
                median = np.median(values)
                mad = np.median(np.abs(values - median))
                threshold = median + 3 * mad

                # Outlier가 아닌 점들만 선택
                mask = values < threshold
                robust_indices = indices[mask]
                robust_values = values[mask]
                robust_weights = confidences[mask]

                if len(robust_indices) > 3:
                    spl = UnivariateSpline(
                        robust_indices,
                        robust_values,
                        w=robust_weights,
                        s=len(robust_indices) * smooth_factor,
                        k=min(3, len(robust_indices) - 1)
                    )
                    baseline = spl(np.arange(len(self.intensity)))
                else:
                    f = interp1d(robust_indices, robust_values, kind='linear', fill_value='extrapolate')
                    baseline = f(np.arange(len(self.intensity)))
            else:
                f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
                baseline = f(np.arange(len(self.intensity)))

        # 베이스라인이 신호 위로 가지 않도록
        baseline = np.minimum(baseline, self.intensity)

        # 부드럽게 만들기
        if len(baseline) > 21:
            baseline = signal.savgol_filter(baseline, 21, 3)
            baseline = np.minimum(baseline, self.intensity)

        return baseline

    def optimize_baseline(self) -> Tuple[np.ndarray, Dict]:
        """
        여러 파라미터 조합을 시도하여 최적 베이스라인 찾기
        """
        best_score = -np.inf
        best_baseline = None
        best_params = {}

        # 파라미터 조합
        param_combinations = [
            {'valley_prominence': 0.005, 'percentile': 5, 'method': 'weighted_spline'},
            {'valley_prominence': 0.01, 'percentile': 10, 'method': 'weighted_spline'},
            {'valley_prominence': 0.02, 'percentile': 15, 'method': 'adaptive_connect'},
            {'valley_prominence': 0.01, 'percentile': 10, 'method': 'robust_fit'},
        ]

        for params in param_combinations:
            # 앵커 포인트 찾기
            self.find_baseline_anchor_points(
                valley_prominence=params['valley_prominence'],
                percentile=params['percentile']
            )

            # 베이스라인 생성
            baseline = self.generate_hybrid_baseline(method=params['method'])
            corrected = self.intensity - baseline

            # 평가 점수 계산
            score = self._evaluate_baseline(baseline, corrected)

            if score > best_score:
                best_score = score
                best_baseline = baseline
                best_params = params

        return best_baseline, best_params

    def _evaluate_baseline(self, baseline: np.ndarray, corrected: np.ndarray) -> float:
        """베이스라인 품질 평가"""
        # 1. 음수 값 비율 (적을수록 좋음)
        neg_ratio = np.sum(corrected < 0) / len(corrected)

        # 2. 베이스라인 부드러움
        smoothness = np.std(np.diff(baseline, 2))

        # 3. 피크 보존
        original_peaks = signal.find_peaks(self.intensity, prominence=np.ptp(self.intensity)*0.05)[0]
        if len(original_peaks) > 0:
            corrected_peaks = signal.find_peaks(corrected, prominence=np.ptp(corrected)*0.05)[0]
            peak_preservation = min(1.0, len(corrected_peaks) / len(original_peaks))
        else:
            peak_preservation = 1.0

        # 종합 점수
        score = (1 - neg_ratio) * 100 + peak_preservation * 50 - smoothness
        return score


def test_hybrid_baseline():
    """Hybrid 베이스라인 방법 테스트"""

    # 데이터 로드
    print("Loading datasets...")

    # EXPORT.CSV
    df1 = pd.read_csv('peakpicker/examples/EXPORT.CSV',
                      header=None, sep='\t', encoding='utf-16-le')
    time1 = df1[0].values
    intensity1 = df1[1].values
    if np.min(intensity1) < 0:
        intensity1 = intensity1 - np.min(intensity1)

    # sample_chromatogram.csv
    df2 = pd.read_csv('peakpicker/examples/sample_chromatogram.csv')
    time2 = df2['Time'].values
    intensity2 = df2['Intensity'].values

    # 시각화
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    for idx, (time, intensity, name) in enumerate([
        (time1, intensity1, 'EXPORT.CSV'),
        (time2, intensity2, 'sample_chromatogram')
    ]):
        print(f"\n{name}:")
        corrector = HybridBaselineCorrector(time, intensity)

        # 1. 앵커 포인트 찾기
        anchor_points = corrector.find_baseline_anchor_points()
        print(f"  Total anchor points: {len(anchor_points)}")
        print(f"    - Valleys: {sum(1 for p in anchor_points if p.type == 'valley')}")
        print(f"    - Local minima: {sum(1 for p in anchor_points if p.type == 'local_min')}")
        print(f"    - Boundaries: {sum(1 for p in anchor_points if p.type == 'boundary')}")

        # 앵커 포인트 시각화
        axes[idx, 0].plot(time, intensity, 'b-', alpha=0.6, label='Original')

        # 타입별로 다른 색상과 크기
        for point in anchor_points:
            if point.type == 'valley':
                color, size, marker = 'red', 50, 'v'
            elif point.type == 'local_min':
                color, size, marker = 'green', 30, 'o'
            else:  # boundary
                color, size, marker = 'orange', 40, 's'

            axes[idx, 0].scatter(
                time[point.index],
                point.value,
                c=color,
                s=size * point.confidence,  # confidence에 따라 크기 조정
                marker=marker,
                alpha=0.8,
                edgecolors='black',
                linewidths=0.5
            )

        axes[idx, 0].set_title(f'{name}\nAnchor Points')
        axes[idx, 0].set_xlabel('Time (min)')
        axes[idx, 0].set_ylabel('Intensity')
        axes[idx, 0].grid(True, alpha=0.3)

        # 범례 추가
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='red', label='Valley'),
            Patch(facecolor='green', label='Local Min'),
            Patch(facecolor='orange', label='Boundary')
        ]
        axes[idx, 0].legend(handles=legend_elements, loc='upper right', fontsize=8)

        # 2. 세 가지 방법으로 베이스라인 생성
        methods = ['weighted_spline', 'adaptive_connect', 'robust_fit']
        colors = ['red', 'green', 'blue']

        for method, color in zip(methods, colors):
            baseline = corrector.generate_hybrid_baseline(method=method)
            axes[idx, 1].plot(time, baseline, '--', color=color, alpha=0.7, label=method)

        axes[idx, 1].plot(time, intensity, 'k-', alpha=0.3, label='Original')
        axes[idx, 1].set_title(f'Baseline Methods Comparison')
        axes[idx, 1].set_xlabel('Time (min)')
        axes[idx, 1].set_ylabel('Intensity')
        axes[idx, 1].legend(fontsize=8)
        axes[idx, 1].grid(True, alpha=0.3)

        # 3. 최적화된 베이스라인
        best_baseline, best_params = corrector.optimize_baseline()
        corrected = intensity - best_baseline

        axes[idx, 2].plot(time, intensity, 'b-', alpha=0.3, label='Original')
        axes[idx, 2].plot(time, best_baseline, 'r--', alpha=0.8, label='Optimized Baseline')
        axes[idx, 2].fill_between(time, 0, corrected, alpha=0.5, color='green', label='Corrected')

        # 피크 검출
        peaks, _ = signal.find_peaks(
            corrected,
            prominence=np.ptp(corrected) * 0.05,
            height=np.std(corrected) * 2
        )

        if len(peaks) > 0:
            axes[idx, 2].scatter(time[peaks], corrected[peaks],
                              color='red', s=50, zorder=5, marker='^', label=f'{len(peaks)} peaks')

            # RT 표시
            for peak in peaks[:5]:  # 처음 5개만
                axes[idx, 2].annotate(
                    f'{time[peak]:.1f}',
                    xy=(time[peak], corrected[peak]),
                    xytext=(time[peak], corrected[peak] + np.max(corrected)*0.05),
                    fontsize=7,
                    ha='center'
                )

        # Adjust y-axis to show full peaks
        y_max = max(np.max(intensity), np.max(corrected)) * 1.15
        y_min = min(0, np.min(corrected)) - y_max * 0.05
        axes[idx, 2].set_ylim(y_min, y_max)

        axes[idx, 2].set_title(f'Optimized Result\n{best_params}')
        axes[idx, 2].set_xlabel('Time (min)')
        axes[idx, 2].set_ylabel('Intensity')
        axes[idx, 2].legend(fontsize=8)
        axes[idx, 2].grid(True, alpha=0.3)

        print(f"  Best method: {best_params.get('method', 'N/A')}")
        print(f"  Detected peaks: {len(peaks)}")
        if len(peaks) > 0:
            print(f"  Peak RTs: {[f'{time[p]:.2f}' for p in peaks[:5]]}")

    plt.suptitle('Hybrid Baseline Correction (Valley + Local Minimum)', fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig('hybrid_baseline_results.png', dpi=100, bbox_inches='tight')
    plt.show()

    print("\n" + "="*60)
    print("HYBRID BASELINE ANALYSIS COMPLETE")
    print("="*60)
    print("\nKey Features:")
    print("  - Combines valley detection and local minimum search")
    print("  - Confidence-weighted anchor points")
    print("  - Multiple connection methods (spline, adaptive, robust)")
    print("  - Automatic parameter optimization")
    print("\nResult saved: hybrid_baseline_results.png")


if __name__ == "__main__":
    test_hybrid_baseline()