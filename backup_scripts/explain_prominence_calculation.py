"""
Prominence 계산 방법 상세 설명
- scipy.signal.find_peaks가 prominence를 어떻게 계산하는지 시각화
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from pathlib import Path


def create_simple_example():
    """간단한 예제로 prominence 계산 설명"""

    # 3개의 서로 다른 높이의 피크 생성
    time = np.linspace(0, 10, 1000)

    # 큰 피크
    peak1 = 100 * np.exp(-((time - 2) ** 2) / 0.2)
    # 중간 피크
    peak2 = 60 * np.exp(-((time - 5) ** 2) / 0.15)
    # 작은 피크
    peak3 = 80 * np.exp(-((time - 7.5) ** 2) / 0.18)

    # 베이스라인과 노이즈
    baseline = 10
    signal_data = baseline + peak1 + peak2 + peak3

    # 피크 검출
    peaks, properties = signal.find_peaks(signal_data, prominence=1)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('Prominence 계산 방법 - 단계별 설명', fontsize=16, fontweight='bold')

    # 1. 전체 신호와 검출된 피크
    ax = axes[0, 0]
    ax.plot(time, signal_data, 'b-', linewidth=2, label='Signal')
    ax.plot(time[peaks], signal_data[peaks], 'ro', markersize=10,
            markeredgecolor='white', markeredgewidth=2, label='Detected Peaks')
    ax.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.set_title('Step 1: 피크 검출', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 각 피크에 번호 표시
    for i, peak_idx in enumerate(peaks, 1):
        ax.text(time[peak_idx], signal_data[peak_idx] + 5,
               f'Peak {i}', ha='center', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

    # 2. Contour lines 설명
    ax = axes[0, 1]
    ax.plot(time, signal_data, 'b-', linewidth=2, label='Signal')
    ax.plot(time[peaks], signal_data[peaks], 'ro', markersize=10,
            markeredgecolor='white', markeredgewidth=2)

    # 각 피크의 contour 높이 표시
    for i, peak_idx in enumerate(peaks):
        # scipy가 계산한 prominence와 contour 높이
        prominence = properties['prominences'][i]
        contour_height = signal_data[peak_idx] - prominence
        left_base = properties['left_bases'][i]
        right_base = properties['right_bases'][i]

        # Contour line 그리기
        ax.hlines(contour_height, time[left_base], time[right_base],
                 colors='red', linestyles='--', linewidth=2, alpha=0.7)

        # Prominence 화살표
        ax.annotate('', xy=(time[peak_idx], contour_height),
                   xytext=(time[peak_idx], signal_data[peak_idx]),
                   arrowprops=dict(arrowstyle='<->', color='green', lw=3))

        # 텍스트
        mid_height = (signal_data[peak_idx] + contour_height) / 2
        ax.text(time[peak_idx] + 0.2, mid_height,
               f'P={prominence:.1f}',
               fontsize=10, fontweight='bold', color='green',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

    ax.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.set_title('Step 2: Contour Height & Prominence', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 3. 특정 피크 상세 설명 (중간 피크 - Peak 2)
    ax = axes[1, 0]
    peak_idx = peaks[1]  # 중간 피크 선택
    prominence = properties['prominences'][1]
    contour_height = signal_data[peak_idx] - prominence
    left_base = properties['left_bases'][1]
    right_base = properties['right_bases'][1]

    # 해당 영역만 확대
    margin = 100
    start_idx = max(0, left_base - margin)
    end_idx = min(len(time), right_base + margin)

    ax.plot(time[start_idx:end_idx], signal_data[start_idx:end_idx],
           'b-', linewidth=3, label='Signal')
    ax.plot(time[peak_idx], signal_data[peak_idx], 'ro', markersize=15,
           markeredgecolor='white', markeredgewidth=2, label='Peak')

    # Left base와 right base 표시
    ax.plot(time[left_base], signal_data[left_base], 's',
           color='orange', markersize=12, label='Left Base')
    ax.plot(time[right_base], signal_data[right_base], 's',
           color='purple', markersize=12, label='Right Base')

    # Contour line
    ax.hlines(contour_height, time[start_idx], time[end_idx],
             colors='red', linestyles='--', linewidth=2.5, label='Contour Line', alpha=0.7)

    # Prominence 표시
    ax.vlines(time[peak_idx], contour_height, signal_data[peak_idx],
             colors='green', linewidth=4, label=f'Prominence = {prominence:.1f}')

    ax.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.set_title(f'Step 3: Peak 2 상세 분석\nProminence = {prominence:.1f}',
                fontsize=12, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 4. 계산 공식 설명
    ax = axes[1, 1]
    ax.axis('off')

    explanation = """
    Prominence 계산 알고리즘:

    1. 각 피크에서 출발하여 양쪽으로 이동

    2. 다음 중 하나를 만날 때까지 진행:
       • 더 높은 피크
       • 신호의 끝

    3. 그 과정에서 만나는 가장 낮은 지점을 찾음
       → 이것이 "Contour Height"

    4. Prominence 계산:
       Prominence = Peak Height - Contour Height


    Prominence의 의미:

    • 피크가 주변보다 얼마나 "돋보이는지"
    • 값이 클수록 → 주변과 명확히 구분되는 피크
    • 값이 작을수록 → 숄더나 노이즈일 가능성


    실제 예시 (위 Peak 2):

    • Peak Height = {:.1f}
    • Contour Height = {:.1f}
    • Prominence = {:.1f} - {:.1f} = {:.1f}


    find_peaks()에서 사용:

    peaks, props = find_peaks(signal, prominence=30)

    → Prominence >= 30인 피크만 검출
    """.format(
        signal_data[peak_idx],
        contour_height,
        signal_data[peak_idx],
        contour_height,
        prominence
    )

    ax.text(0.1, 0.9, explanation, transform=ax.transAxes,
           fontsize=11, verticalalignment='top', family='monospace',
           bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    return fig


def explain_with_real_data():
    """실제 EXPORT 데이터로 prominence 계산 설명"""

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

    # 피크 검출
    peaks, properties = signal.find_peaks(smoothed, prominence=1000, height=600, width=2)

    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle('실제 크로마토그램 데이터에서의 Prominence 계산', fontsize=16, fontweight='bold')

    # 1. 전체 크로마토그램
    ax = axes[0, 0]
    ax.plot(time, intensity, 'b-', linewidth=0.5, alpha=0.4, label='Raw')
    ax.plot(time, smoothed, 'darkblue', linewidth=1.5, label='Smoothed')
    ax.plot(time[peaks], smoothed[peaks], 'ro', markersize=10,
           markeredgecolor='white', markeredgewidth=2, label='Peaks')

    for i, peak_idx in enumerate(peaks):
        ax.text(time[peak_idx], smoothed[peak_idx] + 1000,
               f'{time[peak_idx]:.2f}',
               ha='center', fontsize=9, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

    ax.set_xlabel('Retention Time (min)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.set_title('전체 크로마토그램 - 검출된 피크', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. 각 피크의 prominence 값 표시
    ax = axes[0, 1]
    ax.plot(time, smoothed, 'darkblue', linewidth=1.5, label='Smoothed Signal')

    colors = plt.cm.Set3(np.linspace(0, 1, len(peaks)))

    for i, (peak_idx, color) in enumerate(zip(peaks, colors)):
        prominence = properties['prominences'][i]
        contour_height = smoothed[peak_idx] - prominence
        left_base = int(properties['left_bases'][i])
        right_base = int(properties['right_bases'][i])

        # 피크 마커
        ax.plot(time[peak_idx], smoothed[peak_idx], 'o',
               color=color, markersize=10, markeredgecolor='white',
               markeredgewidth=2, zorder=5)

        # Contour line
        ax.hlines(contour_height, time[left_base], time[right_base],
                 colors=color, linestyles='--', linewidth=2, alpha=0.7)

        # Prominence line
        ax.vlines(time[peak_idx], contour_height, smoothed[peak_idx],
                 colors=color, linewidth=3, alpha=0.8)

        # 텍스트
        ax.text(time[peak_idx], smoothed[peak_idx] + 800,
               f'{time[peak_idx]:.2f}\nP={prominence:.0f}',
               ha='center', fontsize=8, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='white',
                        edgecolor=color, linewidth=2))

    ax.set_xlabel('Retention Time (min)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.set_title('각 피크의 Prominence 값', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)

    # 3. 특정 피크 확대 (가장 큰 피크)
    max_prom_idx = np.argmax(properties['prominences'])
    peak_idx = peaks[max_prom_idx]
    prominence = properties['prominences'][max_prom_idx]
    contour_height = smoothed[peak_idx] - prominence
    left_base = int(properties['left_bases'][max_prom_idx])
    right_base = int(properties['right_bases'][max_prom_idx])

    ax = axes[1, 0]

    # 확대 영역
    margin_points = 200
    start_idx = max(0, left_base - margin_points)
    end_idx = min(len(time), right_base + margin_points)

    ax.plot(time[start_idx:end_idx], intensity[start_idx:end_idx],
           'b-', linewidth=1, alpha=0.5, label='Raw')
    ax.plot(time[start_idx:end_idx], smoothed[start_idx:end_idx],
           'darkblue', linewidth=2.5, label='Smoothed')

    # 피크
    ax.plot(time[peak_idx], smoothed[peak_idx], 'ro', markersize=15,
           markeredgecolor='white', markeredgewidth=2, label='Peak', zorder=5)

    # Base points
    ax.plot(time[left_base], smoothed[left_base], 's',
           color='orange', markersize=12, label='Left Base', zorder=5)
    ax.plot(time[right_base], smoothed[right_base], 's',
           color='purple', markersize=12, label='Right Base', zorder=5)

    # Contour line
    ax.hlines(contour_height, time[start_idx], time[end_idx],
             colors='red', linestyles='--', linewidth=2.5,
             label=f'Contour (height={contour_height:.0f})', alpha=0.7)

    # Prominence
    ax.vlines(time[peak_idx], contour_height, smoothed[peak_idx],
             colors='green', linewidth=5, label=f'Prominence={prominence:.0f}')

    ax.set_xlabel('Retention Time (min)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11, fontweight='bold')
    ax.set_title(f'피크 {time[peak_idx]:.2f}min 상세 분석\nProminence = {prominence:.0f}',
                fontsize=12, fontweight='bold')
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 4. Prominence 값 비교표
    ax = axes[1, 1]
    ax.axis('off')

    # 표 생성
    peak_info = []
    for i, peak_idx in enumerate(peaks):
        rt = time[peak_idx]
        height = smoothed[peak_idx]
        prom = properties['prominences'][i]
        width = properties['widths'][i] * (time[1] - time[0])  # 포인트를 시간으로 변환
        peak_info.append([f'{rt:.2f}', f'{height:.0f}', f'{prom:.0f}', f'{width:.3f}'])

    table = ax.table(cellText=peak_info,
                    colLabels=['RT (min)', 'Height', 'Prominence', 'Width (min)'],
                    cellLoc='center',
                    loc='center',
                    bbox=[0.1, 0.3, 0.8, 0.6])

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)

    # 헤더 스타일
    for i in range(4):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')

    # 행 색상 교대
    for i in range(1, len(peak_info) + 1):
        for j in range(4):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#f0f0f0')

    ax.text(0.5, 0.95, '검출된 피크의 Prominence 값 비교',
           ha='center', fontsize=12, fontweight='bold',
           transform=ax.transAxes)

    explanation = """
    Prominence 기준으로 피크 필터링:

    • prominence=1000 사용 → 5개 피크 검출
    • prominence=2000 사용 → 더 적은 피크 검출
    • prominence=500 사용 → 더 많은 피크 검출
    """

    ax.text(0.5, 0.15, explanation,
           ha='center', fontsize=10, transform=ax.transAxes,
           bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    return fig


def main():
    print("=" * 80)
    print("Prominence 계산 방법 설명")
    print("=" * 80)

    output_dir = Path("analysis_results")
    output_dir.mkdir(exist_ok=True)

    # 1. 간단한 예제
    print("\n[1] 간단한 예제로 prominence 계산 설명...")
    fig1 = create_simple_example()
    filename1 = output_dir / "prominence_calculation_simple.png"
    fig1.savefig(filename1, dpi=300, bbox_inches='tight')
    print(f"    저장: {filename1}")
    plt.close()

    # 2. 실제 데이터
    print("\n[2] 실제 크로마토그램 데이터로 prominence 계산 설명...")
    fig2 = explain_with_real_data()
    filename2 = output_dir / "prominence_calculation_real.png"
    fig2.savefig(filename2, dpi=300, bbox_inches='tight')
    print(f"    저장: {filename2}")
    plt.close()

    print("\n" + "=" * 80)
    print("Prominence 계산 요약")
    print("=" * 80)

    print("\n핵심 알고리즘:")
    print("  1. 피크에서 좌우로 이동하며 더 높은 피크를 찾음")
    print("  2. 그 사이의 가장 낮은 지점 = Contour Height")
    print("  3. Prominence = Peak Height - Contour Height")

    print("\nProminence의 의미:")
    print("  - 피크가 주변보다 얼마나 '돋보이는지'의 척도")
    print("  - 큰 값 = 명확한 피크")
    print("  - 작은 값 = 숄더나 노이즈 가능성")

    print("\n활용:")
    print("  - prominence 임계값으로 의미있는 피크만 선택")
    print("  - 노이즈와 진짜 피크를 구분하는 기준")

    print("\n완료! analysis_results/ 폴더에서 결과를 확인하세요.")


if __name__ == "__main__":
    main()
