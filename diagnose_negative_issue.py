"""
음수 피크 vs 베이스라인 과보정 구분 진단
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys
from scipy import signal

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


def diagnose_negative_regions(csv_file):
    """
    음수 영역 상세 진단:
    1. 실제 음수 피크 (신호가 밑으로 볼록)
    2. 베이스라인 과보정 (베이스라인이 신호보다 아래로 내려감)
    """
    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    sample_name = csv_file.stem

    print(f"\n{'='*80}")
    print(f"음수 영역 진단: {sample_name}")
    print(f"{'='*80}")

    # Robust Fit 베이스라인
    corrector = HybridBaselineCorrector(time, intensity)
    corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
    baseline = corrector.generate_hybrid_baseline(method='robust_fit')
    corrected = intensity - baseline

    # 음수 영역 찾기
    negative_mask = corrected < 0
    negative_count = np.sum(negative_mask)

    print(f"\n음수 값: {negative_count}개 ({negative_count/len(corrected)*100:.2f}%)")

    # 연속된 음수 영역 찾기
    def find_continuous_regions(mask):
        """연속된 True 영역 찾기"""
        regions = []
        in_region = False
        start = 0

        for i, val in enumerate(mask):
            if val and not in_region:
                start = i
                in_region = True
            elif not val and in_region:
                regions.append((start, i-1))
                in_region = False

        if in_region:
            regions.append((start, len(mask)-1))

        return regions

    negative_regions = find_continuous_regions(negative_mask)
    print(f"\n연속된 음수 영역: {len(negative_regions)}개")

    # 각 영역 분석
    print(f"\n{'='*80}")
    print("영역별 상세 분석:")
    print(f"{'='*80}")

    region_analysis = []

    for idx, (start, end) in enumerate(negative_regions, 1):
        region_time = time[start:end+1]
        region_intensity = intensity[start:end+1]
        region_baseline = baseline[start:end+1]
        region_corrected = corrected[start:end+1]

        rt_start = time[start]
        rt_end = time[end]
        duration = rt_end - rt_start

        # 영역 크기 필터 (너무 작은 영역 제외)
        if duration < 0.05:  # 0.05분 미만은 노이즈로 간주
            continue

        print(f"\n[영역 {idx}] RT {rt_start:.2f} ~ {rt_end:.2f} (폭: {duration:.2f}분, 점수: {end-start+1})")

        # 1. 신호 형태 분석
        signal_min = np.min(region_intensity)
        signal_max = np.max(region_intensity)
        signal_range = signal_max - signal_min

        # 2. 베이스라인 위치 분석
        baseline_min = np.min(region_baseline)
        baseline_max = np.max(region_baseline)

        # 신호 대비 베이스라인 위치
        baseline_below_signal = baseline_min < signal_min

        print(f"  신호: {signal_min:.1f} ~ {signal_max:.1f} (범위: {signal_range:.1f})")
        print(f"  베이스라인: {baseline_min:.1f} ~ {baseline_max:.1f}")

        # 3. 원본 신호의 곡률 분석 (2차 미분)
        if len(region_intensity) > 5:
            # 부드럽게 만들기
            window_len = min(11, len(region_intensity))
            if window_len % 2 == 0:
                window_len -= 1  # 홀수로 만들기
            if window_len >= 3:
                smoothed = signal.savgol_filter(region_intensity, window_len, min(2, window_len-1))
                # 2차 미분 (곡률)
                second_deriv = np.gradient(np.gradient(smoothed))
                avg_curvature = np.mean(second_deriv)
            else:
                # 너무 짧으면 직접 계산
                second_deriv = np.gradient(np.gradient(region_intensity))
                avg_curvature = np.mean(second_deriv)

            # 양수: 위로 볼록 (일반 피크), 음수: 아래로 볼록 (음수 피크)
            is_concave_down = avg_curvature < 0  # 밑으로 볼록

            print(f"  평균 곡률: {avg_curvature:.2f} ({'밑으로 볼록' if is_concave_down else '위로 볼록'})")
        else:
            avg_curvature = 0
            is_concave_down = False

        # 4. 진단
        # 실제 음수 피크: 신호가 밑으로 볼록하고, 베이스라인이 신호보다 위에 있어야 함
        # 베이스라인 과보정: 베이스라인이 신호보다 아래에 있음

        if baseline_below_signal:
            diagnosis = "[과보정] 베이스라인 과보정"
            reason = "베이스라인이 신호보다 아래로 내려감"
        elif is_concave_down and signal_range > 100:  # 충분한 크기의 밑으로 볼록
            diagnosis = "[음수피크] 실제 음수 피크 가능성"
            reason = "신호가 밑으로 볼록"
        else:
            diagnosis = "[불명] 애매한 영역"
            reason = "형태가 불분명"

        print(f"  진단: {diagnosis}")
        print(f"  이유: {reason}")

        region_analysis.append({
            'region': idx,
            'rt_start': rt_start,
            'rt_end': rt_end,
            'duration': duration,
            'signal_min': signal_min,
            'signal_max': signal_max,
            'baseline_min': baseline_min,
            'baseline_max': baseline_max,
            'avg_curvature': avg_curvature,
            'baseline_below_signal': baseline_below_signal,
            'is_concave_down': is_concave_down,
            'diagnosis': diagnosis,
            'reason': reason
        })

    # 시각화
    fig, axes = plt.subplots(3, 1, figsize=(16, 12))

    # Panel 1: 전체 신호 + 베이스라인
    ax1 = axes[0]
    ax1.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.7, label='원본 신호')
    ax1.plot(time, baseline, 'r--', linewidth=2, label='베이스라인 (Robust Fit)')
    ax1.axhline(y=0, color='gray', linestyle=':', alpha=0.5)

    # 베이스라인이 신호 아래로 간 영역 강조
    baseline_below = baseline < intensity
    ax1.fill_between(time, baseline, intensity,
                     where=baseline_below,
                     color='orange', alpha=0.3,
                     label=f'베이스라인 < 신호 ({np.sum(baseline_below)}점)')

    ax1.set_xlabel('시간 (min)', fontsize=11)
    ax1.set_ylabel('강도', fontsize=11)
    ax1.set_title(f'{sample_name}: 원본 신호 + 베이스라인', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Panel 2: 보정 후 + 음수 영역 구분
    ax2 = axes[1]
    ax2.plot(time, corrected, 'g-', linewidth=1, label='보정된 신호')
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 음수 영역별로 색상 구분
    colors = ['red', 'orange', 'purple', 'brown', 'pink']
    for i, region in enumerate(region_analysis):
        start_idx = np.argmin(np.abs(time - region['rt_start']))
        end_idx = np.argmin(np.abs(time - region['rt_end']))

        color = colors[i % len(colors)]
        ax2.fill_between(time[start_idx:end_idx+1], 0, corrected[start_idx:end_idx+1],
                        color=color, alpha=0.4,
                        label=f"영역{region['region']}: {region['diagnosis'][:3]}")

        # RT 라벨
        mid_rt = (region['rt_start'] + region['rt_end']) / 2
        ax2.annotate(f"#{region['region']}\n{region['rt_start']:.1f}-{region['rt_end']:.1f}",
                    xy=(mid_rt, np.min(corrected[start_idx:end_idx+1])),
                    xytext=(0, -20), textcoords='offset points',
                    ha='center', fontsize=8,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', lw=1))

    ax2.set_xlabel('시간 (min)', fontsize=11)
    ax2.set_ylabel('강도', fontsize=11)
    ax2.set_title('보정 후 신호: 음수 영역 진단', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=8, loc='best')
    ax2.grid(True, alpha=0.3)

    # Panel 3: 주요 음수 영역 확대 (가장 큰 3개)
    ax3 = axes[2]

    # 영역 크기 순 정렬
    sorted_regions = sorted(region_analysis, key=lambda x: x['duration'], reverse=True)

    for i, region in enumerate(sorted_regions[:3]):  # 가장 큰 3개만
        start_idx = np.argmin(np.abs(time - region['rt_start']))
        end_idx = np.argmin(np.abs(time - region['rt_end']))

        # 확대 범위 (앞뒤 여유)
        margin = int((end_idx - start_idx) * 0.5)
        plot_start = max(0, start_idx - margin)
        plot_end = min(len(time) - 1, end_idx + margin)

        plot_time = time[plot_start:plot_end+1]
        plot_intensity = intensity[plot_start:plot_end+1]
        plot_baseline = baseline[plot_start:plot_end+1]

        offset = i * 3000  # 각 영역을 수직으로 이동

        color = colors[i % len(colors)]
        ax3.plot(plot_time, plot_intensity + offset, 'b-', linewidth=1.5, alpha=0.7)
        ax3.plot(plot_time, plot_baseline + offset, 'r--', linewidth=2, alpha=0.8)

        # 영역 표시
        region_time = time[start_idx:end_idx+1]
        region_intensity = intensity[start_idx:end_idx+1]
        region_baseline = baseline[start_idx:end_idx+1]

        ax3.fill_between(region_time, region_baseline + offset, region_intensity + offset,
                        color=color, alpha=0.4)

        # 라벨
        ax3.text(region['rt_start'], np.max(plot_intensity) + offset + 200,
                f"영역 {region['region']}: {region['diagnosis']}\n{region['reason']}",
                fontsize=9, bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.8))

    ax3.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
    ax3.set_xlabel('시간 (min)', fontsize=11)
    ax3.set_ylabel('강도 (offset 적용)', fontsize=11)
    ax3.set_title('주요 음수 영역 확대 (상위 3개)', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = f'result/negative_diagnosis_{sample_name}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n시각화 저장: {output_file}")
    plt.show()

    return region_analysis


def main():
    """첫 번째 샘플로 진단"""
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    if len(csv_files) == 0:
        print("데이터 파일이 없습니다.")
        return

    # 첫 번째 파일
    csv_file = csv_files[0]

    Path('result').mkdir(exist_ok=True)

    analysis = diagnose_negative_regions(csv_file)

    # 통계
    print(f"\n{'='*80}")
    print("통계 요약:")
    print(f"{'='*80}")

    total = len(analysis)
    over_corrected = sum(1 for a in analysis if '과보정' in a['diagnosis'])
    real_negative = sum(1 for a in analysis if '실제' in a['diagnosis'])
    unclear = sum(1 for a in analysis if '애매' in a['diagnosis'])

    print(f"\n총 음수 영역: {total}개")
    print(f"  - 베이스라인 과보정: {over_corrected}개 ({over_corrected/total*100:.1f}%)")
    print(f"  - 실제 음수 피크 가능성: {real_negative}개 ({real_negative/total*100:.1f}%)")
    print(f"  - 애매한 영역: {unclear}개 ({unclear/total*100:.1f}%)")


if __name__ == '__main__':
    main()
