"""
스무딩 강화 및 음수 영역 후처리 테스트
이전 vs 개선 비교
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


def compare_before_after(csv_file):
    """이전 방식 vs 개선 방식 비교"""

    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    sample_name = csv_file.stem

    print(f"\n{'='*80}")
    print(f"샘플: {sample_name}")
    print(f"{'='*80}")

    # === 이전 방식 (스무딩 약함, 음수 후처리 없음) ===
    print("\n[이전 방식]")
    corrector_old = HybridBaselineCorrector(time, intensity)
    corrector_old.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
    baseline_old = corrector_old.generate_hybrid_baseline(
        method='robust_fit',
        enhanced_smoothing=False  # 스무딩 약함
    )
    corrected_old = intensity - baseline_old
    # 음수 후처리 없음

    neg_count_old = np.sum(corrected_old < 0)
    neg_ratio_old = neg_count_old / len(corrected_old) * 100
    neg_min_old = np.min(corrected_old)

    print(f"  음수 값: {neg_count_old}개 ({neg_ratio_old:.2f}%)")
    print(f"  최소값: {neg_min_old:.2f}")

    # === 개선 방식 (스무딩 강화, 음수 후처리) ===
    print("\n[개선 방식]")
    corrector_new = HybridBaselineCorrector(time, intensity)
    corrector_new.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
    baseline_new = corrector_new.generate_hybrid_baseline(
        method='robust_fit',
        enhanced_smoothing=True  # 스무딩 강화
    )
    corrected_new_raw = intensity - baseline_new
    corrected_new = corrector_new.post_process_corrected_signal(
        corrected_new_raw,
        clip_negative=True,
        negative_threshold=-50.0
    )

    neg_count_new_raw = np.sum(corrected_new_raw < 0)
    neg_ratio_new_raw = neg_count_new_raw / len(corrected_new_raw) * 100
    neg_count_new = np.sum(corrected_new < 0)
    neg_ratio_new = neg_count_new / len(corrected_new) * 100
    neg_min_new = np.min(corrected_new)

    print(f"  음수 값 (후처리 전): {neg_count_new_raw}개 ({neg_ratio_new_raw:.2f}%)")
    print(f"  음수 값 (후처리 후): {neg_count_new}개 ({neg_ratio_new:.2f}%)")
    print(f"  최소값: {neg_min_new:.2f}")
    print(f"  음수 감소: {neg_count_old - neg_count_new}개 ({neg_ratio_old - neg_ratio_new:.2f}%p)")

    # 피크 검출 (양방향)
    def detect_bidirectional_peaks(corrected_signal):
        """양수/음수 피크 검출"""
        signal_range = np.ptp(corrected_signal)
        noise_level = np.percentile(np.abs(corrected_signal), 25) * 1.5

        min_prominence = max(signal_range * 0.005, noise_level * 2)
        min_height = noise_level * 2

        # 양수 피크
        pos_peaks, _ = signal.find_peaks(
            corrected_signal,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        # 음수 피크
        neg_peaks, _ = signal.find_peaks(
            -corrected_signal,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        return pos_peaks, neg_peaks

    pos_old, neg_old = detect_bidirectional_peaks(corrected_old)
    pos_new, neg_new = detect_bidirectional_peaks(corrected_new)

    print(f"\n[피크 검출 비교]")
    print(f"  이전: 양수 {len(pos_old)}개, 음수 {len(neg_old)}개")
    print(f"  개선: 양수 {len(pos_new)}개, 음수 {len(neg_new)}개")
    print(f"  음수 피크 감소: {len(neg_old) - len(neg_new)}개")

    # 시각화
    fig = plt.figure(figsize=(18, 14))
    gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.3)

    # === Row 1: 이전 방식 ===
    # Panel 1: 원본 + 베이스라인
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본 신호')
    ax1.plot(time, baseline_old, 'r--', linewidth=2, label='베이스라인 (약한 스무딩)')
    ax1.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
    ax1.set_xlabel('시간 (min)', fontsize=10)
    ax1.set_ylabel('강도', fontsize=10)
    ax1.set_title('[이전] 원본 + 베이스라인', fontsize=11, fontweight='bold')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Panel 2: 보정 후
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(time, corrected_old, 'g-', linewidth=1, label='보정된 신호')
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax2.fill_between(time, 0, corrected_old, where=corrected_old >= 0,
                     color='green', alpha=0.3, label='양수 영역')
    ax2.fill_between(time, 0, corrected_old, where=corrected_old < 0,
                     color='red', alpha=0.3, label=f'음수 영역 ({neg_count_old}점)')
    ax2.set_xlabel('시간 (min)', fontsize=10)
    ax2.set_ylabel('강도', fontsize=10)
    ax2.set_title(f'[이전] 보정 후 (음수: {neg_ratio_old:.1f}%)', fontsize=11, fontweight='bold')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Panel 3: 검출된 피크
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.plot(time, corrected_old, 'gray', linewidth=0.5, alpha=0.5, label='보정 신호')
    ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    if len(pos_old) > 0:
        ax3.plot(time[pos_old], corrected_old[pos_old],
                'go', markersize=8, markeredgecolor='darkgreen', markeredgewidth=1.5,
                label=f'양수 피크 ({len(pos_old)})')
    if len(neg_old) > 0:
        ax3.plot(time[neg_old], corrected_old[neg_old],
                'r^', markersize=10, markeredgecolor='darkred', markeredgewidth=1.5,
                label=f'음수 피크 ({len(neg_old)})')
    ax3.set_xlabel('시간 (min)', fontsize=10)
    ax3.set_ylabel('강도', fontsize=10)
    ax3.set_title(f'[이전] 검출된 피크', fontsize=11, fontweight='bold')
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)

    # === Row 2: 개선 방식 (후처리 전) ===
    # Panel 4: 원본 + 베이스라인
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본 신호')
    ax4.plot(time, baseline_new, 'r--', linewidth=2, label='베이스라인 (강화 스무딩)')
    ax4.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
    ax4.set_xlabel('시간 (min)', fontsize=10)
    ax4.set_ylabel('강도', fontsize=10)
    ax4.set_title('[개선] 원본 + 베이스라인 (스무딩 강화)', fontsize=11, fontweight='bold')
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.3)

    # Panel 5: 보정 후 (후처리 전)
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.plot(time, corrected_new_raw, 'g-', linewidth=1, label='보정된 신호')
    ax5.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax5.fill_between(time, 0, corrected_new_raw, where=corrected_new_raw >= 0,
                     color='green', alpha=0.3, label='양수 영역')
    ax5.fill_between(time, 0, corrected_new_raw, where=corrected_new_raw < 0,
                     color='red', alpha=0.3, label=f'음수 영역 ({neg_count_new_raw}점)')
    ax5.set_xlabel('시간 (min)', fontsize=10)
    ax5.set_ylabel('강도', fontsize=10)
    ax5.set_title(f'[개선] 보정 후 - 후처리 전 (음수: {neg_ratio_new_raw:.1f}%)',
                 fontsize=11, fontweight='bold')
    ax5.legend(fontsize=8)
    ax5.grid(True, alpha=0.3)

    # Panel 6: 보정 후 (후처리 후)
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.plot(time, corrected_new, 'g-', linewidth=1, label='보정된 신호')
    ax6.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax6.fill_between(time, 0, corrected_new, where=corrected_new >= 0,
                     color='green', alpha=0.3, label='양수 영역')
    ax6.fill_between(time, 0, corrected_new, where=corrected_new < 0,
                     color='orange', alpha=0.3, label=f'음수 영역 ({neg_count_new}점)')
    ax6.set_xlabel('시간 (min)', fontsize=10)
    ax6.set_ylabel('강도', fontsize=10)
    ax6.set_title(f'[개선] 보정 후 - 후처리 후 (음수: {neg_ratio_new:.1f}%)',
                 fontsize=11, fontweight='bold')
    ax6.legend(fontsize=8)
    ax6.grid(True, alpha=0.3)

    # === Row 3: 검출된 피크 ===
    ax7 = fig.add_subplot(gs[2, :])
    ax7.plot(time, corrected_new, 'gray', linewidth=0.5, alpha=0.5, label='보정 신호 (개선)')
    ax7.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    if len(pos_new) > 0:
        ax7.plot(time[pos_new], corrected_new[pos_new],
                'go', markersize=10, markeredgecolor='darkgreen', markeredgewidth=2,
                label=f'양수 피크 ({len(pos_new)})')
    if len(neg_new) > 0:
        ax7.plot(time[neg_new], corrected_new[neg_new],
                'r^', markersize=12, markeredgecolor='darkred', markeredgewidth=2,
                label=f'음수 피크 ({len(neg_new)})')
        # 음수 피크 RT 표시
        for p in neg_new[:5]:
            ax7.annotate(f"{time[p]:.1f}",
                        xy=(time[p], corrected_new[p]),
                        xytext=(0, -15), textcoords='offset points',
                        ha='center', fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))
    ax7.set_xlabel('시간 (min)', fontsize=11)
    ax7.set_ylabel('강도', fontsize=11)
    ax7.set_title(f'[개선] 최종 검출 피크 (양수: {len(pos_new)}, 음수: {len(neg_new)})',
                 fontsize=12, fontweight='bold')
    ax7.legend(fontsize=9)
    ax7.grid(True, alpha=0.3)

    # === Row 4: 비교 ===
    # Panel 8: 베이스라인 비교
    ax8 = fig.add_subplot(gs[3, 0])
    ax8.plot(time, baseline_old, 'r--', linewidth=2, alpha=0.7, label='이전 (약한 스무딩)')
    ax8.plot(time, baseline_new, 'b--', linewidth=2, alpha=0.7, label='개선 (강화 스무딩)')
    ax8.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
    ax8.set_xlabel('시간 (min)', fontsize=10)
    ax8.set_ylabel('강도', fontsize=10)
    ax8.set_title('베이스라인 비교', fontsize=11, fontweight='bold')
    ax8.legend(fontsize=8)
    ax8.grid(True, alpha=0.3)

    # Panel 9: 보정 신호 비교
    ax9 = fig.add_subplot(gs[3, 1])
    ax9.plot(time, corrected_old, 'r-', linewidth=1, alpha=0.6, label='이전')
    ax9.plot(time, corrected_new, 'b-', linewidth=1, alpha=0.6, label='개선')
    ax9.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax9.set_xlabel('시간 (min)', fontsize=10)
    ax9.set_ylabel('강도', fontsize=10)
    ax9.set_title('보정 신호 비교', fontsize=11, fontweight='bold')
    ax9.legend(fontsize=8)
    ax9.grid(True, alpha=0.3)

    # Panel 10: 차이
    ax10 = fig.add_subplot(gs[3, 2])
    difference = corrected_old - corrected_new
    ax10.plot(time, difference, 'purple', linewidth=1, label='차이 (이전 - 개선)')
    ax10.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax10.fill_between(time, 0, difference, where=difference >= 0,
                     color='red', alpha=0.3, label='이전이 더 큼')
    ax10.fill_between(time, 0, difference, where=difference < 0,
                     color='blue', alpha=0.3, label='개선이 더 큼')
    ax10.set_xlabel('시간 (min)', fontsize=10)
    ax10.set_ylabel('강도 차이', fontsize=10)
    ax10.set_title(f'차이 (평균 절대값: {np.mean(np.abs(difference)):.2f})',
                  fontsize=11, fontweight='bold')
    ax10.legend(fontsize=8)
    ax10.grid(True, alpha=0.3)

    # 전체 제목
    fig.suptitle(f'스무딩 강화 및 음수 후처리 비교: {sample_name}',
                fontsize=14, fontweight='bold', y=0.995)

    # 저장
    output_file = f'result/smoothing_improvement_{sample_name}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n시각화 저장: {output_file}")
    plt.show()

    return {
        'sample': sample_name,
        'neg_count_old': neg_count_old,
        'neg_count_new': neg_count_new,
        'neg_reduction': neg_count_old - neg_count_new,
        'pos_peaks_old': len(pos_old),
        'neg_peaks_old': len(neg_old),
        'pos_peaks_new': len(pos_new),
        'neg_peaks_new': len(neg_new)
    }


def main():
    """첫 번째 샘플로 테스트"""
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    if len(csv_files) == 0:
        print("데이터 파일이 없습니다.")
        return

    Path('result').mkdir(exist_ok=True)

    # 첫 번째 파일
    result = compare_before_after(csv_files[0])

    print(f"\n{'='*80}")
    print("개선 효과 요약:")
    print(f"{'='*80}")
    print(f"  음수 값 감소: {result['neg_count_old']} → {result['neg_count_new']} "
          f"({result['neg_reduction']}개 감소)")
    print(f"  음수 피크 감소: {result['neg_peaks_old']} → {result['neg_peaks_new']}")
    print(f"  양수 피크 유지: {result['pos_peaks_old']} → {result['pos_peaks_new']}")


if __name__ == '__main__':
    main()
