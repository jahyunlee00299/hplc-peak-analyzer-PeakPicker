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
        smooth_factor: float = 0.5,
        enhanced_smoothing: bool = True
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
                # 가중치 기반 스무싱 팩터 (강화된 스무딩)
                weights = confidences
                if enhanced_smoothing:
                    # 스무딩 강화: smooth_factor를 3배 증가
                    s = len(indices) * smooth_factor * 3.0 * (1 - np.mean(confidences) * 0.5)
                else:
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
                    # 스무딩 강화
                    if enhanced_smoothing:
                        s = len(robust_indices) * smooth_factor * 3.0
                    else:
                        s = len(robust_indices) * smooth_factor

                    spl = UnivariateSpline(
                        robust_indices,
                        robust_values,
                        w=robust_weights,
                        s=s,
                        k=min(3, len(robust_indices) - 1)
                    )
                    baseline = spl(np.arange(len(self.intensity)))
                else:
                    f = interp1d(robust_indices, robust_values, kind='linear', fill_value='extrapolate')
                    baseline = f(np.arange(len(self.intensity)))
            else:
                f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
                baseline = f(np.arange(len(self.intensity)))

        # 베이스라인 제약 제거: 음수 피크를 위해 신호 위로 갈 수 있음
        # baseline = np.minimum(baseline, self.intensity)  # 주석 처리

        # 부드럽게 만들기 (강화된 스무딩)
        if len(baseline) > 21:
            if enhanced_smoothing:
                # 1차 스무딩: savgol_filter
                baseline = signal.savgol_filter(baseline, 21, 3)
                # 2차 스무딩: 이동 평균 (추가)
                window = 15
                baseline = np.convolve(baseline, np.ones(window)/window, mode='same')
            else:
                baseline = signal.savgol_filter(baseline, 21, 3)
            # baseline = np.minimum(baseline, self.intensity)  # 주석 처리

        return baseline

    def post_process_corrected_signal(
        self,
        corrected: np.ndarray,
        clip_negative: bool = True,
        negative_threshold: float = -50.0
    ) -> np.ndarray:
        """
        보정된 신호의 후처리

        Args:
            corrected: 베이스라인 보정 후 신호
            clip_negative: 음수 값을 0으로 클리핑할지 여부
            negative_threshold: 이 값보다 작은 음수는 실제 음수 피크로 간주하고 보존

        Returns:
            후처리된 신호
        """
        processed = corrected.copy()

        if clip_negative:
            # 음수 영역 분석
            negative_mask = processed < 0

            if np.any(negative_mask):
                # 연속된 음수 영역 찾기
                regions = []
                in_region = False
                start = 0

                for i, val in enumerate(negative_mask):
                    if val and not in_region:
                        start = i
                        in_region = True
                    elif not val and in_region:
                        regions.append((start, i-1))
                        in_region = False

                if in_region:
                    regions.append((start, len(negative_mask)-1))

                # 각 음수 영역 검사
                for start, end in regions:
                    region_values = processed[start:end+1]
                    min_val = np.min(region_values)
                    region_size = end - start + 1

                    # 작고 얕은 음수 영역만 클리핑
                    # 조건: 최소값이 threshold보다 크고 (얕음), 크기가 작음
                    if min_val > negative_threshold and region_size < 100:
                        # 0으로 클리핑
                        processed[start:end+1] = np.maximum(processed[start:end+1], 0)
                    # 크고 깊은 음수 영역은 실제 음수 피크로 보존

        return processed

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

    def apply_linear_baseline_to_peaks(self, baseline: np.ndarray, detected_peaks: List[int]) -> np.ndarray:
        """
        검출된 피크 영역에 직선 베이스라인 적용
        기울기가 너무 급격하면 앵커 포인트를 양쪽으로 확장하여 기울기 완화

        Args:
            baseline: 원본 베이스라인
            detected_peaks: 검출된 피크의 인덱스 리스트

        Returns:
            피크 영역에 직선 베이스라인이 적용된 베이스라인
        """
        linear_baseline = baseline.copy()

        for peak_idx in detected_peaks:
            # 피크 너비 추정 (half-height method)
            peak_height = self.intensity[peak_idx] - baseline[peak_idx]
            half_height = baseline[peak_idx] + peak_height / 2

            # 왼쪽 경계 찾기
            left_idx = peak_idx
            while left_idx > 0 and self.intensity[left_idx] > half_height:
                left_idx -= 1

            # 오른쪽 경계 찾기
            right_idx = peak_idx
            while right_idx < len(self.intensity) - 1 and self.intensity[right_idx] > half_height:
                right_idx += 1

            # 초기 앵커 포인트
            anchor_left = left_idx
            anchor_right = right_idx

            # 기울기 완화: 너무 급격하면 앵커 포인트 확장
            if right_idx > left_idx:
                baseline_left = max(0, baseline[anchor_left])
                baseline_right = max(0, baseline[anchor_right])

                # 시간 간격 계산
                time_diff = self.time[anchor_right] - self.time[anchor_left]
                if time_diff > 0:
                    # 초기 기울기 계산 (강도/시간)
                    current_slope = abs(baseline_right - baseline_left) / time_diff

                    # 피크 높이 대비 기울기 비율로 급격함 판단
                    peak_range = np.ptp(self.intensity)
                    # 매우 엄격한 임계값: 전체 범위의 1% 이상이면 평평하지 않음
                    slope_threshold = peak_range * 0.01

                    # RT 기준으로 확장 (시간 간격 기준)
                    rt_expansion_step = 0.1  # 0.1분(6초)씩 양쪽으로 확장
                    max_rt_expansion = 5.0  # 최대 5분까지 확장
                    total_expansion = 0.0

                    iteration_count = 0
                    max_iterations = 100  # 최대 반복 횟수 증가

                    # 기울기가 거의 평평해질 때까지 반복
                    while current_slope > slope_threshold and total_expansion < max_rt_expansion and iteration_count < max_iterations:
                        # 현재 RT 범위
                        current_rt_left = self.time[anchor_left]
                        current_rt_right = self.time[anchor_right]

                        # RT 기준으로 확장할 새로운 위치 찾기
                        target_rt_left = current_rt_left - rt_expansion_step
                        target_rt_right = current_rt_right + rt_expansion_step

                        # RT를 인덱스로 변환
                        new_left = anchor_left
                        for i in range(anchor_left - 1, -1, -1):
                            if self.time[i] <= target_rt_left:
                                new_left = i
                                break

                        new_right = anchor_right
                        for i in range(anchor_right + 1, len(self.time)):
                            if self.time[i] >= target_rt_right:
                                new_right = i
                                break

                        # 더 이상 확장할 수 없으면 중단
                        if new_left == anchor_left and new_right == anchor_right:
                            break

                        # 확장된 위치의 베이스라인 값
                        new_baseline_left = max(0, baseline[new_left])
                        new_baseline_right = max(0, baseline[new_right])

                        # 새로운 기울기 계산
                        new_time_diff = self.time[new_right] - self.time[new_left]
                        if new_time_diff > 0:
                            new_slope = abs(new_baseline_right - new_baseline_left) / new_time_diff

                            # 기울기가 완화되었거나 거의 평평하면 적용
                            if new_slope < current_slope or new_slope <= slope_threshold:
                                anchor_left = new_left
                                anchor_right = new_right
                                baseline_left = new_baseline_left
                                baseline_right = new_baseline_right
                                current_slope = new_slope

                                # 거의 평평하면 조기 종료
                                if new_slope <= slope_threshold:
                                    break
                            else:
                                # 기울기가 더 나빠지면 중단
                                break

                        total_expansion += rt_expansion_step
                        iteration_count += 1

                # 최종 검증: 기울기가 여전히 너무 가파르면 원본 베이스라인 유지
                # 최대 허용 기울기: 전체 범위의 2% (1%보다 약간 여유)
                max_allowed_slope = peak_range * 0.02

                if current_slope <= max_allowed_slope:
                    # 기울기가 충분히 완화되었으면 직선 베이스라인 적용
                    linear_baseline[anchor_left:anchor_right+1] = np.linspace(
                        baseline_left, baseline_right, anchor_right - anchor_left + 1
                    )
                else:
                    # 기울기가 여전히 너무 가파르면 원본 베이스라인 유지
                    # 이 피크에 대해서는 직선 베이스라인을 적용하지 않음
                    pass

        return linear_baseline

    def compare_baselines_by_peak_width(
        self,
        baseline_robust: np.ndarray,
        baseline_weighted: np.ndarray
    ) -> Tuple[np.ndarray, Dict]:
        """
        robust_fit과 weighted_spline을 피크별로 비교하여 더 넓은 피크 너비를 제공하는 방법 선택

        Args:
            baseline_robust: robust_fit 방법으로 생성한 베이스라인
            baseline_weighted: weighted_spline 방법으로 생성한 베이스라인

        Returns:
            최적 베이스라인과 선택 정보
        """
        # 두 베이스라인으로 보정된 신호
        corrected_robust = np.maximum(self.intensity - baseline_robust, 0)
        corrected_weighted = np.maximum(self.intensity - baseline_weighted, 0)

        # 피크 검출
        noise_level_robust = np.percentile(corrected_robust, 25) * 1.5
        noise_level_weighted = np.percentile(corrected_weighted, 25) * 1.5

        peaks_robust, props_robust = signal.find_peaks(
            corrected_robust,
            prominence=np.ptp(corrected_robust) * 0.005,
            height=noise_level_robust * 3,
            width=0
        )

        peaks_weighted, props_weighted = signal.find_peaks(
            corrected_weighted,
            prominence=np.ptp(corrected_weighted) * 0.005,
            height=noise_level_weighted * 3,
            width=0
        )

        # 피크별로 비교
        hybrid_baseline = baseline_weighted.copy()  # 기본은 weighted 사용
        selection_info = {
            'robust_peaks': len(peaks_robust),
            'weighted_peaks': len(peaks_weighted),
            'robust_selected_count': 0,
            'weighted_selected_count': 0,
            'selections': []
        }

        # 모든 피크 위치를 찾기 (robust + weighted 통합)
        all_peak_positions = set(peaks_robust.tolist() + peaks_weighted.tolist())

        for peak_pos in all_peak_positions:
            # robust에서 이 피크의 너비
            width_robust = 0
            if peak_pos in peaks_robust:
                idx_robust = np.where(peaks_robust == peak_pos)[0][0]
                width_robust = props_robust['widths'][idx_robust] if 'widths' in props_robust else 0

            # weighted에서 이 피크의 너비
            width_weighted = 0
            if peak_pos in peaks_weighted:
                idx_weighted = np.where(peaks_weighted == peak_pos)[0][0]
                width_weighted = props_weighted['widths'][idx_weighted] if 'widths' in props_weighted else 0

            # 더 넓은 너비를 가진 방법 선택
            if width_robust > width_weighted:
                # robust가 더 넓음 - 피크 영역에서 robust 베이스라인 사용
                peak_height = self.intensity[peak_pos] - baseline_robust[peak_pos]
                half_height = baseline_robust[peak_pos] + peak_height / 2

                left_idx = peak_pos
                while left_idx > 0 and self.intensity[left_idx] > half_height:
                    left_idx -= 1

                right_idx = peak_pos
                while right_idx < len(self.intensity) - 1 and self.intensity[right_idx] > half_height:
                    right_idx += 1

                hybrid_baseline[left_idx:right_idx+1] = baseline_robust[left_idx:right_idx+1]
                selection_info['robust_selected_count'] += 1
                selection_info['selections'].append({
                    'rt': self.time[peak_pos],
                    'method': 'robust',
                    'width_robust': width_robust,
                    'width_weighted': width_weighted
                })
            else:
                selection_info['weighted_selected_count'] += 1
                selection_info['selections'].append({
                    'rt': self.time[peak_pos],
                    'method': 'weighted',
                    'width_robust': width_robust,
                    'width_weighted': width_weighted
                })

        return hybrid_baseline, selection_info

    def optimize_baseline_with_linear_peaks(self) -> Tuple[np.ndarray, Dict]:
        """
        피크 영역에 직선 베이스라인을 적용하고, robust vs weighted를 피크 너비로 비교

        Returns:
            최적 베이스라인과 파라미터 정보
        """
        # 앵커 포인트 찾기
        self.find_baseline_anchor_points(
            valley_prominence=0.01,
            percentile=10
        )

        # robust_fit과 weighted_spline 방법으로 베이스라인 생성
        baseline_robust = self.generate_hybrid_baseline(method='robust_fit')
        baseline_weighted = self.generate_hybrid_baseline(method='weighted_spline')

        # 피크 너비 비교하여 최적 베이스라인 선택
        hybrid_baseline, selection_info = self.compare_baselines_by_peak_width(
            baseline_robust, baseline_weighted
        )

        params = {
            'method': 'hybrid_width_comparison',
            'selection_info': selection_info
        }

        return hybrid_baseline, params


def test_hybrid_baseline():
    """Hybrid 베이스라인 방법 테스트"""

    # 데이터 로드
    print("Loading datasets...")

    # EXPORT.CSV
    df1 = pd.read_csv('peakpicker/examples/EXPORT.CSV',
                      header=None, sep='\t', encoding='utf-16-le')
    time1 = df1[0].values
    intensity1 = df1[1].values
    # 음수 값 보존: 음수 피크 검출을 위해 자동 변환 제거
    # if np.min(intensity1) < 0:
    #     intensity1 = intensity1 - np.min(intensity1)

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