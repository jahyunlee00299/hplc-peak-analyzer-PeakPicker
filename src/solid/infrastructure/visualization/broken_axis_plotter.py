"""
Broken Axis Plotter
===================

Y축 브레이크가 있는 크로마토그램 시각화.
큰 피크와 작은 피크를 동시에 효과적으로 표시.

Author: PeakPicker Project
Date: 2025-11-26
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from typing import List, Tuple, Optional, Union, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    from brokenaxes import brokenaxes
    BROKENAXES_AVAILABLE = True
except ImportError:
    BROKENAXES_AVAILABLE = False
    print("Warning: brokenaxes not installed. Install with: pip install brokenaxes")


class BreakStrategy(Enum):
    """Y축 브레이크 전략"""
    NONE = "none"                    # 브레이크 없음
    AUTO = "auto"                    # 자동 결정
    PEAK_GAP = "peak_gap"            # 피크 높이 갭 기반
    PERCENTILE = "percentile"        # 백분위수 기반
    FIXED = "fixed"                  # 고정값


@dataclass
class BreakPoint:
    """Y축 브레이크 포인트 정보"""
    lower_range: Tuple[float, float]   # 하단 축 범위 (min, max)
    upper_range: Tuple[float, float]   # 상단 축 범위 (min, max)
    gap_ratio: float                   # 생략된 영역 비율
    reason: str                        # 브레이크 적용 이유
    has_negative_break: bool = False   # 음수 영역 브레이크 여부
    negative_range: Optional[Tuple[float, float]] = None  # 음수 영역 범위

    @property
    def ylims(self) -> Tuple[Tuple[float, float], ...]:
        """brokenaxes용 ylims 반환"""
        if self.has_negative_break and self.negative_range is not None:
            # 음수 영역 + 하단 + 상단 (3개 영역)
            return (self.negative_range, self.lower_range, self.upper_range)
        return (self.lower_range, self.upper_range)


class PeakHeightAnalyzer:
    """
    피크 높이 분석기

    전체 피크 높이 분포를 분석하여 최적의 Y축 브레이크 포인트를 결정.
    """

    def __init__(
        self,
        min_gap_ratio: float = 2.5,       # 브레이크 적용할 최소 높이 비율
        min_peaks_for_analysis: int = 2,   # 분석에 필요한 최소 피크 수
        margin_factor: float = 0.15,       # 경계 여유 비율
        percentile_threshold: float = 85   # 백분위수 기준
    ):
        """
        Parameters
        ----------
        min_gap_ratio : float
            연속 피크 간 높이 비율이 이 값 이상이면 브레이크 적용
        min_peaks_for_analysis : int
            분석에 필요한 최소 피크 수
        margin_factor : float
            브레이크 경계에 추가할 여유 비율
        percentile_threshold : float
            백분위수 기반 분석 시 기준값
        """
        self.min_gap_ratio = min_gap_ratio
        self.min_peaks_for_analysis = min_peaks_for_analysis
        self.margin_factor = margin_factor
        self.percentile_threshold = percentile_threshold

    def analyze_peak_heights(
        self,
        peak_heights: np.ndarray
    ) -> Dict[str, Any]:
        """
        피크 높이 분포 분석

        Parameters
        ----------
        peak_heights : np.ndarray
            피크 높이 배열

        Returns
        -------
        Dict
            분석 결과 (gaps, clusters, statistics 등)
        """
        if len(peak_heights) < self.min_peaks_for_analysis:
            return {
                'has_significant_gap': False,
                'reason': f'피크 수 부족 ({len(peak_heights)} < {self.min_peaks_for_analysis})'
            }

        sorted_heights = np.sort(peak_heights)[::-1]  # 내림차순

        # 연속 피크 간 비율 계산
        ratios = []
        for i in range(len(sorted_heights) - 1):
            if sorted_heights[i + 1] > 0:
                ratio = sorted_heights[i] / sorted_heights[i + 1]
                ratios.append({
                    'index': i,
                    'high': sorted_heights[i],
                    'low': sorted_heights[i + 1],
                    'ratio': ratio
                })

        # 가장 큰 갭 찾기
        if ratios:
            max_gap = max(ratios, key=lambda x: x['ratio'])
        else:
            max_gap = None

        # 통계
        stats = {
            'count': len(peak_heights),
            'max': float(np.max(peak_heights)),
            'min': float(np.min(peak_heights)),
            'mean': float(np.mean(peak_heights)),
            'median': float(np.median(peak_heights)),
            'std': float(np.std(peak_heights)),
            'cv': float(np.std(peak_heights) / np.mean(peak_heights)) if np.mean(peak_heights) > 0 else 0
        }

        # 유의미한 갭 판정
        has_gap = max_gap is not None and max_gap['ratio'] >= self.min_gap_ratio

        return {
            'has_significant_gap': has_gap,
            'max_gap': max_gap,
            'all_ratios': ratios,
            'sorted_heights': sorted_heights.tolist(),
            'statistics': stats,
            'reason': f"최대 갭 비율: {max_gap['ratio']:.2f}" if max_gap else "갭 없음"
        }

    def find_break_point_by_peak_gap(
        self,
        peak_heights: np.ndarray,
        signal_min: float = 0,
        signal_max: float = None,
        all_peak_heights: np.ndarray = None
    ) -> Optional[BreakPoint]:
        """
        피크 높이 갭 기반 브레이크 포인트 찾기

        가장 큰 높이 갭이 있는 위치에서 Y축을 끊음.
        모든 피크가 브레이크 영역에 걸리지 않도록 경계를 조정함.

        Parameters
        ----------
        peak_heights : np.ndarray
            피크 높이 배열 (양수)
        signal_min : float
            신호 최소값
        signal_max : float
            신호 최대값 (None이면 피크 최대값 사용)
        all_peak_heights : np.ndarray, optional
            모든 피크 높이 (음수 포함, 경계 조정용)

        Returns
        -------
        Optional[BreakPoint]
            브레이크 포인트 (불필요시 None)
        """
        analysis = self.analyze_peak_heights(peak_heights)

        if not analysis['has_significant_gap']:
            return None

        max_gap = analysis['max_gap']
        high_value = max_gap['high']
        low_value = max_gap['low']
        gap_index = max_gap['index']

        # all_peak_heights가 없으면 peak_heights 사용
        if all_peak_heights is None:
            all_peak_heights = peak_heights

        sorted_heights = np.sort(peak_heights)[::-1]  # 내림차순

        # === 핵심 개선: 브레이크 영역에 피크가 걸리지 않도록 경계 조정 ===
        # 상위 그룹: gap_index까지의 피크들
        upper_group = sorted_heights[:gap_index + 1]
        # 하위 그룹: gap_index 이후의 피크들
        lower_group = sorted_heights[gap_index + 1:]

        # 하위 그룹의 최대값 위에 여유를 두고 lower_max 설정
        # 모든 작은 피크들이 하단 영역에 완전히 들어가도록
        lower_group_max = np.max(lower_group) if len(lower_group) > 0 else low_value
        lower_max = lower_group_max * (1 + self.margin_factor)

        # 상위 그룹의 최소값 아래에 여유를 두고 upper_min 설정
        # 모든 큰 피크들이 상단 영역에 완전히 들어가도록
        upper_group_min = np.min(upper_group) if len(upper_group) > 0 else high_value
        upper_min = upper_group_min * (1 - self.margin_factor)

        # 브레이크 영역에 피크가 없는지 확인
        # 만약 겹치면 경계 재조정
        if lower_max >= upper_min:
            # 갭이 충분하지 않음 - 강제로 중간에 배치
            mid_point = (lower_group_max + upper_group_min) / 2
            lower_max = mid_point * 0.95
            upper_min = mid_point * 1.05

        # 최종 범위 결정
        if signal_max is None:
            signal_max = high_value * 1.05

        # 하단 범위: signal_min부터 lower_max까지
        lower_range = (signal_min, lower_max)
        # 상단 범위: upper_min부터 signal_max까지
        upper_range = (upper_min, signal_max * 1.05)

        # 생략 비율 계산
        total_range = signal_max - signal_min
        gap_size = upper_min - lower_max
        gap_ratio = gap_size / total_range if total_range > 0 else 0

        return BreakPoint(
            lower_range=lower_range,
            upper_range=upper_range,
            gap_ratio=gap_ratio,
            reason=f"Peak gap: {high_value:.0f} vs {low_value:.0f} ({max_gap['ratio']:.1f}x)"
        )

    def find_break_point_by_percentile(
        self,
        intensity: np.ndarray,
        peak_heights: np.ndarray = None
    ) -> Optional[BreakPoint]:
        """
        백분위수 기반 브레이크 포인트 찾기

        신호 강도 분포의 백분위수를 분석하여 브레이크 결정.

        Parameters
        ----------
        intensity : np.ndarray
            전체 신호 강도 배열
        peak_heights : np.ndarray, optional
            피크 높이 배열 (추가 검증용)

        Returns
        -------
        Optional[BreakPoint]
            브레이크 포인트 (불필요시 None)
        """
        q_low = np.percentile(intensity, self.percentile_threshold)
        q_high = np.percentile(intensity, 99)

        # 상위 1%와 하위 영역 간 갭 확인
        if q_high < q_low * self.min_gap_ratio:
            return None

        signal_min = max(0, np.min(intensity))
        signal_max = np.max(intensity)

        margin = (q_high - q_low) * self.margin_factor

        lower_range = (signal_min, q_low * 1.2)
        upper_range = (q_high * 0.8, signal_max * 1.05)

        total_range = signal_max - signal_min
        gap_size = upper_range[0] - lower_range[1]
        gap_ratio = gap_size / total_range if total_range > 0 else 0

        return BreakPoint(
            lower_range=lower_range,
            upper_range=upper_range,
            gap_ratio=gap_ratio,
            reason=f"백분위수 갭: P{self.percentile_threshold}={q_low:.0f}, P99={q_high:.0f}"
        )

    def analyze_negative_peaks(
        self,
        intensity: np.ndarray,
        threshold_ratio: float = 0.1
    ) -> Dict[str, Any]:
        """
        음수 피크 분석

        Parameters
        ----------
        intensity : np.ndarray
            강도 배열 (음수 포함 가능)
        threshold_ratio : float
            유의미한 음수 피크로 간주할 최소 비율 (양수 최대값 대비)

        Returns
        -------
        Dict
            음수 피크 분석 결과
        """
        signal_max = np.max(intensity)
        signal_min = np.min(intensity)

        # 음수 영역이 있는지 확인
        if signal_min >= 0:
            return {
                'has_negative': False,
                'negative_peaks': [],
                'min_value': 0,
                'reason': 'No negative values'
            }

        # 음수 피크 탐지
        negative_signal = -intensity  # 반전
        from scipy import signal as sig

        # 음수 영역에서 피크 찾기 (반전된 신호에서 양수 피크)
        neg_peaks, properties = sig.find_peaks(
            negative_signal,
            prominence=abs(signal_min) * 0.1,
            height=0
        )

        if len(neg_peaks) == 0:
            return {
                'has_negative': True,
                'negative_peaks': [],
                'min_value': signal_min,
                'reason': 'Negative baseline but no distinct negative peaks'
            }

        neg_peak_heights = -intensity[neg_peaks]  # 음수값의 절대값

        # 유의미한 음수 피크 판정
        threshold = signal_max * threshold_ratio
        significant_neg_peaks = neg_peak_heights[neg_peak_heights > threshold]

        return {
            'has_negative': True,
            'has_significant_negative': len(significant_neg_peaks) > 0,
            'negative_peaks': neg_peaks.tolist(),
            'negative_heights': neg_peak_heights.tolist(),
            'min_value': signal_min,
            'max_negative_height': float(np.max(neg_peak_heights)) if len(neg_peak_heights) > 0 else 0,
            'reason': f'{len(neg_peaks)} negative peaks found, min={signal_min:.0f}'
        }

    def find_break_with_negative(
        self,
        intensity: np.ndarray,
        peak_heights: np.ndarray,
        signal_min: float,
        signal_max: float
    ) -> Optional[BreakPoint]:
        """
        음수 피크를 포함한 브레이크 포인트 찾기

        양수 영역의 피크 갭과 음수 영역의 피크를 모두 고려.

        Parameters
        ----------
        intensity : np.ndarray
            강도 배열
        peak_heights : np.ndarray
            양수 피크 높이 배열
        signal_min : float
            신호 최소값
        signal_max : float
            신호 최대값

        Returns
        -------
        Optional[BreakPoint]
            음수 영역을 포함한 브레이크 포인트
        """
        # 1. 양수 영역 브레이크 분석
        pos_break = self.find_break_point_by_peak_gap(
            peak_heights[peak_heights > 0] if np.any(peak_heights > 0) else peak_heights,
            signal_min=0,
            signal_max=signal_max
        )

        # 2. 음수 영역 분석
        neg_analysis = self.analyze_negative_peaks(intensity)

        if not neg_analysis['has_negative'] or signal_min >= 0:
            # 음수 없으면 양수 브레이크만 반환
            return pos_break

        # 3. 음수 영역이 있는 경우
        min_val = neg_analysis['min_value']

        # 음수 피크가 있고 양수 브레이크도 필요한 경우
        if pos_break is not None:
            # 음수 영역에서 브레이크 필요 여부 확인
            # 음수 최소값과 0 사이에 큰 갭이 있는지
            if abs(min_val) > signal_max * 0.1:  # 음수가 양수 최대의 10% 이상
                # 음수 영역에 대한 브레이크 추가
                # 음수 피크의 꼭지가 잘리지 않도록 설정
                neg_peak_max = neg_analysis.get('max_negative_height', abs(min_val))

                # 음수 영역: min_val ~ -neg_peak_max * margin
                negative_range = (min_val * 1.05, -neg_peak_max * (1 - self.margin_factor))

                # 0 근처 영역과 양수 하단 사이에 갭 생성
                # 0 근처: -small ~ small
                zero_margin = max(abs(min_val) * 0.1, signal_max * 0.02)

                return BreakPoint(
                    lower_range=(-zero_margin, pos_break.lower_range[1]),
                    upper_range=pos_break.upper_range,
                    gap_ratio=pos_break.gap_ratio,
                    reason=f"{pos_break.reason} + negative region",
                    has_negative_break=True,
                    negative_range=negative_range
                )

        # 양수 브레이크는 없지만 음수 영역이 큰 경우
        if abs(min_val) > signal_max * 0.3:  # 음수가 양수의 30% 이상
            neg_peak_max = neg_analysis.get('max_negative_height', abs(min_val))
            negative_range = (min_val * 1.05, -neg_peak_max * (1 - self.margin_factor))
            zero_margin = max(abs(min_val) * 0.1, signal_max * 0.02)

            return BreakPoint(
                lower_range=(-zero_margin, signal_max * 1.05),
                upper_range=(signal_max * 1.05, signal_max * 1.05),  # dummy
                gap_ratio=0,
                reason=f"Negative peaks: min={min_val:.0f}",
                has_negative_break=True,
                negative_range=negative_range
            )

        return pos_break

    def find_optimal_break_point(
        self,
        intensity: np.ndarray,
        peak_heights: np.ndarray = None,
        peak_indices: np.ndarray = None,
        strategy: BreakStrategy = BreakStrategy.AUTO,
        include_negative: bool = True
    ) -> Optional[BreakPoint]:
        """
        최적 브레이크 포인트 찾기 (통합 메서드)

        모든 피크 꼭지가 브레이크 영역에 걸리지 않도록 보장.
        음수 피크도 처리 가능.

        Parameters
        ----------
        intensity : np.ndarray
            전체 신호 강도 배열
        peak_heights : np.ndarray, optional
            피크 높이 배열 (None이면 자동 탐지)
        peak_indices : np.ndarray, optional
            피크 인덱스 배열
        strategy : BreakStrategy
            브레이크 전략
        include_negative : bool
            음수 피크 영역도 브레이크 적용 여부

        Returns
        -------
        Optional[BreakPoint]
            최적 브레이크 포인트 (피크가 브레이크 영역에 걸리지 않음 보장)
        """
        if strategy == BreakStrategy.NONE:
            return None

        # 피크 높이가 없으면 자동 탐지
        if peak_heights is None:
            from scipy import signal as sig

            # 양수 피크 탐지
            peaks, properties = sig.find_peaks(
                intensity,
                prominence=np.std(intensity[intensity > 0]) * 2 if np.any(intensity > 0) else 1,
                distance=10
            )
            if len(peaks) > 0:
                peak_heights = intensity[peaks]
                peak_indices = peaks
            else:
                peak_heights = np.array([np.max(intensity)])

        signal_min = np.min(intensity)
        signal_max = np.max(intensity)

        # 양수 피크만 추출 (브레이크 계산용)
        pos_peak_heights = peak_heights[peak_heights > 0] if np.any(peak_heights > 0) else peak_heights

        if strategy == BreakStrategy.PEAK_GAP:
            bp = self.find_break_point_by_peak_gap(
                pos_peak_heights,
                signal_min=max(0, signal_min),
                signal_max=signal_max,
                all_peak_heights=peak_heights
            )
            # 음수 처리
            if include_negative and signal_min < 0:
                bp = self.find_break_with_negative(intensity, peak_heights, signal_min, signal_max)
            return bp

        elif strategy == BreakStrategy.PERCENTILE:
            return self.find_break_point_by_percentile(intensity, peak_heights)

        elif strategy == BreakStrategy.AUTO:
            # 자동: 피크 갭 먼저 시도
            bp = self.find_break_point_by_peak_gap(
                pos_peak_heights,
                signal_min=max(0, signal_min),
                signal_max=signal_max,
                all_peak_heights=peak_heights
            )

            # 음수 영역 처리
            if include_negative and signal_min < 0:
                bp_with_neg = self.find_break_with_negative(intensity, peak_heights, signal_min, signal_max)
                if bp_with_neg is not None:
                    bp = bp_with_neg

            # 피크 갭 실패 시 백분위수 시도
            if bp is None:
                bp = self.find_break_point_by_percentile(intensity, peak_heights)

            return bp

        return None


class BrokenAxisPlotter:
    """
    Y축 브레이크 플로터

    크로마토그램, 베이스라인, 디콘볼루션 등의 시각화에
    자동 Y축 브레이크를 적용.
    """

    def __init__(
        self,
        analyzer: PeakHeightAnalyzer = None,
        default_figsize: Tuple[int, int] = (14, 8),
        default_dpi: int = 150,
        hspace: float = 0.05,
        break_marker_size: float = 0.015
    ):
        """
        Parameters
        ----------
        analyzer : PeakHeightAnalyzer, optional
            피크 높이 분석기 (None이면 기본값 생성)
        default_figsize : Tuple[int, int]
            기본 그림 크기
        default_dpi : int
            기본 해상도
        hspace : float
            브레이크 영역 간격
        break_marker_size : float
            브레이크 마커 크기
        """
        self.analyzer = analyzer or PeakHeightAnalyzer()
        self.default_figsize = default_figsize
        self.default_dpi = default_dpi
        self.hspace = hspace
        self.break_marker_size = break_marker_size

    def plot_with_auto_break(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        peak_heights: np.ndarray = None,
        title: str = "Chromatogram",
        strategy: BreakStrategy = BreakStrategy.AUTO,
        subplot_spec: Any = None,
        figsize: Tuple[int, int] = None,
        **plot_kwargs
    ) -> Tuple[plt.Figure, Any, Optional[BreakPoint]]:
        """
        자동 Y축 브레이크가 적용된 플롯 생성

        Parameters
        ----------
        time : np.ndarray
            시간 배열
        intensity : np.ndarray
            강도 배열
        peak_heights : np.ndarray, optional
            피크 높이 배열
        title : str
            플롯 제목
        strategy : BreakStrategy
            브레이크 전략
        subplot_spec : GridSpec, optional
            서브플롯 스펙 (멀티 패널용)
        figsize : Tuple[int, int], optional
            그림 크기
        **plot_kwargs
            추가 플롯 옵션

        Returns
        -------
        Tuple[Figure, Axes, Optional[BreakPoint]]
            (피규어, 축 객체, 브레이크 포인트)
        """
        figsize = figsize or self.default_figsize

        # 브레이크 포인트 계산
        break_point = self.analyzer.find_optimal_break_point(
            intensity, peak_heights, strategy=strategy
        )

        if break_point is not None and BROKENAXES_AVAILABLE:
            # 브레이크 적용
            return self._plot_with_break(
                time, intensity, break_point, title,
                subplot_spec, figsize, **plot_kwargs
            )
        else:
            # 일반 플롯
            return self._plot_normal(
                time, intensity, title,
                subplot_spec, figsize, **plot_kwargs
            )

    def _plot_with_break(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        break_point: BreakPoint,
        title: str,
        subplot_spec: Any,
        figsize: Tuple[int, int],
        **plot_kwargs
    ) -> Tuple[plt.Figure, Any, BreakPoint]:
        """브레이크가 적용된 플롯"""
        if subplot_spec is not None:
            fig = plt.gcf()
            bax = brokenaxes(
                ylims=break_point.ylims,
                subplot_spec=subplot_spec,
                hspace=self.hspace,
                despine=False
            )
        else:
            fig = plt.figure(figsize=figsize)
            bax = brokenaxes(
                ylims=break_point.ylims,
                hspace=self.hspace,
                despine=False
            )

        # 기본 플롯 옵션
        default_kwargs = {
            'linewidth': 0.8,
            'alpha': 0.8,
            'color': 'blue'
        }
        default_kwargs.update(plot_kwargs)

        bax.plot(time, intensity, **default_kwargs)

        # 브레이크 정보 표시
        title_with_info = f"{title}\n[Y-axis break: {break_point.reason}]"
        bax.set_title(title_with_info, fontsize=11)
        bax.set_xlabel('Retention Time (min)')
        bax.set_ylabel('Intensity')

        return fig, bax, break_point

    def _plot_normal(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        title: str,
        subplot_spec: Any,
        figsize: Tuple[int, int],
        **plot_kwargs
    ) -> Tuple[plt.Figure, plt.Axes, None]:
        """일반 플롯 (브레이크 없음)"""
        if subplot_spec is not None:
            fig = plt.gcf()
            ax = fig.add_subplot(subplot_spec)
        else:
            fig, ax = plt.subplots(figsize=figsize)

        default_kwargs = {
            'linewidth': 0.8,
            'alpha': 0.8,
            'color': 'blue'
        }
        default_kwargs.update(plot_kwargs)

        ax.plot(time, intensity, **default_kwargs)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel('Retention Time (min)')
        ax.set_ylabel('Intensity')
        ax.grid(True, alpha=0.3)

        return fig, ax, None

    def plot_comparison_with_break(
        self,
        time: np.ndarray,
        signals: Dict[str, np.ndarray],
        peak_heights: np.ndarray = None,
        title: str = "Signal Comparison",
        strategy: BreakStrategy = BreakStrategy.AUTO,
        figsize: Tuple[int, int] = None,
        colors: Dict[str, str] = None,
        **plot_kwargs
    ) -> Tuple[plt.Figure, Any, Optional[BreakPoint]]:
        """
        여러 신호 비교 플롯 (브레이크 적용)

        Parameters
        ----------
        time : np.ndarray
            시간 배열
        signals : Dict[str, np.ndarray]
            신호 딕셔너리 {'label': intensity_array}
        peak_heights : np.ndarray, optional
            피크 높이 배열 (브레이크 계산용)
        title : str
            플롯 제목
        strategy : BreakStrategy
            브레이크 전략
        figsize : Tuple[int, int], optional
            그림 크기
        colors : Dict[str, str], optional
            레이블별 색상

        Returns
        -------
        Tuple[Figure, Axes, Optional[BreakPoint]]
        """
        figsize = figsize or self.default_figsize

        # 모든 신호의 최대값으로 브레이크 계산
        all_intensities = np.concatenate(list(signals.values()))

        break_point = self.analyzer.find_optimal_break_point(
            all_intensities, peak_heights, strategy=strategy
        )

        if break_point is not None and BROKENAXES_AVAILABLE:
            fig = plt.figure(figsize=figsize)
            bax = brokenaxes(
                ylims=break_point.ylims,
                hspace=self.hspace,
                despine=False
            )

            default_colors = ['blue', 'red', 'green', 'orange', 'purple']

            for i, (label, intensity) in enumerate(signals.items()):
                color = (colors or {}).get(label, default_colors[i % len(default_colors)])
                bax.plot(time, intensity, label=label, color=color,
                        linewidth=plot_kwargs.get('linewidth', 1))

            bax.legend(loc='best')
            bax.set_title(f"{title}\n[Y-axis break applied]", fontsize=11)
            bax.set_xlabel('Retention Time (min)')
            bax.set_ylabel('Intensity')

            return fig, bax, break_point
        else:
            fig, ax = plt.subplots(figsize=figsize)

            default_colors = ['blue', 'red', 'green', 'orange', 'purple']

            for i, (label, intensity) in enumerate(signals.items()):
                color = (colors or {}).get(label, default_colors[i % len(default_colors)])
                ax.plot(time, intensity, label=label, color=color,
                       linewidth=plot_kwargs.get('linewidth', 1))

            ax.legend(loc='best')
            ax.set_title(title, fontsize=11)
            ax.set_xlabel('Retention Time (min)')
            ax.set_ylabel('Intensity')
            ax.grid(True, alpha=0.3)

            return fig, ax, None


def create_multi_panel_baseline_plot(
    time: np.ndarray,
    intensity: np.ndarray,
    baseline: np.ndarray,
    anchor_points: List = None,
    peak_heights: np.ndarray = None,
    sample_name: str = "Sample",
    output_path: str = None,
    strategy: BreakStrategy = BreakStrategy.AUTO
) -> plt.Figure:
    """
    멀티 패널 베이스라인 시각화 (Y축 브레이크 포함)

    Parameters
    ----------
    time : np.ndarray
        시간 배열
    intensity : np.ndarray
        원본 강도 배열
    baseline : np.ndarray
        베이스라인 배열
    anchor_points : List, optional
        앵커 포인트 리스트
    peak_heights : np.ndarray, optional
        피크 높이 배열
    sample_name : str
        샘플 이름
    output_path : str, optional
        저장 경로
    strategy : BreakStrategy
        브레이크 전략

    Returns
    -------
    Figure
        Matplotlib 피규어
    """
    analyzer = PeakHeightAnalyzer()
    plotter = BrokenAxisPlotter(analyzer)

    # 보정된 신호
    corrected = intensity - baseline
    corrected_clipped = np.maximum(corrected, 0)

    # 브레이크 포인트 계산
    break_point = analyzer.find_optimal_break_point(
        intensity, peak_heights, strategy=strategy
    )

    corrected_break = analyzer.find_optimal_break_point(
        corrected_clipped, peak_heights, strategy=strategy
    )

    # 그림 생성
    fig = plt.figure(figsize=(16, 14))
    gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.25)

    # === Panel 1: 원본 + 앵커 (브레이크 적용) ===
    if break_point is not None and BROKENAXES_AVAILABLE:
        bax1 = brokenaxes(ylims=break_point.ylims, subplot_spec=gs[0, 0],
                         hspace=0.05, despine=False)
        bax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본')

        if anchor_points:
            for ap in anchor_points:
                conf = getattr(ap, 'confidence', 0.5)
                color = plt.cm.RdYlGn(conf)
                size = 30 + conf * 50
                bax1.scatter([time[ap.index]], [ap.value],
                            c=[color], s=size, zorder=5, edgecolors='black', linewidths=0.5)

        bax1.set_title(f'1. 원본 + 앵커 포인트\n[Break: {break_point.reason}]', fontsize=10)
        bax1.set_xlabel('시간 (min)')
        bax1.set_ylabel('강도')
        bax1.legend(loc='upper right')
    else:
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본')

        if anchor_points:
            for ap in anchor_points:
                conf = getattr(ap, 'confidence', 0.5)
                color = plt.cm.RdYlGn(conf)
                size = 30 + conf * 50
                ax1.scatter([time[ap.index]], [ap.value],
                           c=[color], s=size, zorder=5, edgecolors='black', linewidths=0.5)

        ax1.set_title('1. 원본 + 앵커 포인트', fontsize=10)
        ax1.set_xlabel('시간 (min)')
        ax1.set_ylabel('강도')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

    # === Panel 2: 원본 + 베이스라인 (브레이크 적용) ===
    if break_point is not None and BROKENAXES_AVAILABLE:
        bax2 = brokenaxes(ylims=break_point.ylims, subplot_spec=gs[0, 1],
                         hspace=0.05, despine=False)
        bax2.plot(time, intensity, 'b-', linewidth=1, alpha=0.5, label='원본')
        bax2.plot(time, baseline, 'r-', linewidth=2, label='베이스라인')
        bax2.set_title('2. 원본 + 베이스라인', fontsize=10)
        bax2.set_xlabel('시간 (min)')
        bax2.set_ylabel('강도')
        bax2.legend(loc='upper right')
    else:
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.plot(time, intensity, 'b-', linewidth=1, alpha=0.5, label='원본')
        ax2.plot(time, baseline, 'r-', linewidth=2, label='베이스라인')
        ax2.set_title('2. 원본 + 베이스라인', fontsize=10)
        ax2.set_xlabel('시간 (min)')
        ax2.set_ylabel('강도')
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)

    # === Panel 3: 보정 후 (브레이크 적용) ===
    if corrected_break is not None and BROKENAXES_AVAILABLE:
        bax3 = brokenaxes(ylims=corrected_break.ylims, subplot_spec=gs[1, 0],
                         hspace=0.05, despine=False)
        bax3.plot(time, corrected_clipped, 'g-', linewidth=1, label='보정 후')
        bax3.set_title(f'3. 보정 후\n[Break: {corrected_break.reason}]', fontsize=10)
        bax3.set_xlabel('시간 (min)')
        bax3.set_ylabel('강도')
        bax3.legend(loc='upper right')
    else:
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.plot(time, corrected_clipped, 'g-', linewidth=1, label='보정 후')
        ax3.fill_between(time, 0, corrected_clipped, alpha=0.3, color='green')
        ax3.set_title('3. 보정 후', fontsize=10)
        ax3.set_xlabel('시간 (min)')
        ax3.set_ylabel('강도')
        ax3.legend(loc='upper right')
        ax3.grid(True, alpha=0.3)

    # === Panel 4: 보정 전후 비교 ===
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(time, intensity, 'b-', linewidth=1, alpha=0.4, label='원본')
    ax4.plot(time, corrected_clipped, 'g-', linewidth=1.2, label='보정 후')
    ax4.set_title('4. 보정 전후 비교', fontsize=10)
    ax4.set_xlabel('시간 (min)')
    ax4.set_ylabel('강도')
    ax4.legend(loc='upper right')
    ax4.grid(True, alpha=0.3)

    # === Panel 5: 제거된 베이스라인 ===
    ax5 = fig.add_subplot(gs[2, 0])
    removed = intensity - corrected_clipped
    ax5.plot(time, removed, 'r-', linewidth=1, label='제거된 베이스라인')
    ax5.fill_between(time, 0, removed, alpha=0.3, color='red')
    ax5.set_title('5. 제거된 베이스라인 성분', fontsize=10)
    ax5.set_xlabel('시간 (min)')
    ax5.set_ylabel('강도')
    ax5.legend(loc='upper right')
    ax5.grid(True, alpha=0.3)

    # === Panel 6: 피크 높이 분포 ===
    ax6 = fig.add_subplot(gs[2, 1])

    if peak_heights is not None and len(peak_heights) > 0:
        sorted_heights = np.sort(peak_heights)[::-1]
        x_pos = np.arange(len(sorted_heights))

        colors = ['red' if h > np.percentile(peak_heights, 90) else
                  'orange' if h > np.percentile(peak_heights, 75) else 'blue'
                  for h in sorted_heights]

        ax6.bar(x_pos, sorted_heights, color=colors, alpha=0.7, edgecolor='black')
        ax6.set_xlabel('피크 순위 (높이순)')
        ax6.set_ylabel('피크 높이')
        ax6.set_title('6. 피크 높이 분포', fontsize=10)

        # 브레이크 포인트 표시
        if break_point is not None:
            ax6.axhline(y=break_point.lower_range[1], color='gray',
                       linestyle='--', label='브레이크 하한')
            ax6.axhline(y=break_point.upper_range[0], color='gray',
                       linestyle='--', label='브레이크 상한')
            ax6.legend(loc='upper right', fontsize=8)
    else:
        ax6.text(0.5, 0.5, '피크 높이 데이터 없음', ha='center', va='center',
                transform=ax6.transAxes, fontsize=12)

    ax6.grid(True, alpha=0.3)

    # 전체 제목
    fig.suptitle(f'{sample_name} - 베이스라인 분석', fontsize=14, fontweight='bold', y=0.98)

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"저장됨: {output_path}")

    return fig


# 테스트 코드
if __name__ == "__main__":
    print("BrokenAxisPlotter 테스트")
    print("=" * 50)

    # 테스트 데이터 생성
    np.random.seed(42)
    time = np.linspace(0, 30, 3000)

    # 큰 피크 1개 + 작은 피크 여러개
    signal = np.zeros_like(time)
    signal += 50000 * np.exp(-((time - 8)**2) / 0.5)    # 큰 피크
    signal += 2500 * np.exp(-((time - 12)**2) / 0.3)    # 작은 피크 1
    signal += 1800 * np.exp(-((time - 16)**2) / 0.4)    # 작은 피크 2
    signal += 2200 * np.exp(-((time - 20)**2) / 0.35)   # 작은 피크 3
    signal += 1500 * np.exp(-((time - 24)**2) / 0.3)    # 작은 피크 4
    signal += np.random.normal(0, 50, len(time))        # 노이즈
    signal = np.maximum(signal, 0)

    # 피크 높이 배열
    peak_heights = np.array([50000, 2500, 1800, 2200, 1500])

    # 분석기 테스트
    analyzer = PeakHeightAnalyzer()
    analysis = analyzer.analyze_peak_heights(peak_heights)

    print(f"\n피크 높이 분석:")
    print(f"  - 유의미한 갭 존재: {analysis['has_significant_gap']}")
    print(f"  - 이유: {analysis['reason']}")
    if analysis['max_gap']:
        print(f"  - 최대 갭: {analysis['max_gap']['high']:.0f} vs {analysis['max_gap']['low']:.0f}")
        print(f"  - 갭 비율: {analysis['max_gap']['ratio']:.2f}x")

    # 브레이크 포인트 계산
    bp = analyzer.find_optimal_break_point(signal, peak_heights)

    if bp:
        print(f"\n브레이크 포인트:")
        print(f"  - 하단 범위: {bp.lower_range}")
        print(f"  - 상단 범위: {bp.upper_range}")
        print(f"  - 갭 비율: {bp.gap_ratio:.1%}")
        print(f"  - 이유: {bp.reason}")

    # 플롯 테스트
    plotter = BrokenAxisPlotter(analyzer)

    fig, ax, bp_used = plotter.plot_with_auto_break(
        time, signal, peak_heights,
        title="테스트 크로마토그램",
        strategy=BreakStrategy.AUTO
    )

    plt.savefig('test_broken_axis.png', dpi=150, bbox_inches='tight')
    print(f"\n테스트 플롯 저장됨: test_broken_axis.png")
    plt.close()

    # 멀티 패널 테스트
    # 간단한 베이스라인 시뮬레이션
    baseline = signal * 0.02 + 100  # 단순 베이스라인

    fig2 = create_multi_panel_baseline_plot(
        time, signal, baseline,
        peak_heights=peak_heights,
        sample_name="테스트_샘플",
        output_path='test_multi_panel_broken.png'
    )
    plt.close()

    print("\n테스트 완료!")
