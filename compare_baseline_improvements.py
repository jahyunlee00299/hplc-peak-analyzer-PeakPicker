"""
기존 베이스라인 방법과 개선된 방법 비교 시각화
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import signal
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector
from improved_baseline import ImprovedBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


def compare_baseline_methods(csv_file: Path, output_dir: Path):
    """
    기존 방법 vs 개선된 방법 상세 비교
    """
    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # 음수 처리
    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    sample_name = csv_file.stem

    print(f"\n{'='*80}")
    print(f"분석 중: {sample_name}")
    print(f"{'='*80}")
    print(f"데이터 포인트: {len(time):,}")
    print(f"시간 범위: {time[0]:.2f} - {time[-1]:.2f} min")
    print(f"강도 범위: {intensity.min():.1f} - {intensity.max():.1f}")

    # 1. 기존 방법 (HybridBaselineCorrector)
    print("\n[기존 방법] HybridBaselineCorrector")
    old_corrector = HybridBaselineCorrector(time, intensity)
    baseline_old, params_old = old_corrector.optimize_baseline_with_linear_peaks()
    corrected_old = np.maximum(intensity - baseline_old, 0)

    # 앵커 포인트
    old_corrector.find_baseline_anchor_points()
    old_anchors = old_corrector.baseline_points

    print(f"  앵커 포인트: {len(old_anchors)}개")
    print(f"  방법: {params_old.get('method', 'unknown')}")
    if 'selection_info' in params_old:
        info = params_old['selection_info']
        print(f"  선택: robust={info.get('robust_selected_count', 0)}, "
              f"weighted={info.get('weighted_selected_count', 0)}")

    # 2. 개선된 방법 (ImprovedBaselineCorrector)
    print("\n[개선된 방법] ImprovedBaselineCorrector")
    new_corrector = ImprovedBaselineCorrector(time, intensity)
    baseline_new, params_new = new_corrector.optimize_baseline(use_linear_peaks=True)
    corrected_new = np.maximum(intensity - baseline_new, 0)

    new_anchors = new_corrector.anchors

    print(f"  앵커 포인트: {len(new_anchors)}개")
    print(f"  방법: {params_new.get('method', 'unknown')}")
    print(f"  평가 점수: {params_new.get('score', 0):.2f}")

    # 3. 피크 검출 비교
    def detect_peaks(corrected_signal):
        noise_level = np.percentile(corrected_signal, 25) * 1.5
        peaks, props = signal.find_peaks(
            corrected_signal,
            prominence=np.ptp(corrected_signal) * 0.005,
            height=max(noise_level * 3, np.std(corrected_signal) * 2),
            width=0
        )
        return peaks, props

    peaks_old, props_old = detect_peaks(corrected_old)
    peaks_new, props_new = detect_peaks(corrected_new)

    print(f"\n[피크 검출 결과]")
    print(f"  기존 방법: {len(peaks_old)}개 피크")
    print(f"  개선 방법: {len(peaks_new)}개 피크")

    # 피크 너비 비교
    if 'widths' in props_old and len(props_old['widths']) > 0:
        avg_width_old = np.mean(props_old['widths'])
        print(f"  기존 평균 너비: {avg_width_old:.2f}")
    else:
        avg_width_old = 0

    if 'widths' in props_new and len(props_new['widths']) > 0:
        avg_width_new = np.mean(props_new['widths'])
        print(f"  개선 평균 너비: {avg_width_new:.2f}")
    else:
        avg_width_new = 0

    # 4. 시각화
    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.25)

    # Panel 1: 기존 방법 - 앵커 포인트
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.6)

    # 앵커 포인트 타입별 표시
    for anchor in old_anchors:
        if anchor.type == 'valley':
            color, marker, size = 'red', 'v', 80
        elif anchor.type == 'local_min':
            color, marker, size = 'green', 'o', 50
        else:
            color, marker, size = 'orange', 's', 60

        ax1.scatter(time[anchor.index], anchor.value,
                   c=color, marker=marker, s=size * anchor.confidence,
                   edgecolors='black', linewidths=0.5, zorder=5, alpha=0.8)

    ax1.set_xlabel('시간 (min)', fontweight='bold')
    ax1.set_ylabel('강도', fontweight='bold')
    ax1.set_title(f'기존 방법: 앵커 포인트 ({len(old_anchors)}개)', fontweight='bold', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend(['원본', 'Valley', 'Local Min', 'Boundary'], loc='upper right')

    # Panel 2: 개선된 방법 - 앵커 포인트
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.6)

    for anchor in new_anchors:
        if anchor.type == 'valley':
            color, marker, size = 'red', 'v', 80
        elif anchor.type == 'local_min':
            color, marker, size = 'green', 'o', 50
        else:
            color, marker, size = 'orange', 's', 60

        ax2.scatter(anchor.rt, anchor.value,
                   c=color, marker=marker, s=size * anchor.confidence,
                   edgecolors='black', linewidths=0.5, zorder=5, alpha=0.8)

    ax2.set_xlabel('시간 (min)', fontweight='bold')
    ax2.set_ylabel('강도', fontweight='bold')
    ax2.set_title(f'개선된 방법: 앵커 포인트 ({len(new_anchors)}개)', fontweight='bold', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.legend(['원본', 'Valley', 'Local Min', 'Boundary'], loc='upper right')

    # Panel 3: 기존 방법 - 베이스라인
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.7)
    ax3.plot(time, baseline_old, 'r--', linewidth=2, label='베이스라인')
    ax3.fill_between(time, 0, baseline_old, alpha=0.2, color='red')
    ax3.scatter(time[peaks_old], intensity[peaks_old],
               color='green', s=80, zorder=5, label=f'피크 ({len(peaks_old)}개)', marker='^')

    ax3.set_xlabel('시간 (min)', fontweight='bold')
    ax3.set_ylabel('강도', fontweight='bold')
    ax3.set_title(f'기존 방법: 베이스라인', fontweight='bold', fontsize=12)
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    # Panel 4: 개선된 방법 - 베이스라인
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.7)
    ax4.plot(time, baseline_new, 'purple', linestyle='--', linewidth=2, label='베이스라인')
    ax4.fill_between(time, 0, baseline_new, alpha=0.2, color='purple')
    ax4.scatter(time[peaks_new], intensity[peaks_new],
               color='green', s=80, zorder=5, label=f'피크 ({len(peaks_new)}개)', marker='^')

    ax4.set_xlabel('시간 (min)', fontweight='bold')
    ax4.set_ylabel('강도', fontweight='bold')
    ax4.set_title(f'개선된 방법: 베이스라인', fontweight='bold', fontsize=12)
    ax4.legend(loc='upper right')
    ax4.grid(True, alpha=0.3)

    # Panel 5: 보정 후 신호 비교
    ax5 = fig.add_subplot(gs[2, 0])
    ax5.plot(time, corrected_old, 'b-', linewidth=1.5, alpha=0.6, label='기존 방법')
    ax5.plot(time, corrected_new, 'r-', linewidth=1.5, alpha=0.6, label='개선된 방법')
    ax5.set_xlabel('시간 (min)', fontweight='bold')
    ax5.set_ylabel('강도 (보정 후)', fontweight='bold')
    ax5.set_title('보정 후 신호 비교', fontweight='bold', fontsize=12)
    ax5.legend(loc='upper right')
    ax5.grid(True, alpha=0.3)

    # Panel 6: 베이스라인 차이
    ax6 = fig.add_subplot(gs[2, 1])
    baseline_diff = baseline_new - baseline_old
    ax6.plot(time, baseline_diff, 'g-', linewidth=2)
    ax6.axhline(y=0, color='k', linestyle='--', alpha=0.5)
    ax6.fill_between(time, 0, baseline_diff, where=(baseline_diff > 0),
                     alpha=0.3, color='green', label='개선 방법이 더 높음')
    ax6.fill_between(time, 0, baseline_diff, where=(baseline_diff < 0),
                     alpha=0.3, color='red', label='기존 방법이 더 높음')

    ax6.set_xlabel('시간 (min)', fontweight='bold')
    ax6.set_ylabel('차이', fontweight='bold')
    ax6.set_title('베이스라인 차이 (개선 - 기존)', fontweight='bold', fontsize=12)
    ax6.legend(loc='upper right')
    ax6.grid(True, alpha=0.3)

    # Panel 7: 피크별 상세 비교 (처음 5개 피크)
    ax7 = fig.add_subplot(gs[3, :])

    # RT 범위로 피크 매칭
    matched_peaks = []
    for peak_new in peaks_new[:5]:
        rt_new = time[peak_new]
        # 가장 가까운 기존 피크 찾기
        if len(peaks_old) > 0:
            rt_diffs = np.abs(time[peaks_old] - rt_new)
            closest_idx = np.argmin(rt_diffs)
            if rt_diffs[closest_idx] < 0.1:  # 0.1분 이내
                matched_peaks.append((peak_new, peaks_old[closest_idx]))
            else:
                matched_peaks.append((peak_new, None))
        else:
            matched_peaks.append((peak_new, None))

    # 비교 테이블 생성
    table_data = []
    for i, (peak_new, peak_old) in enumerate(matched_peaks, 1):
        rt = time[peak_new]
        height_new = corrected_new[peak_new]

        if peak_old is not None:
            height_old = corrected_old[peak_old]
            height_diff = ((height_new - height_old) / height_old * 100) if height_old > 0 else 0
            status = "✓" if abs(height_diff) < 10 else "△"
        else:
            height_old = 0
            height_diff = 0
            status = "NEW"

        table_data.append([
            f"{rt:.2f}",
            f"{height_old:.0f}",
            f"{height_new:.0f}",
            f"{height_diff:+.1f}%",
            status
        ])

    table = ax7.table(
        cellText=table_data,
        colLabels=['RT (min)', '기존 높이', '개선 높이', '차이', '상태'],
        cellLoc='center',
        loc='center',
        colWidths=[0.15, 0.2, 0.2, 0.15, 0.1]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2.5)

    # 헤더 스타일
    for i in range(5):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')

    ax7.axis('off')
    ax7.set_title('피크별 상세 비교 (처음 5개)', fontweight='bold', fontsize=12, pad=20)

    # 전체 제목
    fig.suptitle(f'{sample_name}\n기존 vs 개선된 베이스라인 방법 비교',
                 fontsize=14, fontweight='bold', y=0.995)

    # 저장
    output_file = output_dir / f'{sample_name}_comparison.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n시각화 저장: {output_file.name}")

    # 통계 계산
    neg_ratio_old = np.sum(corrected_old < 0) / len(corrected_old) * 100
    neg_ratio_new = np.sum(corrected_new < 0) / len(corrected_new) * 100

    return {
        'sample': sample_name,
        'anchors_old': len(old_anchors),
        'anchors_new': len(new_anchors),
        'peaks_old': len(peaks_old),
        'peaks_new': len(peaks_new),
        'avg_width_old': avg_width_old,
        'avg_width_new': avg_width_new,
        'neg_ratio_old': neg_ratio_old,
        'neg_ratio_new': neg_ratio_new,
        'baseline_max_old': baseline_old.max(),
        'baseline_max_new': baseline_new.max(),
        'score': params_new.get('score', 0)
    }


if __name__ == '__main__':
    # 출력 디렉토리 생성
    output_dir = Path('result/baseline_comparison')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 샘플 선택
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    if len(csv_files) == 0:
        print("ERROR: exported_signals 디렉토리에 CSV 파일이 없습니다!")
        sys.exit(1)

    # 처음 3개 샘플 분석
    selected_files = list(csv_files[:3])

    print("\n" + "="*80)
    print("기존 vs 개선된 베이스라인 방법 비교")
    print("="*80)
    print(f"전체 샘플: {len(csv_files)}개")
    print(f"분석 샘플: {len(selected_files)}개\n")

    results = []
    for csv_file in selected_files:
        result = compare_baseline_methods(csv_file, output_dir)
        results.append(result)

    # 결과 요약
    print("\n" + "="*80)
    print("비교 결과 요약")
    print("="*80)

    for r in results:
        print(f"\n{r['sample'][:60]}")
        print(f"  앵커: {r['anchors_old']} → {r['anchors_new']} "
              f"({'증가' if r['anchors_new'] > r['anchors_old'] else '감소' if r['anchors_new'] < r['anchors_old'] else '동일'})")
        print(f"  피크: {r['peaks_old']} → {r['peaks_new']} "
              f"({'증가' if r['peaks_new'] > r['peaks_old'] else '감소' if r['peaks_new'] < r['peaks_old'] else '동일'})")

        if r['avg_width_old'] > 0 and r['avg_width_new'] > 0:
            width_change = (r['avg_width_new'] - r['avg_width_old']) / r['avg_width_old'] * 100
            print(f"  평균 너비: {r['avg_width_old']:.2f} → {r['avg_width_new']:.2f} ({width_change:+.1f}%)")

        print(f"  음수 비율: {r['neg_ratio_old']:.2f}% → {r['neg_ratio_new']:.2f}% "
              f"({'개선' if r['neg_ratio_new'] < r['neg_ratio_old'] else '동일' if r['neg_ratio_new'] == r['neg_ratio_old'] else '악화'})")
        print(f"  베이스라인 최대값: {r['baseline_max_old']:.1f} → {r['baseline_max_new']:.1f}")
        print(f"  품질 점수: {r['score']:.2f}")

    print(f"\n모든 이미지 저장 위치: {output_dir}/")
    print("\n분석 완료!")
