"""
Prominence 값에 따른 피크 검출 변화 시각화
- 다양한 prominence 값으로 테스트
- 17.5분 근처 상세 분석
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from pathlib import Path


def parse_export_csv(filepath):
    """EXPORT.CSV 파일 파싱"""
    data = []
    encodings = ['utf-16', 'utf-8', 'cp1252', 'latin1']
    f = None
    for encoding in encodings:
        try:
            f = open(filepath, 'r', encoding=encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if f is None:
        raise ValueError(f"Could not decode file")

    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                try:
                    time_str = parts[0].replace(' ', '')
                    intensity_str = parts[1].replace(' ', '')
                    time = float(time_str)
                    intensity = float(intensity_str)
                    data.append((time, intensity))
                except ValueError:
                    continue

    time, intensity = zip(*data)
    return np.array(time), np.array(intensity)


def demonstrate_prominence_concept():
    """Prominence 개념 설명 그래프"""
    # 간단한 예제 데이터
    time = np.linspace(0, 10, 1000)

    # 여러 크기의 피크 생성
    large_peak = 100 * np.exp(-((time - 3) ** 2) / 0.3)
    medium_peak = 50 * np.exp(-((time - 5) ** 2) / 0.2)
    small_peak = 20 * np.exp(-((time - 7) ** 2) / 0.15)
    noise = np.random.normal(0, 2, len(time))
    baseline = 10 + 5 * np.sin(time / 2)

    signal_data = baseline + large_peak + medium_peak + small_peak + noise

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('Prominence (Prominence) Concept - How Peak Detection Changes',
                 fontsize=16, fontweight='bold')

    # 다양한 prominence 값 테스트
    prominence_values = [5, 15, 30, 60]
    colors = ['red', 'orange', 'green', 'blue']

    for idx, (ax, prom, color) in enumerate(zip(axes.flat, prominence_values, colors)):
        # 피크 검출
        peaks, properties = signal.find_peaks(signal_data, prominence=prom)

        # 플롯
        ax.plot(time, signal_data, 'b-', linewidth=2, alpha=0.7, label='Signal')
        ax.plot(time, baseline, 'gray', linestyle='--', linewidth=1.5, alpha=0.5, label='Baseline')

        # 검출된 피크 표시
        if len(peaks) > 0:
            ax.plot(time[peaks], signal_data[peaks], 'o',
                   color=color, markersize=12, markeredgecolor='white',
                   markeredgewidth=2, label=f'{len(peaks)} peaks detected', zorder=5)

            # Prominence 표시
            for i, peak in enumerate(peaks):
                prominence = properties['prominences'][i]
                # 피크에서 prominence 만큼 아래로 선 그리기
                contour_height = signal_data[peak] - prominence
                ax.vlines(time[peak], contour_height, signal_data[peak],
                         color=color, linewidth=3, alpha=0.7)

                # 텍스트 추가
                ax.text(time[peak], signal_data[peak] + 5,
                       f'P={prominence:.1f}',
                       ha='center', va='bottom', fontsize=9,
                       fontweight='bold', color=color)

        ax.set_xlabel('Time', fontsize=11, fontweight='bold')
        ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
        ax.set_title(f'Prominence Threshold = {prom}\n({len(peaks)} peaks detected)',
                    fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)

        # prominence 설명 추가
        explanation = f"Prominence >= {prom}\n"
        if len(peaks) == 3:
            explanation += "All peaks detected"
        elif len(peaks) == 2:
            explanation += "Small peak ignored"
        elif len(peaks) == 1:
            explanation += "Only large peak"
        else:
            explanation += "No peaks detected"

        ax.text(0.02, 0.98, explanation, transform=ax.transAxes,
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    return fig


def test_prominence_on_real_data(time, intensity):
    """실제 EXPORT 데이터로 prominence 효과 테스트"""

    # Smoothing
    smoothed = signal.savgol_filter(intensity, 11, 2)

    # 다양한 prominence 값 - 매우 낮은 값까지 테스트
    prominence_values = [2000, 500, 100, 50, 20, 5]

    fig = plt.figure(figsize=(18, 12))

    # 각 prominence에 대해 테스트
    for idx, prom in enumerate(prominence_values, 1):
        ax = plt.subplot(3, 2, idx)

        # 피크 검출
        peaks, properties = signal.find_peaks(
            smoothed,
            prominence=prom,
            height=prom * 0.6,  # min_height도 비례해서 조정
            width=2
        )

        # 전체 크로마토그램
        ax.plot(time, intensity, 'b-', linewidth=0.5, alpha=0.4, label='Raw')
        ax.plot(time, smoothed, 'darkblue', linewidth=1.5, label='Smoothed')

        # 검출된 피크
        colors_peak = plt.cm.tab20(np.linspace(0, 1, len(peaks)))

        for i, (peak, color) in enumerate(zip(peaks, colors_peak), 1):
            left_base = int(properties['left_bases'][i-1])
            right_base = int(properties['right_bases'][i-1])

            # 피크 마커
            ax.plot(time[peak], intensity[peak], 'o',
                   color=color, markersize=8, markeredgecolor='white',
                   markeredgewidth=1.5, zorder=5)

            # 베이스라인
            ax.plot([time[left_base], time[right_base]],
                   [intensity[left_base], intensity[right_base]],
                   '--', color=color, linewidth=1.5, alpha=0.7)

            # 적분 영역
            peak_time = time[left_base:right_base+1]
            peak_int = intensity[left_base:right_base+1]
            baseline_int = np.linspace(intensity[left_base], intensity[right_base], len(peak_int))
            ax.fill_between(peak_time, baseline_int, peak_int, alpha=0.3, color=color)

            # RT 라벨
            if len(peaks) <= 15:  # 너무 많으면 라벨 생략
                ax.text(time[peak], intensity[peak] + 1000, f'{time[peak]:.2f}',
                       ha='center', va='bottom', fontsize=8, color=color, fontweight='bold')

        ax.set_xlabel('Retention Time (min)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Intensity', fontsize=10, fontweight='bold')
        ax.set_title(f'Prominence = {prom} ({len(peaks)} peaks)',
                    fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

        # 특정 영역 피크 수 표시
        peaks_17 = sum(1 for p in peaks if 17 <= time[p] <= 18.5)
        peaks_21 = sum(1 for p in peaks if 20 <= time[p] <= 22)

        info_text = f"17-18.5min: {peaks_17} peak(s)\n20-22min: {peaks_21} peak(s)"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
               fontsize=9, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

    plt.tight_layout()
    return fig


def detailed_region_analysis(time, intensity):
    """17.5분 근처 상세 분석"""

    # Smoothing
    smoothed = signal.savgol_filter(intensity, 11, 2)

    # 17-18.5분 영역 추출
    mask = (time >= 16) & (time <= 19)
    time_region = time[mask]
    intensity_region = intensity[mask]
    smoothed_region = smoothed[mask]

    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.suptitle('17.5 min Region - Detailed Prominence Analysis (Ultra-Low Values)',
                 fontsize=16, fontweight='bold')

    prominence_values = [500, 100, 50, 20, 10, 5]

    for idx, (ax, prom) in enumerate(zip(axes.flat, prominence_values)):
        # 전체 데이터에서 피크 검출
        peaks_all, properties_all = signal.find_peaks(
            smoothed,
            prominence=prom,
            height=prom * 0.6,
            width=2
        )

        # 이 영역의 피크만 필터링
        peaks_in_region = []
        for i, peak in enumerate(peaks_all):
            if 16 <= time[peak] <= 19:
                peaks_in_region.append((peak, i))

        # 플롯
        ax.plot(time_region, intensity_region, 'b-', linewidth=1.5, alpha=0.5, label='Raw')
        ax.plot(time_region, smoothed_region, 'darkblue', linewidth=2.5, label='Smoothed')

        # 검출된 피크 표시
        colors = plt.cm.Set3(np.linspace(0, 1, max(len(peaks_in_region), 1)))

        for j, (peak, orig_idx) in enumerate(peaks_in_region):
            left_base = int(properties_all['left_bases'][orig_idx])
            right_base = int(properties_all['right_bases'][orig_idx])
            prominence_val = properties_all['prominences'][orig_idx]

            color = colors[j]

            # 피크 마커
            ax.plot(time[peak], intensity[peak], 'o',
                   color=color, markersize=12, markeredgecolor='white',
                   markeredgewidth=2, zorder=5)

            # 베이스라인
            if 16 <= time[left_base] <= 19 and 16 <= time[right_base] <= 19:
                ax.plot([time[left_base], time[right_base]],
                       [intensity[left_base], intensity[right_base]],
                       '--', color=color, linewidth=2.5, alpha=0.8)

                # 적분 영역
                mask_peak = (time >= time[left_base]) & (time <= time[right_base])
                t = time[mask_peak]
                y = intensity[mask_peak]
                b = np.linspace(intensity[left_base], intensity[right_base], len(t))
                ax.fill_between(t, b, y, alpha=0.4, color=color)

            # 라벨
            ax.text(time[peak], intensity[peak] + 500,
                   f'{time[peak]:.2f}\nP={prominence_val:.0f}',
                   ha='center', va='bottom', fontsize=9, fontweight='bold',
                   color=color,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                            edgecolor=color, linewidth=2))

        ax.set_xlabel('Retention Time (min)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
        ax.set_title(f'Prominence = {prom} ({len(peaks_in_region)} peaks in region)',
                    fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def main():
    print("=" * 80)
    print("Prominence에 따른 피크 검출 변화 분석")
    print("=" * 80)

    output_dir = Path("analysis_results")
    output_dir.mkdir(exist_ok=True)

    # 1. Prominence 개념 설명
    print("\n[1] Prominence 개념 설명 그래프 생성 중...")
    fig1 = demonstrate_prominence_concept()
    filename1 = output_dir / "prominence_concept.png"
    plt.savefig(filename1, dpi=300, bbox_inches='tight')
    print(f"    저장: {filename1}")
    plt.close()

    # 2. 실제 데이터로 테스트
    print("\n[2] EXPORT.CSV 데이터 로딩 중...")
    filepath = 'peakpicker/examples/EXPORT.CSV'
    time, intensity = parse_export_csv(filepath)
    print(f"    데이터 포인트: {len(time)}")

    print("\n[3] 다양한 prominence 값으로 테스트 중...")
    fig2 = test_prominence_on_real_data(time, intensity)
    filename2 = output_dir / "prominence_comparison_full.png"
    plt.savefig(filename2, dpi=300, bbox_inches='tight')
    print(f"    저장: {filename2}")
    plt.close()

    print("\n[4] 17.5분 근처 상세 분석 중...")
    fig3 = detailed_region_analysis(time, intensity)
    filename3 = output_dir / "prominence_17min_detail.png"
    plt.savefig(filename3, dpi=300, bbox_inches='tight')
    print(f"    저장: {filename3}")
    plt.close()

    # 결과 요약
    print("\n" + "=" * 80)
    print("Prominence 효과 요약")
    print("=" * 80)

    print("\nProminence란?")
    print("  - 피크가 주변 배경(baseline)보다 얼마나 '두드러지는지'를 나타내는 값")
    print("  - 피크 최대값과 가장 가까운 더 높은 피크 사이의 최소 하강 높이")
    print("  - 값이 클수록 작은 피크는 무시됨")

    print("\nProminence 값별 효과:")
    print("  - 2000: 중간 크기 이상 피크 (5개 정도)")
    print("  - 500:  더 민감하게 검출 (10개 이상)")
    print("  - 100:  초민감 (20개 이상)")
    print("  - 50:   극도로 민감 (30개 이상)")
    print("  - 20:   노이즈 포함 시작")
    print("  - 5:    노이즈까지 모두 검출 (50개 이상)")

    print("\n권장:")
    print("  - 17.5분 근처에서 숨은 피크를 찾으려면: prominence=5~50으로 테스트")
    print("  - 주요 피크만 보려면: prominence=2000")
    print("  - 실제 분석용으로는: prominence=100~500 권장")

    print("\n완료! analysis_results/ 폴더에서 결과를 확인하세요.")


if __name__ == "__main__":
    main()
