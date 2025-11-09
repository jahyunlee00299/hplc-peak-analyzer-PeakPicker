"""
Improved Baseline Correction Algorithm
개선된 하이브리드 베이스라인 보정 알고리즘
"""

import numpy as np
from scipy import signal
from scipy.interpolate import UnivariateSpline, interp1d
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class BaselineAnchor:
    """베이스라인 앵커 포인트"""
    index: int
    rt: float
    value: float
    type: str  # 'valley', 'local_min', 'boundary'
    confidence: float  # 0-1


class ImprovedBaselineCorrector:
    """개선된 베이스라인 보정 알고리즘"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        """
        Initialize corrector

        Args:
            time: Retention time array
            intensity: Signal intensity array
        """
        self.time = time
        self.intensity = intensity
        self.anchors: List[BaselineAnchor] = []

        # 자동으로 음수 처리
        if np.min(intensity) < 0:
            self.intensity = intensity - np.min(intensity)

    def find_anchors(
        self,
        valley_prominence_factor: float = 0.01,
        local_min_percentile: float = 10,
        min_anchor_distance: int = 15,
        smoothing_window: Optional[int] = None
    ) -> List[BaselineAnchor]:
        """
        베이스라인 앵커 포인트 찾기 (개선된 알고리즘)

        Args:
            valley_prominence_factor: Valley 검출 민감도
            local_min_percentile: Local minimum 하위 백분위
            min_anchor_distance: 앵커 간 최소 거리 (데이터 포인트)
            smoothing_window: 스무딩 윈도우 크기

        Returns:
            앵커 포인트 리스트
        """
        anchors = []

        # 1. 스무딩
        if smoothing_window is None:
            smoothing_window = max(11, min(51, len(self.intensity) // 30))
        if smoothing_window % 2 == 0:
            smoothing_window += 1

        if len(self.intensity) > smoothing_window:
            smoothed = signal.savgol_filter(self.intensity, smoothing_window, 3)
        else:
            smoothed = self.intensity.copy()

        # 2. Valley 검출 (개선된 방법)
        valleys = self._find_valleys_improved(
            smoothed,
            prominence_factor=valley_prominence_factor,
            window=smoothing_window
        )

        for v_idx in valleys:
            anchors.append(BaselineAnchor(
                index=v_idx,
                rt=self.time[v_idx],
                value=self.intensity[v_idx],
                type='valley',
                confidence=1.0
            ))

        # 3. Valley 사이 구간에서 Local Minimum 찾기 (개선된 방법)
        valley_indices = np.concatenate(([0], valleys, [len(self.intensity) - 1]))

        for i in range(len(valley_indices) - 1):
            start_idx = valley_indices[i]
            end_idx = valley_indices[i + 1]
            segment_length = end_idx - start_idx

            # 구간이 충분히 길면 local minimum 추가
            if segment_length > min_anchor_distance * 2:
                local_mins = self._find_local_minima_in_segment(
                    start_idx, end_idx,
                    percentile=local_min_percentile,
                    min_distance=min_anchor_distance
                )

                for lm_idx, confidence in local_mins:
                    # Valley와 거리 체크
                    if all(abs(lm_idx - v) > min_anchor_distance for v in valleys):
                        anchors.append(BaselineAnchor(
                            index=lm_idx,
                            rt=self.time[lm_idx],
                            value=self.intensity[lm_idx],
                            type='local_min',
                            confidence=confidence
                        ))

        # 4. 경계 앵커 추가
        if not any(a.index == 0 for a in anchors):
            anchors.append(BaselineAnchor(
                index=0,
                rt=self.time[0],
                value=self.intensity[0],
                type='boundary',
                confidence=0.8
            ))

        if not any(a.index == len(self.intensity) - 1 for a in anchors):
            anchors.append(BaselineAnchor(
                index=len(self.intensity) - 1,
                rt=self.time[-1],
                value=self.intensity[-1],
                type='boundary',
                confidence=0.8
            ))

        # 5. 정렬 및 중복 제거 (개선된 방법)
        anchors = self._remove_close_anchors(anchors, min_anchor_distance)
        anchors.sort(key=lambda a: a.index)

        self.anchors = anchors
        return anchors

    def _find_valleys_improved(
        self,
        signal_data: np.ndarray,
        prominence_factor: float,
        window: int
    ) -> np.ndarray:
        """개선된 Valley 검출"""
        # 역신호에서 피크 찾기
        inverted = -signal_data
        prominence = np.ptp(signal_data) * prominence_factor

        valleys, properties = signal.find_peaks(
            inverted,
            prominence=prominence,
            distance=window // 2,
            width=1
        )

        return valleys

    def _find_local_minima_in_segment(
        self,
        start_idx: int,
        end_idx: int,
        percentile: float,
        min_distance: int
    ) -> List[Tuple[int, float]]:
        """구간 내 Local Minima 찾기 (개선된 방법)"""
        segment = self.intensity[start_idx:end_idx]

        if len(segment) < min_distance:
            return []

        # 하위 percentile 임계값
        threshold = np.percentile(segment, percentile)

        # 임계값 이하인 점들 중 극소값 찾기
        local_mins = []
        candidates = np.where(segment <= threshold)[0]

        if len(candidates) == 0:
            return []

        # 후보들을 클러스터로 그룹화하여 각 클러스터에서 최소값 선택
        clusters = []
        current_cluster = [candidates[0]]

        for i in range(1, len(candidates)):
            if candidates[i] - candidates[i-1] <= min_distance // 2:
                current_cluster.append(candidates[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [candidates[i]]
        clusters.append(current_cluster)

        # 각 클러스터에서 최소값 선택
        for cluster in clusters:
            cluster_values = segment[cluster]
            min_idx_in_cluster = cluster[np.argmin(cluster_values)]
            global_idx = start_idx + min_idx_in_cluster

            # Confidence 계산: 주변 기울기가 작을수록 높음
            confidence = self._calculate_confidence(global_idx)

            local_mins.append((global_idx, confidence))

        return local_mins

    def _calculate_confidence(self, idx: int, window: int = 5) -> float:
        """앵커 포인트의 신뢰도 계산"""
        if idx < window or idx >= len(self.intensity) - window:
            return 0.5

        # 주변 기울기의 표준편차 (낮을수록 평평 = 높은 신뢰도)
        left_slope = abs(self.intensity[idx] - self.intensity[idx - window])
        right_slope = abs(self.intensity[idx + window] - self.intensity[idx])
        avg_slope = (left_slope + right_slope) / 2

        # 정규화 (0-1 범위)
        max_slope = np.ptp(self.intensity) * 0.1
        confidence = 1.0 / (1.0 + avg_slope / max_slope)

        return confidence

    def _remove_close_anchors(
        self,
        anchors: List[BaselineAnchor],
        min_distance: int
    ) -> List[BaselineAnchor]:
        """너무 가까운 앵커 제거 (개선된 알고리즘)"""
        if len(anchors) == 0:
            return []

        # 인덱스로 정렬
        sorted_anchors = sorted(anchors, key=lambda a: a.index)

        # 우선순위: valley > boundary > local_min
        priority = {'valley': 3, 'boundary': 2, 'local_min': 1}

        filtered = [sorted_anchors[0]]

        for anchor in sorted_anchors[1:]:
            # 마지막 추가된 앵커와의 거리 체크
            if anchor.index - filtered[-1].index < min_distance:
                # 더 높은 우선순위 또는 confidence를 가진 것 선택
                last = filtered[-1]

                if priority[anchor.type] > priority[last.type]:
                    filtered[-1] = anchor
                elif priority[anchor.type] == priority[last.type]:
                    if anchor.confidence > last.confidence:
                        filtered[-1] = anchor
            else:
                filtered.append(anchor)

        return filtered

    def generate_baseline(
        self,
        method: str = 'adaptive_spline',
        smooth_factor: float = 1.0,
        apply_rt_relaxation: bool = True
    ) -> np.ndarray:
        """
        베이스라인 생성 (개선된 방법)

        Args:
            method: 베이스라인 생성 방법
                - 'adaptive_spline': Confidence 가중치 + RT 기반 적응형 스플라인
                - 'robust_spline': Outlier 제거 + 강건한 스플라인
                - 'linear': 단순 선형 보간
            smooth_factor: 스무딩 강도 (0-2)
            apply_rt_relaxation: RT 기반 슬로프 완화 적용 여부

        Returns:
            베이스라인 배열
        """
        if len(self.anchors) == 0:
            self.find_anchors()

        if len(self.anchors) < 2:
            return np.zeros_like(self.intensity)

        indices = np.array([a.index for a in self.anchors])
        values = np.array([a.value for a in self.anchors])
        confidences = np.array([a.confidence for a in self.anchors])

        # RT 기반 슬로프 완화 적용
        if apply_rt_relaxation:
            values = self._apply_rt_based_relaxation(indices, values)

        # 베이스라인 생성
        if method == 'adaptive_spline':
            baseline = self._adaptive_spline_baseline(
                indices, values, confidences, smooth_factor
            )
        elif method == 'robust_spline':
            baseline = self._robust_spline_baseline(
                indices, values, confidences, smooth_factor
            )
        elif method == 'linear':
            baseline = self._linear_baseline(indices, values)
        else:
            raise ValueError(f"Unknown method: {method}")

        # 베이스라인이 신호를 초과하지 않도록
        baseline = np.minimum(baseline, self.intensity)

        # 부드럽게 만들기
        if len(baseline) > 21:
            baseline = signal.savgol_filter(baseline, 21, 2)
            baseline = np.minimum(baseline, self.intensity)

        # 음수 제거
        baseline = np.maximum(baseline, 0)

        return baseline

    def _apply_rt_based_relaxation(
        self,
        indices: np.ndarray,
        values: np.ndarray,
        rt_threshold: float = 0.5,  # RT 차이 임계값 (분)
        max_slope_factor: float = 0.15  # 최대 기울기 제한
    ) -> np.ndarray:
        """
        RT 기반 슬로프 완화

        인접 앵커 간 RT 차이가 크면 급격한 기울기 완화
        """
        if len(indices) < 2:
            return values

        relaxed_values = values.copy()

        for i in range(len(indices) - 1):
            rt_diff = self.time[indices[i+1]] - self.time[indices[i]]

            if rt_diff > rt_threshold:
                # 기울기 계산
                value_diff = values[i+1] - values[i]
                index_diff = indices[i+1] - indices[i]

                if index_diff > 0:
                    slope = abs(value_diff / index_diff)
                    max_allowed_slope = np.ptp(self.intensity) * max_slope_factor / len(self.intensity)

                    # 기울기가 너무 크면 완화
                    if slope > max_allowed_slope:
                        # 구간의 최소값으로 조정
                        segment = self.intensity[indices[i]:indices[i+1]+1]
                        segment_min = np.percentile(segment, 5)

                        # 더 낮은 값으로 조정
                        if value_diff > 0:  # 증가 구간
                            relaxed_values[i+1] = min(values[i+1], segment_min)
                        else:  # 감소 구간
                            relaxed_values[i] = min(values[i], segment_min)

        return relaxed_values

    def _adaptive_spline_baseline(
        self,
        indices: np.ndarray,
        values: np.ndarray,
        confidences: np.ndarray,
        smooth_factor: float
    ) -> np.ndarray:
        """Confidence 가중치 적용 스플라인"""
        if len(indices) < 4:
            return self._linear_baseline(indices, values)

        try:
            # 가중치 기반 스무딩
            weights = confidences
            s = len(indices) * smooth_factor * (1 - np.mean(confidences) * 0.3)

            spl = UnivariateSpline(indices, values, w=weights, s=s, k=3)
            baseline = spl(np.arange(len(self.intensity)))
        except:
            baseline = self._linear_baseline(indices, values)

        return baseline

    def _robust_spline_baseline(
        self,
        indices: np.ndarray,
        values: np.ndarray,
        confidences: np.ndarray,
        smooth_factor: float
    ) -> np.ndarray:
        """Outlier 제거 후 강건한 스플라인"""
        if len(values) < 4:
            return self._linear_baseline(indices, values)

        # MAD 기반 outlier 제거
        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad > 0:
            threshold = median + 3 * mad
            mask = values <= threshold
        else:
            mask = np.ones(len(values), dtype=bool)

        robust_indices = indices[mask]
        robust_values = values[mask]
        robust_weights = confidences[mask]

        if len(robust_indices) < 4:
            return self._linear_baseline(indices, values)

        try:
            spl = UnivariateSpline(
                robust_indices,
                robust_values,
                w=robust_weights,
                s=len(robust_indices) * smooth_factor,
                k=min(3, len(robust_indices) - 1)
            )
            baseline = spl(np.arange(len(self.intensity)))
        except:
            baseline = self._linear_baseline(robust_indices, robust_values)

        return baseline

    def _linear_baseline(
        self,
        indices: np.ndarray,
        values: np.ndarray
    ) -> np.ndarray:
        """단순 선형 보간"""
        f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
        return f(np.arange(len(self.intensity)))

    def apply_linear_to_peaks(
        self,
        baseline: np.ndarray,
        peak_indices: Optional[List[int]] = None,
        auto_detect: bool = True
    ) -> np.ndarray:
        """
        피크 영역에 직선 베이스라인 적용

        Args:
            baseline: 원본 베이스라인
            peak_indices: 피크 인덱스 리스트 (None이면 자동 검출)
            auto_detect: 자동으로 피크 검출할지 여부

        Returns:
            직선 베이스라인이 적용된 베이스라인
        """
        if peak_indices is None and auto_detect:
            # 자동 피크 검출
            corrected = np.maximum(self.intensity - baseline, 0)
            noise_level = np.percentile(corrected, 25) * 1.5

            peaks, _ = signal.find_peaks(
                corrected,
                prominence=np.ptp(corrected) * 0.005,
                height=max(noise_level * 3, np.std(corrected) * 2)
            )
            peak_indices = peaks.tolist()

        if not peak_indices:
            return baseline

        linear_baseline = baseline.copy()

        for peak_idx in peak_indices:
            # 피크 경계 찾기 (half-height method)
            peak_height = self.intensity[peak_idx] - baseline[peak_idx]

            if peak_height <= 0:
                continue

            half_height = baseline[peak_idx] + peak_height / 2

            # 왼쪽 경계
            left_idx = peak_idx
            while left_idx > 0 and self.intensity[left_idx] > half_height:
                left_idx -= 1

            # 오른쪽 경계
            right_idx = peak_idx
            while right_idx < len(self.intensity) - 1 and self.intensity[right_idx] > half_height:
                right_idx += 1

            # 직선 베이스라인 적용
            if right_idx > left_idx:
                baseline_left = max(0, baseline[left_idx])
                baseline_right = max(0, baseline[right_idx])
                linear_baseline[left_idx:right_idx+1] = np.linspace(
                    baseline_left, baseline_right, right_idx - left_idx + 1
                )

        return linear_baseline

    def optimize_baseline(
        self,
        methods: Optional[List[str]] = None,
        use_linear_peaks: bool = True
    ) -> Tuple[np.ndarray, Dict]:
        """
        최적 베이스라인 자동 선택

        Args:
            methods: 시도할 방법 리스트
            use_linear_peaks: 피크 영역에 직선 베이스라인 적용 여부

        Returns:
            (최적 베이스라인, 파라미터 정보)
        """
        if methods is None:
            methods = ['adaptive_spline', 'robust_spline']

        best_score = -np.inf
        best_baseline = None
        best_params = {}

        # 앵커 포인트 찾기
        self.find_anchors()

        # 각 방법 시도
        for method in methods:
            baseline = self.generate_baseline(method=method)

            # 피크 영역에 직선 베이스라인 적용
            if use_linear_peaks:
                baseline = self.apply_linear_to_peaks(baseline)

            # 평가
            corrected = np.maximum(self.intensity - baseline, 0)
            score = self._evaluate_baseline(baseline, corrected)

            if score > best_score:
                best_score = score
                best_baseline = baseline
                best_params = {
                    'method': method,
                    'score': score,
                    'use_linear_peaks': use_linear_peaks,
                    'num_anchors': len(self.anchors)
                }

        return best_baseline, best_params

    def _evaluate_baseline(
        self,
        baseline: np.ndarray,
        corrected: np.ndarray
    ) -> float:
        """
        베이스라인 품질 평가 (개선된 방법)

        평가 기준:
        1. 음수 값 비율 (낮을수록 좋음)
        2. 베이스라인 부드러움 (적당히 부드러워야 함)
        3. 피크 보존 (많이 보존될수록 좋음)
        4. 베이스라인이 신호에 가까운 정도 (너무 높으면 안됨)
        """
        # 1. 음수 비율 (0-100점)
        neg_ratio = np.sum(corrected < 0) / len(corrected)
        neg_score = (1 - neg_ratio) * 100

        # 2. 부드러움 (0-50점)
        if len(baseline) > 2:
            smoothness = np.std(np.diff(baseline, 2))
            max_smoothness = np.ptp(self.intensity) * 0.01
            smooth_score = max(0, 50 - smoothness / max_smoothness * 50)
        else:
            smooth_score = 25

        # 3. 피크 보존 (0-50점)
        try:
            original_peaks = signal.find_peaks(
                self.intensity,
                prominence=np.ptp(self.intensity) * 0.02
            )[0]

            if len(original_peaks) > 0:
                corrected_peaks = signal.find_peaks(
                    corrected,
                    prominence=np.ptp(corrected) * 0.02
                )[0]
                preservation = min(1.0, len(corrected_peaks) / len(original_peaks))
            else:
                preservation = 1.0

            peak_score = preservation * 50
        except:
            peak_score = 25

        # 4. 베이스라인 높이 (0-25점) - 너무 높으면 감점
        baseline_ratio = np.median(baseline) / (np.median(self.intensity) + 1e-10)
        if baseline_ratio < 0.3:
            height_score = 25
        elif baseline_ratio < 0.5:
            height_score = 15
        else:
            height_score = 5

        # 종합 점수
        total_score = neg_score + smooth_score + peak_score + height_score

        return total_score


def process_exported_signal(
    csv_file: str,
    method: str = 'adaptive_spline',
    use_linear_peaks: bool = True,
    apply_rt_relaxation: bool = True
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict]:
    """
    Exported signal CSV 파일 처리

    Args:
        csv_file: CSV 파일 경로
        method: 베이스라인 방법
        use_linear_peaks: 피크에 직선 베이스라인 적용 여부
        apply_rt_relaxation: RT 기반 슬로프 완화 적용 여부

    Returns:
        (time, intensity, baseline, info_dict)
    """
    import pandas as pd

    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # 베이스라인 보정
    corrector = ImprovedBaselineCorrector(time, intensity)

    if method == 'auto':
        baseline, params = corrector.optimize_baseline(use_linear_peaks=use_linear_peaks)
    else:
        corrector.find_anchors()
        baseline = corrector.generate_baseline(
            method=method,
            apply_rt_relaxation=apply_rt_relaxation
        )
        if use_linear_peaks:
            baseline = corrector.apply_linear_to_peaks(baseline)

        params = {
            'method': method,
            'num_anchors': len(corrector.anchors),
            'use_linear_peaks': use_linear_peaks,
            'apply_rt_relaxation': apply_rt_relaxation
        }

    return time, intensity, baseline, params
