"""
실제 샘플 크로마토그램 데이터로 피크 검출 테스트
"""

import numpy as np
import matplotlib.pyplot as plt
from peakpicker.modules.data_loader import DataLoader
from peakpicker.modules.visualizer import ChromatogramVisualizer
from peak_detector import PeakDetector


def main():
    print("=" * 70)
    print("실제 샘플 크로마토그램 피크 검출 테스트")
    print("=" * 70)

    # 1. 데이터 로딩
    print("\n[1] 샘플 크로마토그램 데이터 로딩 중...")
    loader = DataLoader()
    time, intensity = loader.load_file('peakpicker/examples/sample_chromatogram.csv')

    data_info = loader.get_data_info()
    print(f"   - 파일: {data_info['file_path']}")
    print(f"   - 데이터 포인트: {data_info['data_points']}")
    print(f"   - 시간 범위: {data_info['time_range'][0]:.2f} ~ {data_info['time_range'][1]:.2f} 분")
    print(f"   - 강도 범위: {data_info['intensity_range'][0]:.1f} ~ {data_info['intensity_range'][1]:.1f}")
    print(f"   - 평균 강도: {data_info['intensity_mean']:.1f}")
    print(f"   - 표준편차: {data_info['intensity_std']:.1f}")

    # 데이터 범위에 맞게 자동으로 파라미터 계산
    intensity_mean = np.mean(intensity)
    intensity_std = np.std(intensity)
    intensity_max = np.max(intensity)

    # prominence: 표준편차의 2배
    prominence = 2 * intensity_std
    # min_height: 평균 + 표준편차
    min_height = intensity_mean + intensity_std

    print(f"\n[2] 자동 계산된 피크 검출 파라미터:")
    print(f"   - prominence (돌출도): {prominence:.1f}")
    print(f"   - min_height (최소 높이): {min_height:.1f}")
    print(f"   - min_width (최소 폭): 0.02 분")

    # 2. 피크 검출
    print(f"\n[3] 피크 검출 중...")
    detector = PeakDetector(
        time=time,
        intensity=intensity,
        prominence=prominence,
        min_height=min_height,
        min_width=0.02,  # 최소 폭
    )
    peaks = detector.detect_peaks()

    print(f"   - 검출된 피크 수: {len(peaks)}")

    if len(peaks) > 0:
        print(f"\n   검출된 피크 상세 정보:")
        print(f"   {'No':<4} {'RT (min)':<10} {'높이':<12} {'면적':<15} {'폭 (min)':<10}")
        print(f"   {'-' * 60}")

        for i, peak in enumerate(peaks, 1):
            print(f"   {i:<4} {peak.rt:<10.3f} {peak.height:<12.1f} {peak.area:<15.2f} {peak.width:<10.3f}")

        # 3. 통계 요약
        summary = detector.get_summary()
        print(f"\n[4] 통계 요약:")
        print(f"   - 총 피크 수: {summary['num_peaks']}")
        print(f"   - 총 면적: {summary['total_area']:.2f}")
        print(f"   - 평균 피크 높이: {summary['avg_peak_height']:.1f}")
        print(f"   - 평균 피크 폭: {summary['avg_peak_width']:.3f} 분")
    else:
        print("   - 검출된 피크가 없습니다!")
        print("   - 파라미터를 조정해보세요.")

    # 4. 시각화
    print(f"\n[5] 크로마토그램 시각화 중...")

    # 4.1 전체 크로마토그램
    visualizer = ChromatogramVisualizer(figsize=(14, 8))
    fig = visualizer.plot_chromatogram(
        time=time,
        intensity=intensity,
        title="Sample Chromatogram - Peak Detection Results",
        xlabel="Retention Time (min)",
        ylabel="Intensity",
        color="navy",
        linewidth=1.5,
    )

    # 검출된 피크 마커 추가
    if len(peaks) > 0:
        peak_times = np.array([p.rt for p in peaks])
        peak_intensities = np.array([intensity[p.index] for p in peaks])
        visualizer.add_peak_markers(
            peak_times=peak_times,
            peak_intensities=peak_intensities,
            marker_style='ro',
            marker_size=10,
        )

        # 피크 영역 표시 (베이스라인)
        ax = visualizer.ax
        for i, peak in enumerate(peaks, 1):
            # 피크 베이스라인
            baseline_y = [intensity[peak.index_start], intensity[peak.index_end]]
            baseline_x = [time[peak.index_start], time[peak.index_end]]
            ax.plot(baseline_x, baseline_y, 'g--', linewidth=2, alpha=0.7)

            # 피크 영역 음영
            peak_time = time[peak.index_start:peak.index_end+1]
            peak_int = intensity[peak.index_start:peak.index_end+1]
            baseline_int = np.linspace(intensity[peak.index_start],
                                       intensity[peak.index_end],
                                       len(peak_int))
            ax.fill_between(peak_time, baseline_int, peak_int, alpha=0.3, color='green')

            # 피크 번호 표시
            offset = (intensity_max - intensity_mean) * 0.05
            ax.text(peak.rt, intensity[peak.index] + offset, f'{i}',
                    ha='center', va='bottom', fontsize=12, fontweight='bold', color='red')

    plt.tight_layout()
    plt.savefig('sample_chromatogram_peaks.png', dpi=300, bbox_inches='tight')
    print(f"   - 전체 그래프 저장: sample_chromatogram_peaks.png")

    # 4.2 개별 피크 상세 보기
    if len(peaks) > 0:
        num_peaks_to_show = min(6, len(peaks))
        rows = 2
        cols = 3
        fig2, axes = plt.subplots(rows, cols, figsize=(15, 8))
        fig2.suptitle('Individual Peak Details', fontsize=16, fontweight='bold')

        for i in range(num_peaks_to_show):
            peak = peaks[i]
            ax = axes.flat[i]

            # 피크 주변 영역 추출
            margin = min(50, peak.index_start)
            start_idx = max(0, peak.index_start - margin)
            end_idx = min(len(time), peak.index_end + margin)

            peak_time = time[start_idx:end_idx]
            peak_int = intensity[start_idx:end_idx]

            # 베이스라인
            baseline_int = np.linspace(intensity[peak.index_start],
                                       intensity[peak.index_end],
                                       peak.index_end - peak.index_start + 1)
            baseline_time = time[peak.index_start:peak.index_end+1]

            # 플롯
            ax.plot(peak_time, peak_int, 'b-', linewidth=2, label='Signal')
            ax.plot(baseline_time, baseline_int, 'r--', linewidth=2, label='Baseline')
            ax.plot([peak.rt], [intensity[peak.index]], 'ro', markersize=10, label='Peak Max')

            # 적분 영역 음영
            integration_int = intensity[peak.index_start:peak.index_end+1]
            ax.fill_between(baseline_time, baseline_int, integration_int,
                           alpha=0.3, color='green', label='Integration Area')

            # 레이블
            ax.set_xlabel('RT (min)', fontsize=10)
            ax.set_ylabel('Intensity', fontsize=10)
            ax.set_title(f'Peak {i+1}: RT={peak.rt:.2f}, Area={peak.area:.2f}',
                        fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8, loc='best')

        # 사용하지 않는 subplot 숨기기
        for i in range(num_peaks_to_show, rows * cols):
            axes.flat[i].set_visible(False)

        plt.tight_layout()
        plt.savefig('sample_peaks_detail.png', dpi=300, bbox_inches='tight')
        print(f"   - 개별 피크 그래프 저장: sample_peaks_detail.png")

    print(f"\n완료! 생성된 그래프 파일:")
    print(f"  - sample_chromatogram_peaks.png (전체 크로마토그램)")
    if len(peaks) > 0:
        print(f"  - sample_peaks_detail.png (개별 피크 상세)")

    # 그래프 표시
    plt.show()


if __name__ == "__main__":
    main()
