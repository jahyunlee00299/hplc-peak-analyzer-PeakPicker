"""
크로마토그램 피크 검출 테스트 스크립트
- 합성 크로마토그램 데이터 생성
- 피크 검출 및 적분
- 시각화
"""

import numpy as np
import matplotlib.pyplot as plt
from peak_detector import PeakDetector
from peakpicker.modules.visualizer import ChromatogramVisualizer


def create_synthetic_chromatogram():
    """합성 크로마토그램 데이터 생성 (가우시안 피크들)"""
    # 시간 축: 0~30분, 3000 데이터 포인트
    time = np.linspace(0, 30, 3000)

    # 노이즈 추가
    noise = np.random.normal(0, 5000, len(time))

    # 베이스라인 (약간의 드리프트)
    baseline = 10000 + 2000 * np.sin(time / 10)

    # 여러 가우시안 피크 생성
    peaks_config = [
        {'center': 5.2, 'height': 150000, 'width': 0.3},   # 피크 1
        {'center': 8.7, 'height': 220000, 'width': 0.25},  # 피크 2
        {'center': 12.5, 'height': 95000, 'width': 0.4},   # 피크 3
        {'center': 15.8, 'height': 180000, 'width': 0.35}, # 피크 4
        {'center': 19.3, 'height': 130000, 'width': 0.28}, # 피크 5
        {'center': 24.1, 'height': 160000, 'width': 0.32}, # 피크 6
    ]

    # 신호 생성
    signal = baseline.copy()
    for peak in peaks_config:
        gaussian = peak['height'] * np.exp(
            -((time - peak['center']) ** 2) / (2 * peak['width'] ** 2)
        )
        signal += gaussian

    # 노이즈 추가
    signal += noise

    return time, signal, peaks_config


def main():
    print("=" * 70)
    print("크로마토그램 피크 검출 및 측정 테스트")
    print("=" * 70)

    # 1. 합성 크로마토그램 생성
    print("\n[1] 합성 크로마토그램 데이터 생성 중...")
    time, intensity, expected_peaks = create_synthetic_chromatogram()
    print(f"   - 데이터 포인트: {len(time)}")
    print(f"   - 시간 범위: {time[0]:.2f} ~ {time[-1]:.2f} 분")
    print(f"   - 강도 범위: {intensity.min():.0f} ~ {intensity.max():.0f}")
    print(f"   - 예상 피크 수: {len(expected_peaks)}")

    # 2. 피크 검출
    print("\n[2] 피크 검출 중...")
    detector = PeakDetector(
        time=time,
        intensity=intensity,
        prominence=50000,    # 피크 돌출도 (prominence)
        min_height=30000,    # 최소 높이
        min_width=0.05,      # 최소 폭 (분)
    )
    peaks = detector.detect_peaks()

    print(f"   - 검출된 피크 수: {len(peaks)}")
    print(f"\n   검출된 피크 상세 정보:")
    print(f"   {'No':<4} {'RT (min)':<10} {'높이':<12} {'면적':<15} {'폭 (min)':<10}")
    print(f"   {'-' * 60}")

    total_area = 0
    for i, peak in enumerate(peaks, 1):
        print(f"   {i:<4} {peak.rt:<10.3f} {peak.height:<12.0f} {peak.area:<15.1f} {peak.width:<10.3f}")
        total_area += peak.area

    # 3. 통계 요약
    summary = detector.get_summary()
    print(f"\n[3] 통계 요약:")
    print(f"   - 총 피크 수: {summary['num_peaks']}")
    print(f"   - 총 면적: {summary['total_area']:.1f}")
    print(f"   - 평균 피크 높이: {summary['avg_peak_height']:.1f}")
    print(f"   - 평균 피크 폭: {summary['avg_peak_width']:.3f} 분")

    # 4. 시각화
    print(f"\n[4] 크로마토그램 시각화 중...")

    # 4.1 전체 크로마토그램
    visualizer = ChromatogramVisualizer(figsize=(14, 8))
    fig = visualizer.plot_chromatogram(
        time=time,
        intensity=intensity,
        title="HPLC 크로마토그램 - 피크 검출 결과",
        xlabel="보유 시간 (Retention Time, 분)",
        ylabel="신호 강도 (Intensity)",
        color="navy",
        linewidth=1.2,
    )

    # 검출된 피크 마커 추가
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
        ax.plot(baseline_x, baseline_y, 'g--', linewidth=1.5, alpha=0.7)

        # 피크 영역 음영
        peak_time = time[peak.index_start:peak.index_end+1]
        peak_int = intensity[peak.index_start:peak.index_end+1]
        baseline_int = np.linspace(intensity[peak.index_start],
                                   intensity[peak.index_end],
                                   len(peak_int))
        ax.fill_between(peak_time, baseline_int, peak_int, alpha=0.2, color='green')

        # 피크 번호 표시
        ax.text(peak.rt, intensity[peak.index] + 10000, f'{i}',
                ha='center', va='bottom', fontsize=12, fontweight='bold', color='red')

    plt.tight_layout()
    plt.savefig('chromatogram_with_peaks.png', dpi=300, bbox_inches='tight')
    print(f"   - 그래프 저장: chromatogram_with_peaks.png")

    # 4.2 개별 피크 상세 보기 (첫 3개 피크)
    fig2, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig2.suptitle('개별 피크 상세 분석', fontsize=16, fontweight='bold')

    for i, (peak, ax) in enumerate(zip(peaks[:6], axes.flat), 1):
        # 피크 주변 영역 추출
        margin = 50  # 데이터 포인트
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
        ax.plot(peak_time, peak_int, 'b-', linewidth=1.5, label='Signal')
        ax.plot(baseline_time, baseline_int, 'r--', linewidth=1.5, label='Baseline')
        ax.plot([peak.rt], [intensity[peak.index]], 'ro', markersize=8, label='Peak Max')

        # 적분 영역 음영
        integration_int = intensity[peak.index_start:peak.index_end+1]
        ax.fill_between(baseline_time, baseline_int, integration_int,
                       alpha=0.3, color='green', label='Integration Area')

        # 레이블
        ax.set_xlabel('RT (min)', fontsize=10)
        ax.set_ylabel('Intensity', fontsize=10)
        ax.set_title(f'피크 {i}: RT={peak.rt:.2f}, Area={peak.area:.0f}',
                    fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig('individual_peaks_detail.png', dpi=300, bbox_inches='tight')
    print(f"   - 개별 피크 그래프 저장: individual_peaks_detail.png")

    # 5. 피크 측정 방법 설명
    print(f"\n[5] 피크 측정 방법:")
    print(f"   ┌─────────────────────────────────────────────────────────────┐")
    print(f"   │ 1. 피크 검출 (Peak Detection)                               │")
    print(f"   │    - scipy.signal.find_peaks() 사용                         │")
    print(f"   │    - prominence (돌출도): {detector.prominence}             │")
    print(f"   │    - min_height (최소 높이): {detector.min_height}          │")
    print(f"   │    - min_width (최소 폭): {detector.min_width} 분            │")
    print(f"   │                                                             │")
    print(f"   │ 2. 베이스라인 설정                                           │")
    print(f"   │    - 피크 시작점과 끝점을 자동으로 찾음                      │")
    print(f"   │    - 두 점을 연결한 직선을 베이스라인으로 사용               │")
    print(f"   │                                                             │")
    print(f"   │ 3. 피크 면적 계산 (Integration)                             │")
    print(f"   │    - 베이스라인을 뺀 신호를 적분                            │")
    print(f"   │    - 사다리꼴 적분법 (Trapezoidal rule) 사용                │")
    print(f"   │    - 면적 = ∫(신호 - 베이스라인) dt                        │")
    print(f"   │                                                             │")
    print(f"   │ 4. 피크 높이 (Height)                                       │")
    print(f"   │    - 피크 최대값에서 베이스라인 값을 뺀 값                  │")
    print(f"   │                                                             │")
    print(f"   │ 5. 피크 폭 (Width)                                          │")
    print(f"   │    - 반치전폭 (FWHM: Full Width at Half Maximum)            │")
    print(f"   │    - 피크 높이의 50% 지점에서의 폭                          │")
    print(f"   └─────────────────────────────────────────────────────────────┘")

    print(f"\n완료! 생성된 그래프 파일:")
    print(f"  - chromatogram_with_peaks.png (전체 크로마토그램)")
    print(f"  - individual_peaks_detail.png (개별 피크 상세)")
    print(f"\n그래프를 확인하여 피크가 어떻게 측정되는지 확인하세요!")

    # 그래프 표시
    plt.show()


if __name__ == "__main__":
    main()
