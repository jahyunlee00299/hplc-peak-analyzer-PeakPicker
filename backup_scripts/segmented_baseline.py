"""
Segmented Baseline Correction for HPLC
각 피크마다 독립적인 베이스라인을 생성하는 새로운 접근법
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import interp1d, UnivariateSpline
from scipy.integrate import trapezoid
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class PeakRegion:
    """피크 영역 정보"""
    start_idx: int
    end_idx: int
    peak_idx: int
    baseline: np.ndarray
    corrected: np.ndarray
    area: float


class SegmentedBaselineCorrector:
    """구간별 독립적인 베이스라인 보정"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        self.time = time
        self.intensity = intensity
        self.valleys = []
        self.peak_regions = []

    def find_valleys(self, window_size: int = None, prominence_factor: float = 0.01) -> np.ndarray:
        """
        피크 사이의 valley (골짜기) 지점들을 찾기
        """
        if window_size is None:
            window_size = max(5, len(self.intensity) // 100)
            if window_size % 2 == 0:
                window_size += 1

        # 부드럽게 만들어서 노이즈 제거
        if len(self.intensity) > window_size:
            smoothed = signal.savgol_filter(self.intensity, window_size, 3)
        else:
            smoothed = self.intensity.copy()

        # 역 피크 찾기 (valleys = negative peaks)
        inverted = -smoothed
        valleys, properties = signal.find_peaks(
            inverted,
            prominence=np.ptp(smoothed) * prominence_factor,
            distance=window_size
        )

        # 시작과 끝 점 추가
        valleys = np.concatenate(([0], valleys, [len(self.intensity)-1]))
        valleys = np.unique(valleys)

        self.valleys = valleys
        return valleys

    def segment_baseline(self, method: str = 'valley_to_valley') -> np.ndarray:
        """
        구간별로 다른 베이스라인 생성

        Methods:
        - valley_to_valley: 골짜기에서 골짜기로 연결
        - local_minimum: 각 구간의 최소값 연결
        - adaptive_spline: 구간별 스플라인 피팅
        """
        if len(self.valleys) == 0:
            self.find_valleys()

        baseline = np.zeros_like(self.intensity)

        if method == 'valley_to_valley':
            # Valley 점들을 직선 또는 곡선으로 연결
            valley_intensities = self.intensity[self.valleys]

            # Cubic spline interpolation through valleys
            if len(self.valleys) > 3:
                f = UnivariateSpline(
                    self.valleys,
                    valley_intensities,
                    s=len(self.valleys) * 0.1,
                    k=min(3, len(self.valleys)-1)
                )
                baseline = f(np.arange(len(self.intensity)))
            else:
                # Linear interpolation for few valleys
                f = interp1d(self.valleys, valley_intensities, kind='linear')
                baseline = f(np.arange(len(self.intensity)))

            # 베이스라인이 신호 위로 가지 않도록
            baseline = np.minimum(baseline, self.intensity)

        elif method == 'local_minimum':
            # 각 구간에서 최소값들을 연결
            local_mins = []
            local_min_indices = []

            for i in range(len(self.valleys) - 1):
                start = self.valleys[i]
                end = self.valleys[i + 1]
                segment = self.intensity[start:end]

                if len(segment) > 0:
                    # 구간 내 하위 10% 값들의 평균
                    threshold = np.percentile(segment, 10)
                    min_points = segment[segment <= threshold]
                    if len(min_points) > 0:
                        local_min = np.mean(min_points)
                    else:
                        local_min = np.min(segment)

                    local_mins.append(local_min)
                    local_min_indices.append((start + end) // 2)

            if len(local_mins) > 1:
                # Interpolate between local minima
                f = interp1d(
                    local_min_indices,
                    local_mins,
                    kind='linear',
                    fill_value='extrapolate'
                )
                baseline = f(np.arange(len(self.intensity)))
                baseline = np.minimum(baseline, self.intensity)

        elif method == 'adaptive_spline':
            # 각 구간마다 적응적으로 베이스라인 피팅
            for i in range(len(self.valleys) - 1):
                start = self.valleys[i]
                end = self.valleys[i + 1]

                # 구간 내에서 베이스라인 포인트 선택
                segment = self.intensity[start:end]
                if len(segment) > 10:
                    # 하위 20 percentile 점들 선택
                    threshold = np.percentile(segment, 20)
                    baseline_mask = segment <= threshold

                    if np.sum(baseline_mask) > 2:
                        baseline_indices = np.where(baseline_mask)[0] + start
                        baseline_values = self.intensity[baseline_indices]

                        # 구간 내 스플라인 피팅
                        if len(baseline_indices) > 3:
                            f = UnivariateSpline(
                                baseline_indices,
                                baseline_values,
                                s=len(baseline_indices) * 0.5,
                                k=min(3, len(baseline_indices)-1)
                            )
                            baseline[start:end] = f(np.arange(start, end))
                        else:
                            # Linear interpolation
                            baseline[start:end] = np.linspace(
                                self.intensity[start],
                                self.intensity[end-1],
                                end - start
                            )
                    else:
                        # Fallback to linear
                        baseline[start:end] = np.linspace(
                            self.intensity[start],
                            self.intensity[end-1],
                            end - start
                        )
                else:
                    # 짧은 구간은 선형 보간
                    baseline[start:end] = np.linspace(
                        self.intensity[start],
                        self.intensity[end-1] if end > start else self.intensity[start],
                        end - start
                    )

            # Smooth the baseline
            if len(baseline) > 11:
                baseline = signal.savgol_filter(baseline, 11, 3)

            baseline = np.minimum(baseline, self.intensity)

        return baseline

    def peak_wise_baseline(self) -> Tuple[np.ndarray, List[PeakRegion]]:
        """
        각 피크마다 독립적인 베이스라인 생성
        피크별로 최적화된 베이스라인 적용
        """
        # 먼저 피크 찾기
        peaks, properties = signal.find_peaks(
            self.intensity,
            prominence=np.ptp(self.intensity) * 0.01,
            width=3
        )

        if len(peaks) == 0:
            # 피크가 없으면 전체 베이스라인
            return self.segment_baseline('valley_to_valley'), []

        # 전체 베이스라인 초기화
        full_baseline = np.zeros_like(self.intensity)
        peak_regions = []

        for i, peak_idx in enumerate(peaks):
            # 피크 경계 찾기
            if 'left_bases' in properties and 'right_bases' in properties:
                left_base = properties['left_bases'][i]
                right_base = properties['right_bases'][i]
            else:
                # 수동으로 경계 찾기
                left_base = self._find_peak_boundary(peak_idx, direction='left')
                right_base = self._find_peak_boundary(peak_idx, direction='right')

            # 피크 영역 확장 (조금 더 넓게)
            left_base = max(0, left_base - 5)
            right_base = min(len(self.intensity) - 1, right_base + 5)

            # 이 피크에 대한 베이스라인
            peak_baseline = np.zeros(right_base - left_base + 1)

            # 피크 양끝의 최소값 찾기
            left_region = self.intensity[left_base:min(left_base + 10, peak_idx)]
            right_region = self.intensity[max(peak_idx, right_base - 10):right_base + 1]

            left_min = np.min(left_region) if len(left_region) > 0 else self.intensity[left_base]
            right_min = np.min(right_region) if len(right_region) > 0 else self.intensity[right_base]

            # 베이스라인 타입 결정 (피크 형태에 따라)
            peak_height = self.intensity[peak_idx] - min(left_min, right_min)
            peak_width = right_base - left_base

            if peak_width < 20:
                # 좁은 피크: 선형 베이스라인
                peak_baseline = np.linspace(left_min, right_min, len(peak_baseline))
            else:
                # 넓은 피크: 곡선 베이스라인
                # 피크 영역 내 최소값들 찾기
                segment = self.intensity[left_base:right_base + 1]
                percentile_20 = np.percentile(segment, 20)

                min_indices = np.where(segment <= percentile_20)[0]
                if len(min_indices) > 2:
                    min_values = segment[min_indices]

                    # 스플라인 피팅
                    try:
                        f = UnivariateSpline(
                            min_indices,
                            min_values,
                            s=len(min_indices) * 0.5,
                            k=min(3, len(min_indices)-1)
                        )
                        peak_baseline = f(np.arange(len(peak_baseline)))
                    except:
                        # Fallback to linear
                        peak_baseline = np.linspace(left_min, right_min, len(peak_baseline))
                else:
                    peak_baseline = np.linspace(left_min, right_min, len(peak_baseline))

            # 베이스라인이 피크를 넘지 않도록
            peak_baseline = np.minimum(peak_baseline, segment)

            # 전체 베이스라인에 병합
            full_baseline[left_base:right_base + 1] = peak_baseline

            # 피크 영역 정보 저장
            corrected_segment = segment - peak_baseline
            area = trapezoid(np.maximum(corrected_segment, 0),
                           self.time[left_base:right_base + 1])

            peak_regions.append(PeakRegion(
                start_idx=left_base,
                end_idx=right_base,
                peak_idx=peak_idx,
                baseline=peak_baseline,
                corrected=corrected_segment,
                area=area
            ))

        # 피크 외 영역 처리
        covered = np.zeros(len(self.intensity), dtype=bool)
        for region in peak_regions:
            covered[region.start_idx:region.end_idx + 1] = True

        # 피크 외 영역은 최소값으로
        if not np.all(covered):
            non_peak_indices = np.where(~covered)[0]
            for idx in non_peak_indices:
                # 주변 10 포인트의 최소값
                window_start = max(0, idx - 5)
                window_end = min(len(self.intensity), idx + 6)
                full_baseline[idx] = np.min(self.intensity[window_start:window_end])

        # 부드럽게 만들기
        if len(full_baseline) > 21:
            # 피크 영역은 보존하면서 부드럽게
            smooth_baseline = signal.savgol_filter(full_baseline, 21, 3)
            for region in peak_regions:
                # 피크 영역은 원래 베이스라인 유지
                smooth_baseline[region.start_idx:region.end_idx + 1] = \
                    full_baseline[region.start_idx:region.end_idx + 1]
            full_baseline = smooth_baseline

        self.peak_regions = peak_regions
        return full_baseline, peak_regions

    def _find_peak_boundary(self, peak_idx: int, direction: str = 'left') -> int:
        """피크 경계 찾기"""
        if direction == 'left':
            # 왼쪽으로 가면서 증가가 멈추는 지점 찾기
            for i in range(peak_idx, max(0, peak_idx - 100), -1):
                if i > 0 and self.intensity[i] > self.intensity[i-1]:
                    return i
            return 0
        else:
            # 오른쪽으로 가면서 감소가 멈추는 지점 찾기
            for i in range(peak_idx, min(len(self.intensity), peak_idx + 100)):
                if i < len(self.intensity) - 1 and self.intensity[i] > self.intensity[i+1]:
                    return i
            return len(self.intensity) - 1


def test_segmented_baseline():
    """구간별 베이스라인 테스트"""

    # 두 데이터셋 로드
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

    print(f"\nDataset 1: {len(time1)} points")
    print(f"Dataset 2: {len(time2)} points")

    # 각 데이터셋에 대해 다양한 베이스라인 방법 적용
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))

    for idx, (time, intensity, name) in enumerate([
        (time1, intensity1, 'EXPORT.CSV'),
        (time2, intensity2, 'sample_chromatogram')
    ]):
        corrector = SegmentedBaselineCorrector(time, intensity)

        # 1. Valley-to-valley
        valleys = corrector.find_valleys()
        baseline_v2v = corrector.segment_baseline('valley_to_valley')
        corrected_v2v = intensity - baseline_v2v

        axes[idx, 0].plot(time, intensity, 'b-', alpha=0.5, label='Original')
        axes[idx, 0].plot(time, baseline_v2v, 'r--', label='Valley-to-Valley')
        axes[idx, 0].scatter(time[valleys], intensity[valleys],
                           color='red', s=30, zorder=5, label='Valleys')
        # Adjust y-axis limits
        y_max = np.max(intensity) * 1.1
        axes[idx, 0].set_ylim(np.min(intensity) - y_max * 0.05, y_max)

        axes[idx, 0].set_title(f'{name}\nValley-to-Valley')
        axes[idx, 0].set_xlabel('Time (min)')
        axes[idx, 0].legend(fontsize=8)
        axes[idx, 0].grid(True, alpha=0.3)

        # 2. Local minimum
        baseline_local = corrector.segment_baseline('local_minimum')
        corrected_local = intensity - baseline_local

        axes[idx, 1].plot(time, intensity, 'b-', alpha=0.5, label='Original')
        axes[idx, 1].plot(time, baseline_local, 'g--', label='Local Minimum')
        axes[idx, 1].set_ylim(np.min(intensity) - y_max * 0.05, y_max)
        axes[idx, 1].set_title(f'Local Minimum')
        axes[idx, 1].set_xlabel('Time (min)')
        axes[idx, 1].legend(fontsize=8)
        axes[idx, 1].grid(True, alpha=0.3)

        # 3. Adaptive spline
        baseline_spline = corrector.segment_baseline('adaptive_spline')
        corrected_spline = intensity - baseline_spline

        axes[idx, 2].plot(time, intensity, 'b-', alpha=0.5, label='Original')
        axes[idx, 2].plot(time, baseline_spline, 'm--', label='Adaptive Spline')
        axes[idx, 2].set_ylim(np.min(intensity) - y_max * 0.05, y_max)
        axes[idx, 2].set_title(f'Adaptive Spline')
        axes[idx, 2].set_xlabel('Time (min)')
        axes[idx, 2].legend(fontsize=8)
        axes[idx, 2].grid(True, alpha=0.3)

        # 4. Peak-wise baseline
        baseline_peak, peak_regions = corrector.peak_wise_baseline()
        corrected_peak = intensity - baseline_peak

        axes[idx, 3].plot(time, intensity, 'b-', alpha=0.5, label='Original')
        axes[idx, 3].plot(time, baseline_peak, 'c--', label='Peak-wise', linewidth=2)

        # 각 피크 영역 표시
        colors = plt.cm.rainbow(np.linspace(0, 1, len(peak_regions)))
        for region, color in zip(peak_regions, colors):
            axes[idx, 3].fill_between(
                time[region.start_idx:region.end_idx + 1],
                baseline_peak[region.start_idx:region.end_idx + 1],
                intensity[region.start_idx:region.end_idx + 1],
                alpha=0.3,
                color=color
            )

        axes[idx, 3].set_ylim(np.min(intensity) - y_max * 0.05, y_max)
        axes[idx, 3].set_title(f'Peak-wise ({len(peak_regions)} peaks)')
        axes[idx, 3].set_xlabel('Time (min)')
        axes[idx, 3].legend(fontsize=8)
        axes[idx, 3].grid(True, alpha=0.3)

        # 결과 출력
        print(f"\n{name} Results:")
        print(f"  Valleys found: {len(valleys)}")
        print(f"  Peak regions: {len(peak_regions)}")

        if peak_regions:
            print(f"  Peak details:")
            for i, region in enumerate(peak_regions[:5]):  # 처음 5개만
                print(f"    Peak {i+1}: RT={time[region.peak_idx]:.2f}, Area={region.area:.2f}")

    plt.suptitle('Segmented Baseline Correction Methods', fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig('segmented_baseline_comparison.png', dpi=100, bbox_inches='tight')
    plt.show()

    # 보정된 크로마토그램 비교
    fig2, axes2 = plt.subplots(2, 2, figsize=(12, 8))

    for idx, (time, intensity, name) in enumerate([
        (time1, intensity1, 'EXPORT.CSV'),
        (time2, intensity2, 'sample_chromatogram')
    ]):
        corrector = SegmentedBaselineCorrector(time, intensity)

        # Peak-wise baseline으로 보정
        baseline_peak, peak_regions = corrector.peak_wise_baseline()
        corrected = intensity - baseline_peak

        # 원본
        axes2[idx, 0].plot(time, intensity, 'b-', alpha=0.7)
        axes2[idx, 0].set_title(f'{name} - Original')
        axes2[idx, 0].set_xlabel('Time (min)')
        axes2[idx, 0].set_ylabel('Intensity')
        axes2[idx, 0].grid(True, alpha=0.3)

        # 보정됨
        axes2[idx, 1].plot(time, corrected, 'g-', alpha=0.7)
        axes2[idx, 1].axhline(y=0, color='k', linestyle='-', alpha=0.3)

        # 피크 영역 표시
        for region in peak_regions:
            axes2[idx, 1].fill_between(
                time[region.start_idx:region.end_idx + 1],
                0,
                corrected[region.start_idx:region.end_idx + 1],
                alpha=0.3
            )
            # RT 표시
            axes2[idx, 1].annotate(
                f'{time[region.peak_idx]:.1f}',
                xy=(time[region.peak_idx], corrected[region.peak_idx]),
                xytext=(time[region.peak_idx], corrected[region.peak_idx] + np.max(corrected)*0.05),
                fontsize=8,
                ha='center'
            )

        axes2[idx, 1].set_title(f'{name} - Corrected ({len(peak_regions)} peaks)')
        axes2[idx, 1].set_xlabel('Time (min)')
        axes2[idx, 1].set_ylabel('Intensity')
        axes2[idx, 1].grid(True, alpha=0.3)

    plt.suptitle('Baseline Corrected Chromatograms', fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig('corrected_chromatograms.png', dpi=100, bbox_inches='tight')
    plt.show()

    print("\n" + "="*60)
    print("SEGMENTED BASELINE ANALYSIS COMPLETE")
    print("="*60)
    print("\nKey Features:")
    print("  - Valley-to-valley: Connect valley points")
    print("  - Local minimum: Connect segment minima")
    print("  - Adaptive spline: Adaptive spline per segment")
    print("  - Peak-wise: Independent baseline for each peak")
    print("\nResults saved:")
    print("  - segmented_baseline_comparison.png")
    print("  - corrected_chromatograms.png")


if __name__ == "__main__":
    test_segmented_baseline()