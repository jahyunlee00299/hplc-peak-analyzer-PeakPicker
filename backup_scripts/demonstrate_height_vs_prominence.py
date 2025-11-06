"""
Height vs Prominence 차이 설명
- 같은 높이의 피크라도 prominence는 주변 환경에 따라 달라짐
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from pathlib import Path


def create_comparison_example():
    """같은 높이, 다른 prominence 시나리오"""

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('Height vs Prominence - 왜 다를까?', fontsize=16, fontweight='bold')

    # 시나리오 1: 고립된 피크 (Prominence ≈ Height)
    ax = axes[0, 0]
    time1 = np.linspace(0, 10, 1000)
    peak1 = 100 * np.exp(-((time1 - 5) ** 2) / 0.3)
    baseline1 = 10
    signal1 = baseline1 + peak1

    peaks1, props1 = signal.find_peaks(signal1, prominence=1)

    ax.plot(time1, signal1, 'b-', linewidth=2.5, label='Signal')
    if len(peaks1) > 0:
        peak_idx = peaks1[0]
        height = signal1[peak_idx]
        prom = props1['prominences'][0]
        contour = height - prom

        ax.plot(time1[peak_idx], height, 'ro', markersize=15,
               markeredgecolor='white', markeredgewidth=2, label='Peak')
        ax.hlines(contour, 0, 10, colors='red', linestyles='--', linewidth=2, label='Contour Line')
        ax.vlines(time1[peak_idx], contour, height, colors='green', linewidth=5, label='Prominence')
        ax.hlines(baseline1, 0, 10, colors='gray', linestyles=':', linewidth=1.5, alpha=0.5)

        ax.text(5, height + 5, f'Height = {height:.0f}', ha='center', fontsize=11, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))
        ax.text(7, (height + contour) / 2, f'Prominence\n= {prom:.0f}', ha='center', fontsize=11,
               fontweight='bold', color='green',
               bbox=dict(boxstyle='round', facecolor='white', edgecolor='green', linewidth=2))

    ax.set_title('시나리오 1: 고립된 피크\nProminence ≈ Height', fontsize=12, fontweight='bold')
    ax.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 시나리오 2: 더 큰 피크 옆의 작은 피크 (Prominence << Height)
    ax = axes[0, 1]
    time2 = np.linspace(0, 10, 1000)
    large_peak = 150 * np.exp(-((time2 - 3) ** 2) / 0.4)
    small_peak = 100 * np.exp(-((time2 - 6) ** 2) / 0.3)  # 높이는 100이지만...
    baseline2 = 10
    signal2 = baseline2 + large_peak + small_peak

    peaks2, props2 = signal.find_peaks(signal2, prominence=1)

    ax.plot(time2, signal2, 'b-', linewidth=2.5, label='Signal')

    # 두 피크 표시
    colors = ['orange', 'purple']
    for i, (peak_idx, color) in enumerate(zip(peaks2, colors)):
        height = signal2[peak_idx]
        prom = props2['prominences'][i]
        contour = height - prom
        left_base = int(props2['left_bases'][i])
        right_base = int(props2['right_bases'][i])

        ax.plot(time2[peak_idx], height, 'o', markersize=15, color=color,
               markeredgecolor='white', markeredgewidth=2)
        ax.hlines(contour, time2[left_base], time2[right_base],
                 colors=color, linestyles='--', linewidth=2)
        ax.vlines(time2[peak_idx], contour, height, colors=color, linewidth=5)

        ax.text(time2[peak_idx], height + 10,
               f'H={height:.0f}',
               ha='center', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

        ax.text(time2[peak_idx] - 0.5, (height + contour) / 2,
               f'P={prom:.0f}',
               ha='center', fontsize=10, fontweight='bold', color=color,
               bbox=dict(boxstyle='round', facecolor='white', edgecolor=color, linewidth=2))

    ax.set_title('시나리오 2: 큰 피크 옆의 작은 피크\n작은 피크: Prominence << Height',
                fontsize=12, fontweight='bold')
    ax.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)

    # 시나리오 3: 숄더 피크 (매우 작은 Prominence)
    ax = axes[1, 0]
    time3 = np.linspace(0, 10, 1000)
    main_peak = 150 * np.exp(-((time3 - 5) ** 2) / 0.5)
    shoulder = 80 * np.exp(-((time3 - 6.5) ** 2) / 0.2)  # 숄더
    baseline3 = 10
    signal3 = baseline3 + main_peak + shoulder

    peaks3, props3 = signal.find_peaks(signal3, prominence=1)

    ax.plot(time3, signal3, 'b-', linewidth=2.5, label='Signal')

    colors = ['darkgreen', 'red']
    labels = ['Main Peak', 'Shoulder']
    for i, (peak_idx, color, label) in enumerate(zip(peaks3, colors, labels)):
        height = signal3[peak_idx]
        prom = props3['prominences'][i]
        contour = height - prom
        left_base = int(props3['left_bases'][i])
        right_base = int(props3['right_bases'][i])

        ax.plot(time3[peak_idx], height, 'o', markersize=15, color=color,
               markeredgecolor='white', markeredgewidth=2, label=label)
        ax.hlines(contour, time3[left_base], time3[right_base],
                 colors=color, linestyles='--', linewidth=2)
        ax.vlines(time3[peak_idx], contour, height, colors=color, linewidth=5)

        ax.text(time3[peak_idx], height + 8,
               f'H={height:.0f}',
               ha='center', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

        ax.text(time3[peak_idx] + 0.5, (height + contour) / 2,
               f'P={prom:.0f}',
               ha='center', fontsize=10, fontweight='bold', color=color,
               bbox=dict(boxstyle='round', facecolor='white', edgecolor=color, linewidth=2))

    ax.set_title('시나리오 3: 숄더 피크 (Shoulder Peak)\n숄더: Height는 있지만 Prominence 매우 작음',
                fontsize=12, fontweight='bold')
    ax.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 시나리오 4: 비교 요약
    ax = axes[1, 1]
    ax.axis('off')

    summary = """
    핵심 정리: Height vs Prominence

    Height (피크 높이):
      • 피크의 절대적 높이
      • Baseline에서 피크 정상까지의 거리

    Prominence (두드러짐):
      • 피크가 주변보다 얼마나 "돋보이는지"
      • 주변 환경에 따라 완전히 달라짐


    같은 Height라도 Prominence가 다른 경우:

    ✓ 고립된 피크:
      → Prominence ≈ Height
      → 예: Height=100, Prominence=95

    ✗ 큰 피크 옆의 작은 피크:
      → Prominence << Height
      → 예: Height=100, Prominence=30
         (두 피크 사이 valley가 70이면)

    ✗ 숄더 피크 (Shoulder):
      → Prominence 매우 작음
      → 예: Height=80, Prominence=10
         (메인 피크의 측면에 붙어있음)


    왜 Prominence가 중요한가?

    • Height만 보면:
      숄더도 진짜 피크로 잘못 인식

    • Prominence로 필터링:
      진짜 독립적인 피크만 선택 가능


    실전 예시:

    prominence=50 사용:
      • 고립 피크 (P=95) → 검출 ✓
      • 작은 피크 (P=30) → 무시 ✗
      • 숄더 (P=10) → 무시 ✗
    """

    ax.text(0.5, 0.5, summary, transform=ax.transAxes,
           fontsize=11, verticalalignment='center', horizontalalignment='center',
           family='monospace',
           bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

    plt.tight_layout()
    return fig


def real_data_example():
    """실제 데이터에서 height vs prominence 비교"""

    # 데이터 로딩
    filepath = 'peakpicker/examples/EXPORT.CSV'
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
    time = np.array(time)
    intensity = np.array(intensity)

    # Smoothing
    smoothed = signal.savgol_filter(intensity, 11, 2)

    # 매우 낮은 prominence로 많은 피크 검출
    peaks, properties = signal.find_peaks(smoothed, prominence=100, height=600, width=2)

    fig, axes = plt.subplots(2, 1, figsize=(18, 10))
    fig.suptitle('실제 데이터: Height와 Prominence 비교', fontsize=16, fontweight='bold')

    # 전체 크로마토그램
    ax = axes[0]
    ax.plot(time, smoothed, 'darkblue', linewidth=1.5, label='Smoothed Signal')

    colors = plt.cm.tab20(np.linspace(0, 1, len(peaks)))

    for i, (peak_idx, color) in enumerate(zip(peaks, colors)):
        height = smoothed[peak_idx]
        prom = properties['prominences'][i]

        ax.plot(time[peak_idx], height, 'o', markersize=8, color=color,
               markeredgecolor='white', markeredgewidth=1.5)

        # Height와 Prominence 비율에 따라 레이블 색상 결정
        ratio = prom / height if height > 0 else 0

        if ratio > 0.8:  # Prominence ≈ Height (고립된 피크)
            box_color = 'lightgreen'
            marker = '✓'
        elif ratio > 0.3:  # 중간
            box_color = 'yellow'
            marker = '~'
        else:  # Prominence << Height (숄더 가능성)
            box_color = 'lightcoral'
            marker = '?'

        ax.text(time[peak_idx], height + 1000,
               f'{marker}\n{time[peak_idx]:.2f}',
               ha='center', fontsize=8, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor=box_color, alpha=0.8))

    ax.set_xlabel('Retention Time (min)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.set_title('피크별 Height/Prominence 비율 평가', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 범례 추가
    legend_text = '✓ = 고립 피크 (P/H > 0.8)  |  ~ = 중간 (P/H > 0.3)  |  ? = 숄더 가능성 (P/H < 0.3)'
    ax.text(0.5, 0.98, legend_text, transform=ax.transAxes,
           ha='center', va='top', fontsize=10,
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

    # 상세 비교 표
    ax = axes[1]
    ax.axis('off')

    # 데이터 준비
    table_data = []
    for i, peak_idx in enumerate(peaks):
        rt = time[peak_idx]
        height = smoothed[peak_idx]
        prom = properties['prominences'][i]
        ratio = prom / height * 100
        diff = height - prom

        # 타입 판정
        if ratio > 80:
            peak_type = '고립 피크'
        elif ratio > 30:
            peak_type = '일반 피크'
        else:
            peak_type = '숄더?'

        table_data.append([
            f'{rt:.2f}',
            f'{height:.0f}',
            f'{prom:.0f}',
            f'{diff:.0f}',
            f'{ratio:.1f}%',
            peak_type
        ])

    # 표 생성
    table = ax.table(
        cellText=table_data,
        colLabels=['RT (min)', 'Height', 'Prominence', 'Diff\n(H-P)', 'Ratio\n(P/H)', 'Type'],
        cellLoc='center',
        loc='center',
        bbox=[0.05, 0.1, 0.9, 0.8]
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    # 헤더 스타일
    for i in range(6):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')

    # 행 색상 (타입별)
    for i in range(1, len(table_data) + 1):
        peak_type = table_data[i-1][5]
        if peak_type == '고립 피크':
            row_color = '#d4edda'  # 연한 녹색
        elif peak_type == '일반 피크':
            row_color = '#fff3cd'  # 연한 노란색
        else:
            row_color = '#f8d7da'  # 연한 빨간색

        for j in range(6):
            table[(i, j)].set_facecolor(row_color)

    ax.text(0.5, 0.95, 'Height vs Prominence 상세 비교', transform=ax.transAxes,
           ha='center', fontsize=12, fontweight='bold')

    explanation = """
    해석:
    • Height - Prominence = Contour Height (주변 배경 높이)
    • Ratio가 높을수록 (>80%) → 고립된 피크
    • Ratio가 낮을수록 (<30%) → 숄더나 큰 피크의 영향권
    """

    ax.text(0.5, 0.02, explanation, transform=ax.transAxes,
           ha='center', fontsize=10,
           bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    return fig


def main():
    print("=" * 80)
    print("Height vs Prominence 차이 설명")
    print("=" * 80)

    output_dir = Path("analysis_results")
    output_dir.mkdir(exist_ok=True)

    # 1. 개념 설명
    print("\n[1] Height vs Prominence 개념 설명...")
    fig1 = create_comparison_example()
    filename1 = output_dir / "height_vs_prominence_concept.png"
    fig1.savefig(filename1, dpi=300, bbox_inches='tight')
    print(f"    저장: {filename1}")
    plt.close()

    # 2. 실제 데이터 분석
    print("\n[2] 실제 데이터에서 Height vs Prominence 비교...")
    fig2 = real_data_example()
    filename2 = output_dir / "height_vs_prominence_real.png"
    fig2.savefig(filename2, dpi=300, bbox_inches='tight')
    print(f"    저장: {filename2}")
    plt.close()

    print("\n" + "=" * 80)
    print("핵심 정리")
    print("=" * 80)

    print("\nHeight (피크 높이):")
    print("  • 피크의 절대적 높이")
    print("  • 항상 일정 (주변과 무관)")

    print("\nProminence (두드러짐):")
    print("  • 피크가 주변보다 얼마나 '돋보이는지'")
    print("  • 주변 환경에 따라 달라짐")

    print("\n같은 높이의 피크라도:")
    print("  • 고립되어 있으면 → Prominence ≈ Height")
    print("  • 큰 피크 옆에 있으면 → Prominence << Height")
    print("  • 숄더 형태면 → Prominence 매우 작음")

    print("\n완료! analysis_results/ 폴더에서 결과를 확인하세요.")


if __name__ == "__main__":
    main()
