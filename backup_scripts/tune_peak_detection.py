"""
피크 검출 파라미터 조정 및 테스트
- 17.5분과 21분 피크 구분
- 9.58분 피크 베이스라인 조정 (8.5-10분)
"""

import numpy as np
import pandas as pd
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
        raise ValueError(f"Could not decode file {filepath}")

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

    if not data:
        raise ValueError("No valid data found")

    time, intensity = zip(*data)
    return np.array(time), np.array(intensity)


def test_parameters(time, intensity, prominence, min_height, min_width, smooth_window=11):
    """
    다양한 파라미터로 피크 검출 테스트
    """
    # Smoothing
    if smooth_window > 0:
        time_per_sample = np.mean(np.diff(time))
        min_width_samples = max(1, int(min_width / time_per_sample))
        window_size = max(3, min(smooth_window, len(intensity) // 4))
        if window_size % 2 == 0:
            window_size += 1
        smoothed = signal.savgol_filter(intensity, window_size, 2)
    else:
        smoothed = intensity.copy()

    # 피크 검출
    time_per_sample = np.mean(np.diff(time))
    min_width_samples = max(1, int(min_width / time_per_sample))

    peak_indices, properties = signal.find_peaks(
        smoothed,
        prominence=prominence,
        height=min_height,
        width=min_width_samples,
        rel_height=0.5,
    )

    return peak_indices, properties, smoothed


def visualize_peaks_detailed(time, intensity, peak_indices, properties, smoothed,
                             params_text, focus_regions=None):
    """
    피크 검출 결과를 상세하게 시각화
    """
    fig = plt.figure(figsize=(18, 12))

    # 1. 전체 크로마토그램
    ax1 = plt.subplot(3, 1, 1)
    ax1.plot(time, intensity, 'b-', linewidth=0.8, alpha=0.6, label='Raw Signal')
    ax1.plot(time, smoothed, 'darkblue', linewidth=1.5, label='Smoothed Signal')

    # 피크 표시
    colors = plt.cm.tab20(np.linspace(0, 1, len(peak_indices)))
    for i, (peak_idx, color) in enumerate(zip(peak_indices, colors), 1):
        left_base = int(properties['left_bases'][i-1])
        right_base = int(properties['right_bases'][i-1])

        # 피크 마커
        ax1.plot(time[peak_idx], intensity[peak_idx], 'o',
                color=color, markersize=10, markeredgecolor='white',
                markeredgewidth=2, zorder=5)

        # 베이스라인
        baseline_x = [time[left_base], time[peak_idx], time[right_base]]
        baseline_y = [intensity[left_base],
                     intensity[left_base] + (intensity[right_base] - intensity[left_base]) *
                     (time[peak_idx] - time[left_base]) / (time[right_base] - time[left_base]),
                     intensity[right_base]]
        ax1.plot([time[left_base], time[right_base]],
                [intensity[left_base], intensity[right_base]],
                '--', color=color, linewidth=2, alpha=0.8)

        # 적분 영역
        peak_time = time[left_base:right_base+1]
        peak_int = intensity[left_base:right_base+1]
        baseline_int = np.linspace(intensity[left_base], intensity[right_base], len(peak_int))
        ax1.fill_between(peak_time, baseline_int, peak_int, alpha=0.3, color=color)

        # RT 라벨
        ax1.text(time[peak_idx], intensity[peak_idx] + 2000,
                f'#{i}\n{time[peak_idx]:.2f}min',
                ha='center', va='bottom', fontsize=9, fontweight='bold',
                color=color, bbox=dict(boxstyle='round,pad=0.4',
                facecolor='white', edgecolor=color, linewidth=2))

    ax1.set_xlabel('Retention Time (min)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Intensity', fontsize=12, fontweight='bold')
    ax1.set_title(f'Peak Detection Results - {len(peak_indices)} Peaks\n{params_text}',
                 fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 2. 관심 영역 1: 8-11분 (9.58분 피크)
    ax2 = plt.subplot(3, 2, 3)
    region_mask = (time >= 8) & (time <= 11)
    plot_region(ax2, time[region_mask], intensity[region_mask], smoothed[region_mask],
               peak_indices, properties, time, intensity, '8-11 min (Peak around 9.58)', colors)

    # 3. 관심 영역 2: 17-18.5분 (17.5분 근처)
    ax3 = plt.subplot(3, 2, 4)
    region_mask = (time >= 16.5) & (time <= 18.5)
    plot_region(ax3, time[region_mask], intensity[region_mask], smoothed[region_mask],
               peak_indices, properties, time, intensity, '16.5-18.5 min (around 17.5)', colors)

    # 4. 관심 영역 3: 20-22분 (21분 근처)
    ax4 = plt.subplot(3, 2, 5)
    region_mask = (time >= 19.5) & (time <= 22)
    plot_region(ax4, time[region_mask], intensity[region_mask], smoothed[region_mask],
               peak_indices, properties, time, intensity, '19.5-22 min (around 21)', colors)

    # 5. 피크 정보 테이블
    ax5 = plt.subplot(3, 2, 6)
    ax5.axis('off')

    peak_info = "Peak Detection Summary\n" + "="*50 + "\n\n"
    peak_info += f"{'#':<3} {'RT (min)':<10} {'Height':<12} {'Width (min)':<12} {'Start':<10} {'End':<10}\n"
    peak_info += "-"*70 + "\n"

    for i, peak_idx in enumerate(peak_indices, 1):
        left_base = int(properties['left_bases'][i-1])
        right_base = int(properties['right_bases'][i-1])
        width = properties['widths'][i-1] * np.mean(np.diff(time))
        height = properties['peak_heights'][i-1]

        peak_info += f"{i:<3} {time[peak_idx]:<10.3f} {height:<12.0f} {width:<12.3f} "
        peak_info += f"{time[left_base]:<10.3f} {time[right_base]:<10.3f}\n"

    ax5.text(0.05, 0.95, peak_info, transform=ax5.transAxes,
            fontsize=9, verticalalignment='top', family='monospace',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

    plt.tight_layout()
    return fig


def plot_region(ax, time_region, intensity_region, smoothed_region,
               peak_indices, properties, time_full, intensity_full, title, colors):
    """관심 영역 플롯"""
    ax.plot(time_region, intensity_region, 'b-', linewidth=1.5, alpha=0.5, label='Raw')
    ax.plot(time_region, smoothed_region, 'darkblue', linewidth=2, label='Smoothed')

    # 이 영역의 피크만 표시
    for i, (peak_idx, color) in enumerate(zip(peak_indices, colors), 1):
        if time_region[0] <= time_full[peak_idx] <= time_region[-1]:
            left_base = int(properties['left_bases'][i-1])
            right_base = int(properties['right_bases'][i-1])

            # 피크 마커
            ax.plot(time_full[peak_idx], intensity_full[peak_idx], 'o',
                   color=color, markersize=12, markeredgecolor='white',
                   markeredgewidth=2, zorder=5)

            # 베이스라인
            ax.plot([time_full[left_base], time_full[right_base]],
                   [intensity_full[left_base], intensity_full[right_base]],
                   '--', color=color, linewidth=2.5, alpha=0.8)

            # 적분 영역
            mask = (time_region >= time_full[left_base]) & (time_region <= time_full[right_base])
            if np.any(mask):
                t = time_region[mask]
                y = intensity_region[mask]
                baseline = np.linspace(intensity_full[left_base], intensity_full[right_base], len(t))
                ax.fill_between(t, baseline, y, alpha=0.4, color=color)

            # 라벨
            ax.text(time_full[peak_idx], intensity_full[peak_idx] + 1000,
                   f'#{i}\n{time_full[peak_idx]:.2f}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold',
                   color=color)

    ax.set_xlabel('RT (min)', fontsize=10, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=10, fontweight='bold')
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def main():
    print("=" * 80)
    print("피크 검출 파라미터 조정 - EXPORT.CSV")
    print("=" * 80)

    # 데이터 로드
    filepath = 'peakpicker/examples/EXPORT.CSV'
    time, intensity = parse_export_csv(filepath)

    print(f"\n데이터 정보:")
    print(f"  - 포인트 수: {len(time)}")
    print(f"  - 시간 범위: {time[0]:.2f} ~ {time[-1]:.2f} 분")
    print(f"  - 강도 범위: {intensity.min():.1f} ~ {intensity.max():.1f}")

    # 여러 파라미터 세트 테스트
    test_cases = [
        {
            'name': 'Case 1: Current (기본 설정)',
            'prominence': 4646.8,
            'min_height': 3012.8,
            'min_width': 0.01,
            'smooth_window': 11
        },
        {
            'name': 'Case 2: More Sensitive (더 민감하게)',
            'prominence': 2000,
            'min_height': 1500,
            'min_width': 0.005,
            'smooth_window': 11
        },
        {
            'name': 'Case 3: Very Sensitive (매우 민감하게)',
            'prominence': 1000,
            'min_height': 800,
            'min_width': 0.003,
            'smooth_window': 9
        },
        {
            'name': 'Case 4: Ultra Sensitive (초민감)',
            'prominence': 500,
            'min_height': 500,
            'min_width': 0.002,
            'smooth_window': 7
        },
    ]

    output_dir = Path("analysis_results")
    output_dir.mkdir(exist_ok=True)

    for idx, case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"{case['name']}")
        print(f"{'='*80}")
        print(f"  prominence: {case['prominence']}")
        print(f"  min_height: {case['min_height']}")
        print(f"  min_width: {case['min_width']}")
        print(f"  smooth_window: {case['smooth_window']}")

        # 피크 검출
        peak_indices, properties, smoothed = test_parameters(
            time, intensity,
            prominence=case['prominence'],
            min_height=case['min_height'],
            min_width=case['min_width'],
            smooth_window=case['smooth_window']
        )

        print(f"\n  검출된 피크 수: {len(peak_indices)}")

        # 특정 영역의 피크 확인
        peaks_8_11 = [i for i, idx in enumerate(peak_indices)
                      if 8 <= time[idx] <= 11]
        peaks_17_18 = [i for i, idx in enumerate(peak_indices)
                       if 17 <= time[idx] <= 18.5]
        peaks_20_22 = [i for i, idx in enumerate(peak_indices)
                       if 20 <= time[idx] <= 22]

        print(f"\n  영역별 피크 수:")
        print(f"    8-11분 영역: {len(peaks_8_11)}개")
        if peaks_8_11:
            for i in peaks_8_11:
                print(f"      - Peak at {time[peak_indices[i]]:.2f} min")

        print(f"    17-18.5분 영역: {len(peaks_17_18)}개")
        if peaks_17_18:
            for i in peaks_17_18:
                print(f"      - Peak at {time[peak_indices[i]]:.2f} min")

        print(f"    20-22분 영역: {len(peaks_20_22)}개")
        if peaks_20_22:
            for i in peaks_20_22:
                print(f"      - Peak at {time[peak_indices[i]]:.2f} min")

        # 시각화
        params_text = (f"prominence={case['prominence']}, min_height={case['min_height']}, "
                      f"min_width={case['min_width']}, smooth={case['smooth_window']}")

        fig = visualize_peaks_detailed(
            time, intensity, peak_indices, properties, smoothed,
            params_text
        )

        filename = output_dir / f"peak_tuning_case{idx}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"\n  그래프 저장: {filename}")
        plt.close()

    print(f"\n{'='*80}")
    print("완료! analysis_results/ 폴더에서 결과를 확인하세요.")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
