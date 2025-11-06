"""
제거된 베이스라인에서 놓친 피크 찾기
점진적으로 낮은 임계값을 사용하여 베이스라인에서 피크 패턴 검출
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import signal
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


def detect_peaks_with_threshold(time, intensity, prominence_factor, height_factor, noise_level, signal_range):
    """특정 임계값으로 피크 검출"""
    min_prominence = signal_range * prominence_factor
    min_height = noise_level * height_factor

    peaks, properties = signal.find_peaks(
        intensity,
        prominence=min_prominence,
        height=min_height,
        width=2,
        distance=10
    )

    peak_info = []
    for i, peak_idx in enumerate(peaks):
        peak_info.append({
            'index': peak_idx,
            'rt': time[peak_idx],
            'height': intensity[peak_idx],
            'prominence': properties['prominences'][i] if 'prominences' in properties else 0
        })

    return peaks, peak_info


def find_rt_overlap(rt, main_peaks_rt, tolerance=0.1):
    """특정 RT가 메인 피크와 겹치는지 확인 (±tolerance min)"""
    for main_rt in main_peaks_rt:
        if abs(rt - main_rt) <= tolerance:
            return True, main_rt
    return False, None


def analyze_removed_baseline(csv_file, output_dir):
    """제거된 베이스라인을 분석하여 놓친 피크 찾기"""

    # CSV 파일 읽기
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # 음수 값 처리
    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    sample_name = Path(csv_file).stem

    print(f"\n분석 중: {sample_name}")
    print(f"  데이터 포인트: {len(time)}")

    # 하이브리드 베이스라인 보정
    corrector = HybridBaselineCorrector(time, intensity)
    best_baseline, best_params = corrector.optimize_baseline()
    corrected = intensity - best_baseline
    corrected = np.maximum(corrected, 0)

    # 제거된 베이스라인
    removed_baseline = intensity - corrected

    # 노이즈 및 신호 범위 추정
    noise_level = np.percentile(corrected, 25)
    signal_range = np.ptp(corrected)
    baseline_range = np.ptp(removed_baseline)

    print(f"  신호 범위: {signal_range:.1f}")
    print(f"  베이스라인 범위: {baseline_range:.1f}")
    print(f"  노이즈 수준: {noise_level:.1f}")

    # 1. 메인 피크 검출 (보정된 신호)
    main_peaks, main_peak_info = detect_peaks_with_threshold(
        time, corrected,
        prominence_factor=0.005,
        height_factor=3,
        noise_level=noise_level,
        signal_range=signal_range
    )

    print(f"  메인 피크: {len(main_peaks)}개")

    # 2. 제거된 베이스라인에서 점진적 임계값으로 피크 검출
    threshold_levels = [
        ('높음', 0.01, 2.0),
        ('중간', 0.005, 1.0),
        ('낮음', 0.002, 0.5),
        ('매우낮음', 0.001, 0.3)
    ]

    baseline_peaks_by_level = {}

    for level_name, prom_factor, height_factor in threshold_levels:
        peaks, peak_info = detect_peaks_with_threshold(
            time, removed_baseline,
            prominence_factor=prom_factor,
            height_factor=height_factor,
            noise_level=noise_level,
            signal_range=baseline_range
        )
        baseline_peaks_by_level[level_name] = {
            'peaks': peaks,
            'info': peak_info
        }
        print(f"  베이스라인 피크 ({level_name}): {len(peaks)}개")

    # 3. 메인 피크와 겹치지 않는 베이스라인 피크 찾기
    main_peaks_rt = [p['rt'] for p in main_peak_info]

    potentially_missed = {}
    for level_name, data in baseline_peaks_by_level.items():
        missed = []
        overlapped = []

        for peak in data['info']:
            is_overlap, nearest_rt = find_rt_overlap(peak['rt'], main_peaks_rt, tolerance=0.1)
            if is_overlap:
                overlapped.append({**peak, 'nearest_main_rt': nearest_rt})
            else:
                missed.append(peak)

        potentially_missed[level_name] = {
            'missed': missed,
            'overlapped': overlapped
        }

        print(f"  잠재적 누락 피크 ({level_name}): {len(missed)}개")

    # 4. 시각화
    fig = plt.figure(figsize=(16, 12))

    # Panel 1: 원본 신호 + 베이스라인 + 보정 후
    ax1 = plt.subplot(3, 2, 1)
    ax1.plot(time, intensity, 'b-', alpha=0.5, linewidth=1, label='원본 신호')
    ax1.plot(time, best_baseline, 'r-', linewidth=2, label='베이스라인')
    ax1.plot(time, corrected, 'g-', alpha=0.7, linewidth=1, label='보정 후')
    ax1.set_xlabel('시간 (min)')
    ax1.set_ylabel('강도')
    ax1.set_title('1. 베이스라인 보정 개요')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Panel 2: 보정된 신호 + 메인 피크
    ax2 = plt.subplot(3, 2, 2)
    ax2.plot(time, corrected, 'g-', linewidth=1, label='보정된 신호')
    for peak in main_peak_info:
        ax2.plot(peak['rt'], peak['height'], 'ro', markersize=8)
    ax2.set_xlabel('시간 (min)')
    ax2.set_ylabel('강도')
    ax2.set_title(f'2. 메인 피크 검출 ({len(main_peaks)}개)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Panel 3: 제거된 베이스라인 + 4단계 임계값 피크
    ax3 = plt.subplot(3, 2, 3)
    ax3.plot(time, removed_baseline, 'k-', linewidth=1, alpha=0.5, label='제거된 베이스라인')

    colors = {'높음': 'red', '중간': 'orange', '낮음': 'yellow', '매우낮음': 'cyan'}
    for level_name, data in baseline_peaks_by_level.items():
        for peak in data['info']:
            ax3.plot(peak['rt'], peak['height'], 'o',
                    color=colors[level_name], markersize=6, alpha=0.7)

    # 범례 추가
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], marker='o', color='w',
                             markerfacecolor=colors[level], markersize=8,
                             label=f'{level} ({len(baseline_peaks_by_level[level]["peaks"])}개)')
                      for level in threshold_levels[0][0:1]]
    for level_name, _, _ in threshold_levels:
        legend_elements.append(
            Line2D([0], [0], marker='o', color='w',
                  markerfacecolor=colors[level_name], markersize=8,
                  label=f'{level_name} ({len(baseline_peaks_by_level[level_name]["peaks"])}개)')
        )

    ax3.set_xlabel('시간 (min)')
    ax3.set_ylabel('강도')
    ax3.set_title('3. 제거된 베이스라인의 피크 (4단계 임계값)')
    ax3.legend(handles=legend_elements, loc='upper right', fontsize=8)
    ax3.grid(True, alpha=0.3)

    # Panel 4: 겹치는 피크 vs 누락된 피크 (중간 임계값 기준)
    ax4 = plt.subplot(3, 2, 4)
    ax4.plot(time, removed_baseline, 'gray', linewidth=1, alpha=0.3, label='제거된 베이스라인')

    level_to_show = '중간'
    for peak in potentially_missed[level_to_show]['overlapped']:
        ax4.plot(peak['rt'], peak['height'], 'go', markersize=8,
                label='메인 피크와 겹침' if peak == potentially_missed[level_to_show]['overlapped'][0] else '')

    for peak in potentially_missed[level_to_show]['missed']:
        ax4.plot(peak['rt'], peak['height'], 'r^', markersize=10,
                label='잠재적 누락' if peak == potentially_missed[level_to_show]['missed'][0] else '')

    ax4.set_xlabel('시간 (min)')
    ax4.set_ylabel('강도')
    ax4.set_title(f'4. RT 비교 분석 ({level_to_show} 임계값)')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # Panel 5: 원본 신호에서 누락 피크 위치 표시
    ax5 = plt.subplot(3, 2, 5)
    ax5.plot(time, intensity, 'b-', linewidth=1, alpha=0.5, label='원본 신호')

    # 메인 피크 표시
    for peak in main_peak_info:
        idx = np.argmin(np.abs(time - peak['rt']))
        ax5.plot(peak['rt'], intensity[idx], 'go', markersize=8,
                label='검출된 피크' if peak == main_peak_info[0] else '')

    # 누락 피크 표시
    for peak in potentially_missed[level_to_show]['missed']:
        idx = np.argmin(np.abs(time - peak['rt']))
        ax5.plot(peak['rt'], intensity[idx], 'r^', markersize=10,
                label='잠재적 누락 위치' if peak == potentially_missed[level_to_show]['missed'][0] else '')

    ax5.set_xlabel('시간 (min)')
    ax5.set_ylabel('강도')
    ax5.set_title('5. 원본 신호에서 누락 피크 위치')
    ax5.legend()
    ax5.grid(True, alpha=0.3)

    # Panel 6: 통계 요약
    ax6 = plt.subplot(3, 2, 6)
    ax6.axis('off')

    stats_text = f"""
    【분석 요약】

    샘플: {sample_name[:40]}

    ▶ 메인 피크: {len(main_peaks)}개

    ▶ 베이스라인 피크 검출:
    """

    for level_name, _, _ in threshold_levels:
        n_total = len(baseline_peaks_by_level[level_name]['peaks'])
        n_missed = len(potentially_missed[level_name]['missed'])
        n_overlap = len(potentially_missed[level_name]['overlapped'])
        stats_text += f"   • {level_name}: {n_total}개 (누락 {n_missed}, 겹침 {n_overlap})\n"

    stats_text += f"""
    ▶ 추천 검토 대상 (중간 임계값):
       {len(potentially_missed['중간']['missed'])}개 위치

    RT 허용 범위: ±0.1 min
    """

    ax6.text(0.1, 0.9, stats_text, transform=ax6.transAxes,
            fontsize=11, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    # 저장
    output_file = output_dir / f'{sample_name}_baseline_analysis.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  저장: {output_file.name}")
    plt.close()

    return {
        'sample': sample_name,
        'main_peaks': len(main_peaks),
        'potentially_missed': {level: len(data['missed'])
                              for level, data in potentially_missed.items()}
    }


if __name__ == '__main__':
    # 출력 디렉토리
    output_dir = Path('result/baseline_analysis')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 분석할 샘플 선택
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    # 처음 5개 샘플 분석
    selected_files = list(csv_files[:5])

    print("=" * 80)
    print("제거된 베이스라인 분석 - 놓친 피크 찾기")
    print("=" * 80)
    print(f"총 {len(selected_files)}개 샘플 분석\n")

    results = []
    for csv_file in selected_files:
        result = analyze_removed_baseline(csv_file, output_dir)
        results.append(result)

    # 요약
    print("\n" + "=" * 80)
    print("분석 완료 요약")
    print("=" * 80)
    for r in results:
        print(f"\n{r['sample'][:50]}")
        print(f"  메인 피크: {r['main_peaks']}개")
        print(f"  잠재적 누락:")
        for level, count in r['potentially_missed'].items():
            print(f"    {level}: {count}개")

    print(f"\n모든 이미지 저장: {output_dir}/")
