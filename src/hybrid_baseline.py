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
        percentile: float = None,  # Adaptive percentile (None = auto)
        min_distance: int = 10
    ) -> List[BaselinePoint]:
        """
        Valley와 Local Minimum을 결합하여 최적의 베이스라인 앵커 포인트 찾기

        Parameters
        ----------
        valley_prominence : float
            Valley detection prominence factor
        local_window : int
            Window size for local minimum search
        percentile : float or None
            Percentile threshold for local minimum selection.
            If None, automatically determined based on signal characteristics.
        min_distance : int
            Minimum distance between anchor points
        """
        baseline_points = []

        # Adaptive percentile calculation based on signal characteristics
        if percentile is None:
            # Estimate noise level using MAD of signal derivative
            derivative = np.diff(self.intensity)
            noise_mad = np.median(np.abs(derivative - np.median(derivative)))
            signal_range = np.ptp(self.intensity)

            # Higher noise -> higher percentile (more conservative)
            # Lower noise -> lower percentile (more sensitive)
            if signal_range > 0:
                noise_ratio = noise_mad / signal_range
                if noise_ratio > 0.05:
                    # Noisy signal: use 10th percentile
                    percentile = 10
                elif noise_ratio > 0.02:
                    # Moderate noise: use 5th percentile
                    percentile = 5
                else:
                    # Low noise: use 2nd percentile
                    percentile = 2
            else:
                percentile = 5  # Default

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

        # Outlier 제거: 비정상적으로 낮은 값을 가진 앵커 포인트 필터링
        # Valley가 큰 피크 사이의 골짜기를 잘못 감지하는 경우 방지
        if len(filtered_points) > 5:
            values = np.array([p.value for p in filtered_points])
            median_value = np.median(values)
            mad = np.median(np.abs(values - median_value))

            # MAD 기반 outlier 감지 (median - 3*MAD 이하는 제거)
            # 신호 범위 대비 MAD가 작으면 stable baseline으로 판단
            signal_range = np.ptp(self.intensity)  # 전체 신호 범위
            relative_mad_threshold = signal_range * 0.02  # 신호 범위의 2%

            if mad < relative_mad_threshold:
                # Stable baseline: 10th percentile 이하 제거
                threshold = np.percentile(values, 10)
            else:
                # Variable baseline: median - 3*MAD 이하 제거
                threshold = median_value - 3 * mad

            filtered_points = [p for p in filtered_points if p.value >= threshold]

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
                # 가중치 기반 스무싱 팩터 - 앵커 포인트에서 크게 벗어나지 않도록 조절
                weights = confidences
                if enhanced_smoothing:
                    # 스무딩 강화: 5.0 -> 0.5로 감소
                    s = len(indices) * smooth_factor * 0.5 * (1 - np.mean(confidences) * 0.5)
                else:
                    s = len(indices) * smooth_factor * 0.1 * (1 - np.mean(confidences) * 0.5)

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
                    # 스무딩 강화 - 하지만 앵커 포인트에서 너무 벗어나지 않도록 조절
                    # 5.0 -> 0.5로 감소: s/n ratio를 2.5에서 0.25로 낮춤
                    if enhanced_smoothing:
                        s = len(robust_indices) * smooth_factor * 0.5
                    else:
                        s = len(robust_indices) * smooth_factor * 0.1

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

        # TEMPORARILY DISABLED: 베이스라인 안전 제약
        # 디버깅을 위해 임시로 비활성화
        # # 1. 초반 1-3분 구간을 기준 베이스라인으로 사용 (LC 특성)
        # reference_start_time = 1.0  # min
        # reference_end_time = 3.0    # min
        #
        # # 시간 범위를 인덱스로 변환
        # time_per_point = (self.time[-1] - self.time[0]) / len(self.time)
        # ref_start_idx = int(reference_start_time / time_per_point)
        # ref_end_idx = int(reference_end_time / time_per_point)
        #
        # if ref_start_idx < ref_end_idx < len(self.intensity):
        #     # 1-3분 구간의 낮은 값을 기준으로 사용 (10th percentile)
        #     reference_region = self.intensity[ref_start_idx:ref_end_idx]
        #     reference_baseline = np.percentile(reference_region, 10)
        #     reference_range = np.ptp(reference_region)  # 1-3분 구간 자체의 범위
        #
        #     # 베이스라인이 기준점에서 1-3분 구간 범위의 ±3배만큼 벗어나는 것 허용
        #     # 이는 피크가 있는 구간에서도 베이스라인이 합리적으로 유지되도록 함
        #     allowed_deviation = max(reference_range * 3.0, 1000)  # 최소 1000 허용
        #     lower_bound = reference_baseline - allowed_deviation
        #     upper_bound = reference_baseline + allowed_deviation * 2.0  # 위로는 더 여유
        #
        #     baseline = np.clip(baseline, lower_bound, upper_bound)

        # 2. 로컬 윈도우에서 원본 신호 범위를 초과하지 않도록 제한
        # DISABLED: 이 제약이 베이스라인을 너무 낮게 만들어서 제거
        # 앵커 포인트가 이미 올바른 베이스라인을 나타내므로 추가 제약 불필요
        # from scipy.ndimage import maximum_filter, minimum_filter
        # window_size = 201  # ~1분 윈도우
        # local_max = maximum_filter(self.intensity, size=window_size, mode='nearest')
        # local_min = minimum_filter(self.intensity, size=window_size, mode='nearest')
        # baseline = np.minimum(baseline, local_min * 1.0)

        # 음수 방지만 유지
        baseline = np.maximum(baseline, -50.0)

        # TEMPORARILY DISABLED: 스무딩 비활성화 (디버깅용)
        # # 부드럽게 만들기 (강화된 스무딩) - 마지막 구간 제외
        # if len(baseline) > 21 and len(self.baseline_points) >= 2:
        #     # 마지막 구간 인덱스 계산
        #     last_pt = self.baseline_points[-1]
        #     second_last_pt = self.baseline_points[-2]
        #     last_segment_start = second_last_pt.index
        #
        #     # 마지막 구간 제외하고 스무딩
        #     if last_segment_start > 21:
        #         if enhanced_smoothing:
        #             # 1차 스무딩: savgol_filter
        #             baseline[:last_segment_start] = signal.savgol_filter(baseline[:last_segment_start], 21, 3)
        #             # 2차 스무딩: 이동 평균 (추가)
        #             window = 15
        #             baseline[:last_segment_start] = np.convolve(
        #                 baseline[:last_segment_start],
        #                 np.ones(window)/window,
        #                 mode='same'
        #             )
        #         else:
        #             baseline[:last_segment_start] = signal.savgol_filter(baseline[:last_segment_start], 21, 3)

        # TEMPORARILY DISABLED: 마지막 구간 선형 보간 비활성화 (디버깅용)
        # # 마지막 구간 선형 보간으로 교체 (스플라인 발산 방지)
        # if len(self.baseline_points) >= 2:
        #     last_pt = self.baseline_points[-1]
        #     second_last_pt = self.baseline_points[-2]
        #
        #     # 마지막 두 앵커 포인트 사이를 선형 보간
        #     start_idx = second_last_pt.index
        #     end_idx = last_pt.index
        #
        #     if end_idx > start_idx:
        #         x_range = np.arange(start_idx, end_idx + 1)
        #         linear_baseline = np.interp(
        #             x_range,
        #             [start_idx, end_idx],
        #             [second_last_pt.value, last_pt.value]
        #         )
        #         baseline[start_idx:end_idx + 1] = linear_baseline

        # DISABLED: 이 제약들이 베이스라인을 파괴함
        # 앵커 포인트만 신뢰하고 추가 제약 제거
        # # 베이스라인이 원본 신호보다 충분히 낮게 유지되도록 제약
        # # 로컬 최소값의 50%로 제한하여 피크 베이스 보호
        # from scipy.ndimage import minimum_filter
        # local_min_final = minimum_filter(self.intensity, size=51, mode='nearest')
        # baseline = np.minimum(baseline, local_min_final * 0.5)
        #
        # # 추가로 원본 신호의 70%를 초과하지 않도록 (90% -> 70%)
        # baseline = np.minimum(baseline, self.intensity * 0.7)

        # 베이스라인이 과도하게 음수가 되지 않도록 제한만 유지
        # 작은 음수는 허용하되 (-50까지), 큰 음수는 방지
        baseline = np.maximum(baseline, -50.0)

        # 베이스라인이 원본 신호를 초과하지 않도록만 제한
        baseline = np.minimum(baseline, self.intensity)

        # 음수 영역 브릿지 처리: 신호가 음수로 내려가는 구간에서
        # 베이스라인이 따라 내려가지 않도록 직선으로 연결
        baseline = self.bridge_negative_regions(baseline, threshold_ratio=0.1)

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
        검출된 피크 영역에 선형(linear) 베이스라인 적용
        피크 양쪽의 실제 베이스라인 지점을 찾아 직선으로 연결

        Args:
            baseline: 원본 베이스라인
            detected_peaks: 검출된 피크의 인덱스 리스트

        Returns:
            피크 영역에 linear 베이스라인이 적용된 베이스라인
        """
        linear_baseline = baseline.copy()

        for peak_idx in detected_peaks:
            # 피크 높이 계산
            peak_height = self.intensity[peak_idx] - baseline[peak_idx]
            if peak_height <= 0:
                continue

            # 피크 베이스(1% 높이) 지점 찾기
            base_threshold = baseline[peak_idx] + peak_height * 0.01

            # 왼쪽 베이스 지점 찾기 - 신호가 베이스라인 근처로 내려가는 지점
            left_idx = peak_idx
            while left_idx > 0:
                # 신호가 베이스라인 + 1% 높이 이하로 내려가면 중지
                if self.intensity[left_idx] <= base_threshold:
                    break
                # 또는 신호가 베이스라인과 거의 같아지면 중지
                if self.intensity[left_idx] <= baseline[left_idx] * 1.02:
                    break
                left_idx -= 1

            # 오른쪽 베이스 지점 찾기
            right_idx = peak_idx
            while right_idx < len(self.intensity) - 1:
                if self.intensity[right_idx] <= base_threshold:
                    break
                if self.intensity[right_idx] <= baseline[right_idx] * 1.02:
                    break
                right_idx += 1

            # 피크 영역이 유효한 경우에만 처리
            if right_idx > left_idx + 5:
                # 실제 베이스라인 값 사용 (보간된 baseline이 아닌 원본 신호의 낮은 지점)
                # 피크 양쪽에서 가장 낮은 지점을 찾음
                search_range = 20  # 경계에서 20포인트 내에서 검색

                # 왼쪽 실제 베이스라인 값
                left_search_start = max(0, left_idx - search_range)
                left_search_end = left_idx + 5
                left_region = self.intensity[left_search_start:left_search_end]
                if len(left_region) > 0:
                    left_base_value = np.min(left_region)
                    left_base_idx = left_search_start + np.argmin(left_region)
                else:
                    left_base_value = baseline[left_idx]
                    left_base_idx = left_idx

                # 오른쪽 실제 베이스라인 값
                right_search_start = right_idx - 5
                right_search_end = min(len(self.intensity), right_idx + search_range)
                right_region = self.intensity[right_search_start:right_search_end]
                if len(right_region) > 0:
                    right_base_value = np.min(right_region)
                    right_base_idx = right_search_start + np.argmin(right_region)
                else:
                    right_base_value = baseline[right_idx]
                    right_base_idx = right_idx

                # 선형 보간으로 피크 아래 베이스라인 생성
                if right_base_idx > left_base_idx:
                    x_range = np.arange(left_base_idx, right_base_idx + 1)
                    linear_segment = np.interp(
                        x_range,
                        [left_base_idx, right_base_idx],
                        [left_base_value, right_base_value]
                    )
                    linear_baseline[left_base_idx:right_base_idx + 1] = linear_segment

        return linear_baseline

    def bridge_negative_regions(self, baseline: np.ndarray, threshold_ratio: float = 0.1) -> np.ndarray:
        """
        음수 영역이나 급격히 낮아지는 구간을 직선으로 연결

        신호가 음수로 내려가거나 비정상적으로 낮아지는 구간에서
        베이스라인이 따라 내려가지 않도록 직선으로 브릿지 처리

        Args:
            baseline: 원본 베이스라인
            threshold_ratio: 신호 범위 대비 음수 임계값 비율

        Returns:
            음수 구간이 브릿지 처리된 베이스라인
        """
        bridged_baseline = baseline.copy()

        # 1. 안정적인 베이스라인 참조값 계산
        # 상위 75% 중 하위 값들 (피크 제외, 음수 제외)
        positive_intensity = self.intensity[self.intensity > 0]
        if len(positive_intensity) < 10:
            return bridged_baseline

        # 양수 값들 중 하위 30%의 중앙값 = 안정적인 베이스라인 수준
        sorted_positive = np.sort(positive_intensity)
        stable_baseline_values = sorted_positive[:len(sorted_positive) // 3]
        stable_baseline_level = np.median(stable_baseline_values) if len(stable_baseline_values) > 0 else np.median(positive_intensity)

        # 2. 급격히 낮아지는 구간 감지 (여러 조건 결합)
        # 조건 1: 음수 값
        # 조건 2: 안정 베이스라인의 50% 미만
        # 조건 3: 급격한 하락 (기울기 기반)
        low_threshold = stable_baseline_level * 0.5

        # 급격한 하락 감지 (derivative)
        derivative = np.diff(self.intensity, prepend=self.intensity[0])
        rapid_drop_threshold = -np.std(np.abs(derivative)) * 3

        # 세 조건 중 하나라도 해당하면 마스킹
        low_mask = (
            (self.intensity < 0) |  # 음수
            (self.intensity < low_threshold) |  # 임계값 미만
            (derivative < rapid_drop_threshold)  # 급락
        )

        if not np.any(low_mask):
            return bridged_baseline

        # 3. 연속된 낮은 구간 찾기 (마진 추가)
        # 작은 간격은 연결하여 하나의 큰 영역으로 처리
        expanded_mask = low_mask.copy()

        # 마진 확장: 전후 10포인트도 포함
        for i in range(len(expanded_mask)):
            if low_mask[i]:
                start = max(0, i - 10)
                end = min(len(expanded_mask), i + 11)
                expanded_mask[start:end] = True

        # 연속 구간 찾기
        regions = []
        in_region = False
        start = 0

        for i, is_low in enumerate(expanded_mask):
            if is_low and not in_region:
                start = i
                in_region = True
            elif not is_low and in_region:
                regions.append((start, i - 1))
                in_region = False

        if in_region:
            regions.append((start, len(expanded_mask) - 1))

        # 4. 각 낮은 구간에 대해 직선 브릿지 적용
        for region_start, region_end in regions:
            # 구간이 너무 작으면 스킵 (노이즈일 가능성)
            if region_end - region_start < 3:
                continue

            # 5. 안정적인 앵커 포인트 찾기
            # 왼쪽: 구간 시작 전에서 안정 베이스라인 수준 이상인 지점
            left_anchor = 0
            search_start = max(0, region_start - 500)  # 최대 500포인트 검색

            for i in range(region_start - 1, search_start - 1, -1):
                if i >= 0:
                    # 안정 베이스라인 수준의 80% 이상이고, 급락 중이 아닌 지점
                    if self.intensity[i] >= stable_baseline_level * 0.8 and derivative[i] >= rapid_drop_threshold:
                        left_anchor = i
                        break

            # 오른쪽: 구간 끝 후에서 안정 베이스라인 수준 이상인 지점
            right_anchor = len(self.intensity) - 1
            search_end = min(len(self.intensity), region_end + 500)

            for i in range(region_end + 1, search_end):
                if i < len(self.intensity):
                    # 안정 베이스라인 수준의 80% 이상이고, 급상승 중이 아닌 지점
                    if self.intensity[i] >= stable_baseline_level * 0.8 and derivative[i] <= -rapid_drop_threshold:
                        right_anchor = i
                        break

            # 6. 앵커 포인트 값 결정 (중앙값 사용 - 더 안정적)
            # 왼쪽 앵커 값: 앵커 주변 50포인트의 하위 25% 중앙값
            left_region_start = max(0, left_anchor - 50)
            left_region_end = left_anchor + 1
            left_region = self.intensity[left_region_start:left_region_end]
            left_region_stable = left_region[(left_region > 0) & (left_region >= stable_baseline_level * 0.5)]

            if len(left_region_stable) > 0:
                # 하위 25%의 중앙값 사용 (피크 영향 제거)
                sorted_left = np.sort(left_region_stable)
                left_value = np.median(sorted_left[:max(1, len(sorted_left) // 4)])
            else:
                left_value = stable_baseline_level

            # 오른쪽 앵커 값
            right_region_start = right_anchor
            right_region_end = min(len(self.intensity), right_anchor + 50)
            right_region = self.intensity[right_region_start:right_region_end]
            right_region_stable = right_region[(right_region > 0) & (right_region >= stable_baseline_level * 0.5)]

            if len(right_region_stable) > 0:
                sorted_right = np.sort(right_region_stable)
                right_value = np.median(sorted_right[:max(1, len(sorted_right) // 4)])
            else:
                right_value = stable_baseline_level

            # 7. 앵커 값이 너무 낮으면 안정 베이스라인 수준으로 보정
            left_value = max(left_value, stable_baseline_level * 0.7)
            right_value = max(right_value, stable_baseline_level * 0.7)

            # 8. 직선 보간으로 브릿지
            if right_anchor > left_anchor:
                x_range = np.arange(left_anchor, right_anchor + 1)
                bridge_line = np.interp(
                    x_range,
                    [left_anchor, right_anchor],
                    [left_value, right_value]
                )
                # 기존 베이스라인보다 높은 경우에만 브릿지 적용
                # (이미 좋은 베이스라인을 낮추지 않도록)
                for idx, val in zip(range(left_anchor, right_anchor + 1), bridge_line):
                    if bridged_baseline[idx] < val:
                        bridged_baseline[idx] = val

        return bridged_baseline

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
        피크 영역에 평평한 베이스라인을 적용하고, robust vs weighted를 피크 너비로 비교

        Returns:
            최적 베이스라인과 파라미터 정보
        """
        # 앵커 포인트 찾기
        self.find_baseline_anchor_points(
            valley_prominence=0.01,
            percentile=10
        )

        # robust_fit 방법으로 베이스라인 생성
        baseline_robust = self.generate_hybrid_baseline(method='robust_fit')

        # 피크 검출
        corrected = np.maximum(self.intensity - baseline_robust, 0)
        noise_level = np.percentile(corrected, 25) * 1.5
        peaks, _ = signal.find_peaks(
            corrected,
            prominence=np.ptp(corrected) * 0.005,
            height=noise_level * 3,
            width=0
        )

        # 피크 영역에 평평한 베이스라인 적용
        if len(peaks) > 0:
            hybrid_baseline = self.apply_linear_baseline_to_peaks(baseline_robust, peaks)
        else:
            hybrid_baseline = baseline_robust

        params = {
            'method': 'robust_fit_with_flat_peaks',
            'num_peaks': len(peaks),
            'peaks_rt': [self.time[p] for p in peaks] if len(peaks) > 0 else []
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