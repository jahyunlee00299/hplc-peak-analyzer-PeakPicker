"""
베이스라인 점검: 기존 결과 재분석
베이스라인이 신호 위로 가는 경우와 음수 피크를 확인
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


def inspect_baseline(csv_file, output_dir):
    """
    개별 샘플의 베이스라인 상세 점검
    """
    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    sample_name = csv_file.stem

    print(f"\n{'='*80}")
    print(f"샘플: {sample_name}")
    print(f"{'='*80}")

    # 원본 신호 통계
    print(f"\n[원본 신호 통계]")
    print(f"  범위: {np.min(intensity):.2f} ~ {np.max(intensity):.2f}")
    print(f"  평균: {np.mean(intensity):.2f}")
    print(f"  표준편차: {np.std(intensity):.2f}")
    print(f"  음수 값: {np.sum(intensity < 0)}개 ({np.sum(intensity < 0)/len(intensity)*100:.2f}%)")

    # 베이스라인 보정 (robust_fit)
    corrector_robust = HybridBaselineCorrector(time, intensity)
    corrector_robust.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
    baseline_robust = corrector_robust.generate_hybrid_baseline(method='robust_fit')
    corrected_robust = intensity - baseline_robust

    # 베이스라인 보정 (weighted_spline)
    corrector_weighted = HybridBaselineCorrector(time, intensity)
    corrector_weighted.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
    baseline_weighted = corrector_weighted.generate_hybrid_baseline(method='weighted_spline')
    corrected_weighted = intensity - baseline_weighted

    # 베이스라인 통계
    print(f"\n[베이스라인 통계 - Robust Fit]")
    print(f"  범위: {np.min(baseline_robust):.2f} ~ {np.max(baseline_robust):.2f}")
    above_signal_robust = baseline_robust > intensity
    print(f"  신호 위로 간 점: {np.sum(above_signal_robust)}개 ({np.sum(above_signal_robust)/len(intensity)*100:.2f}%)")

    print(f"\n[베이스라인 통계 - Weighted Spline]")
    print(f"  범위: {np.min(baseline_weighted):.2f} ~ {np.max(baseline_weighted):.2f}")
    above_signal_weighted = baseline_weighted > intensity
    print(f"  신호 위로 간 점: {np.sum(above_signal_weighted)}개 ({np.sum(above_signal_weighted)/len(intensity)*100:.2f}%)")

    # 보정 후 통계
    print(f"\n[보정 후 통계 - Robust Fit]")
    print(f"  범위: {np.min(corrected_robust):.2f} ~ {np.max(corrected_robust):.2f}")
    print(f"  음수 값: {np.sum(corrected_robust < 0)}개 ({np.sum(corrected_robust < 0)/len(corrected_robust)*100:.2f}%)")

    print(f"\n[보정 후 통계 - Weighted Spline]")
    print(f"  범위: {np.min(corrected_weighted):.2f} ~ {np.max(corrected_weighted):.2f}")
    print(f"  음수 값: {np.sum(corrected_weighted < 0)}개 ({np.sum(corrected_weighted < 0)/len(corrected_weighted)*100:.2f}%)")

    # 피크 검출 (양방향)
    def detect_bidirectional_peaks(corrected_signal, time):
        """양수/음수 피크 모두 검출"""
        signal_range = np.ptp(corrected_signal)
        noise_level = np.percentile(np.abs(corrected_signal), 25) * 1.5

        min_prominence = max(signal_range * 0.005, noise_level * 2)
        min_height = noise_level * 2

        # 양수 피크
        pos_peaks, pos_props = signal.find_peaks(
            corrected_signal,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        # 음수 피크
        neg_peaks, neg_props = signal.find_peaks(
            -corrected_signal,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        return pos_peaks, neg_peaks

    pos_peaks_robust, neg_peaks_robust = detect_bidirectional_peaks(corrected_robust, time)
    pos_peaks_weighted, neg_peaks_weighted = detect_bidirectional_peaks(corrected_weighted, time)

    print(f"\n[피크 검출 - Robust Fit]")
    print(f"  양수 피크: {len(pos_peaks_robust)}개")
    print(f"  음수 피크: {len(neg_peaks_robust)}개")
    if len(neg_peaks_robust) > 0:
        print(f"  음수 피크 RT: {[f'{time[p]:.2f}' for p in neg_peaks_robust[:5]]}")

    print(f"\n[피크 검출 - Weighted Spline]")
    print(f"  양수 피크: {len(pos_peaks_weighted)}개")
    print(f"  음수 피크: {len(neg_peaks_weighted)}개")
    if len(neg_peaks_weighted) > 0:
        print(f"  음수 피크 RT: {[f'{time[p]:.2f}' for p in neg_peaks_weighted[:5]]}")

    # 시각화
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Row 1: Robust Fit
    # Panel 1: 원본 + 베이스라인
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본 신호')
    ax1.plot(time, baseline_robust, 'r--', linewidth=2, label='베이스라인 (Robust)')
    ax1.axhline(y=0, color='gray', linestyle=':', alpha=0.5)

    # 베이스라인이 신호 위로 가는 영역 강조
    if np.any(above_signal_robust):
        ax1.fill_between(time, intensity, baseline_robust,
                        where=above_signal_robust,
                        color='red', alpha=0.3,
                        label=f'베이스라인 > 신호 ({np.sum(above_signal_robust)}점)')

    ax1.set_xlabel('시간 (min)', fontsize=10)
    ax1.set_ylabel('강도', fontsize=10)
    ax1.set_title('Robust Fit: 원본 + 베이스라인', fontsize=11, fontweight='bold')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Panel 2: 보정 후 신호
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(time, corrected_robust, 'g-', linewidth=1, label='보정된 신호')
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수/음수 영역 구분
    ax2.fill_between(time, 0, corrected_robust,
                    where=corrected_robust >= 0,
                    color='green', alpha=0.3, label='양수 영역')
    ax2.fill_between(time, 0, corrected_robust,
                    where=corrected_robust < 0,
                    color='red', alpha=0.3, label='음수 영역')

    ax2.set_xlabel('시간 (min)', fontsize=10)
    ax2.set_ylabel('강도', fontsize=10)
    ax2.set_title(f'Robust Fit: 보정 후 (음수: {np.sum(corrected_robust < 0)}점)',
                 fontsize=11, fontweight='bold')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Panel 3: 검출된 피크
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.plot(time, corrected_robust, 'gray', linewidth=0.5, alpha=0.5, label='보정 신호')
    ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수 피크
    if len(pos_peaks_robust) > 0:
        ax3.plot(time[pos_peaks_robust], corrected_robust[pos_peaks_robust],
                'go', markersize=8, markeredgecolor='darkgreen', markeredgewidth=1.5,
                label=f'양수 피크 ({len(pos_peaks_robust)})')

    # 음수 피크
    if len(neg_peaks_robust) > 0:
        ax3.plot(time[neg_peaks_robust], corrected_robust[neg_peaks_robust],
                'r^', markersize=10, markeredgecolor='darkred', markeredgewidth=1.5,
                label=f'음수 피크 ({len(neg_peaks_robust)})')
        # 음수 피크 RT 표시 (처음 5개만)
        for p in neg_peaks_robust[:5]:
            ax3.annotate(f"{time[p]:.1f}",
                       xy=(time[p], corrected_robust[p]),
                       xytext=(0, -15), textcoords='offset points',
                       ha='center', fontsize=7,
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))

    ax3.set_xlabel('시간 (min)', fontsize=10)
    ax3.set_ylabel('강도', fontsize=10)
    ax3.set_title(f'Robust Fit: 검출된 피크', fontsize=11, fontweight='bold')
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)

    # Row 2: Weighted Spline
    # Panel 4: 원본 + 베이스라인
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본 신호')
    ax4.plot(time, baseline_weighted, 'r--', linewidth=2, label='베이스라인 (Weighted)')
    ax4.axhline(y=0, color='gray', linestyle=':', alpha=0.5)

    # 베이스라인이 신호 위로 가는 영역 강조
    if np.any(above_signal_weighted):
        ax4.fill_between(time, intensity, baseline_weighted,
                        where=above_signal_weighted,
                        color='red', alpha=0.3,
                        label=f'베이스라인 > 신호 ({np.sum(above_signal_weighted)}점)')

    ax4.set_xlabel('시간 (min)', fontsize=10)
    ax4.set_ylabel('강도', fontsize=10)
    ax4.set_title('Weighted Spline: 원본 + 베이스라인', fontsize=11, fontweight='bold')
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.3)

    # Panel 5: 보정 후 신호
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.plot(time, corrected_weighted, 'g-', linewidth=1, label='보정된 신호')
    ax5.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수/음수 영역 구분
    ax5.fill_between(time, 0, corrected_weighted,
                    where=corrected_weighted >= 0,
                    color='green', alpha=0.3, label='양수 영역')
    ax5.fill_between(time, 0, corrected_weighted,
                    where=corrected_weighted < 0,
                    color='red', alpha=0.3, label='음수 영역')

    ax5.set_xlabel('시간 (min)', fontsize=10)
    ax5.set_ylabel('강도', fontsize=10)
    ax5.set_title(f'Weighted Spline: 보정 후 (음수: {np.sum(corrected_weighted < 0)}점)',
                 fontsize=11, fontweight='bold')
    ax5.legend(fontsize=8)
    ax5.grid(True, alpha=0.3)

    # Panel 6: 검출된 피크
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.plot(time, corrected_weighted, 'gray', linewidth=0.5, alpha=0.5, label='보정 신호')
    ax6.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수 피크
    if len(pos_peaks_weighted) > 0:
        ax6.plot(time[pos_peaks_weighted], corrected_weighted[pos_peaks_weighted],
                'go', markersize=8, markeredgecolor='darkgreen', markeredgewidth=1.5,
                label=f'양수 피크 ({len(pos_peaks_weighted)})')

    # 음수 피크
    if len(neg_peaks_weighted) > 0:
        ax6.plot(time[neg_peaks_weighted], corrected_weighted[neg_peaks_weighted],
                'r^', markersize=10, markeredgecolor='darkred', markeredgewidth=1.5,
                label=f'음수 피크 ({len(neg_peaks_weighted)})')
        # 음수 피크 RT 표시 (처음 5개만)
        for p in neg_peaks_weighted[:5]:
            ax6.annotate(f"{time[p]:.1f}",
                       xy=(time[p], corrected_weighted[p]),
                       xytext=(0, -15), textcoords='offset points',
                       ha='center', fontsize=7,
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))

    ax6.set_xlabel('시간 (min)', fontsize=10)
    ax6.set_ylabel('강도', fontsize=10)
    ax6.set_title(f'Weighted Spline: 검출된 피크', fontsize=11, fontweight='bold')
    ax6.legend(fontsize=8)
    ax6.grid(True, alpha=0.3)

    # Row 3: 비교
    # Panel 7: 베이스라인 비교
    ax7 = fig.add_subplot(gs[2, 0])
    ax7.plot(time, intensity, 'k-', linewidth=1, alpha=0.3, label='원본 신호')
    ax7.plot(time, baseline_robust, 'r--', linewidth=2, alpha=0.8, label='Robust Fit')
    ax7.plot(time, baseline_weighted, 'b--', linewidth=2, alpha=0.8, label='Weighted Spline')
    ax7.axhline(y=0, color='gray', linestyle=':', alpha=0.5)

    ax7.set_xlabel('시간 (min)', fontsize=10)
    ax7.set_ylabel('강도', fontsize=10)
    ax7.set_title('베이스라인 방법 비교', fontsize=11, fontweight='bold')
    ax7.legend(fontsize=8)
    ax7.grid(True, alpha=0.3)

    # Panel 8: 보정 신호 비교
    ax8 = fig.add_subplot(gs[2, 1])
    ax8.plot(time, corrected_robust, 'r-', linewidth=1, alpha=0.6, label='Robust Fit')
    ax8.plot(time, corrected_weighted, 'b-', linewidth=1, alpha=0.6, label='Weighted Spline')
    ax8.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    ax8.set_xlabel('시간 (min)', fontsize=10)
    ax8.set_ylabel('강도', fontsize=10)
    ax8.set_title('보정 신호 비교', fontsize=11, fontweight='bold')
    ax8.legend(fontsize=8)
    ax8.grid(True, alpha=0.3)

    # Panel 9: 차이 (Robust - Weighted)
    ax9 = fig.add_subplot(gs[2, 2])
    difference = corrected_robust - corrected_weighted
    ax9.plot(time, difference, 'purple', linewidth=1, label='차이 (Robust - Weighted)')
    ax9.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax9.fill_between(time, 0, difference, where=difference >= 0,
                    color='red', alpha=0.3, label='Robust가 더 큼')
    ax9.fill_between(time, 0, difference, where=difference < 0,
                    color='blue', alpha=0.3, label='Weighted가 더 큼')

    ax9.set_xlabel('시간 (min)', fontsize=10)
    ax9.set_ylabel('강도 차이', fontsize=10)
    ax9.set_title(f'방법 간 차이 (평균: {np.mean(np.abs(difference)):.2f})',
                 fontsize=11, fontweight='bold')
    ax9.legend(fontsize=8)
    ax9.grid(True, alpha=0.3)

    # 전체 제목
    fig.suptitle(f'베이스라인 점검: {sample_name}',
                fontsize=14, fontweight='bold', y=0.995)

    # 저장
    output_file = output_dir / f'{sample_name}_baseline_inspection.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n시각화 저장: {output_file.name}")
    plt.close()

    return {
        'sample': sample_name,
        'original_has_negative': np.any(intensity < 0),
        'robust_baseline_above': np.sum(above_signal_robust),
        'weighted_baseline_above': np.sum(above_signal_weighted),
        'robust_corrected_negative': np.sum(corrected_robust < 0),
        'weighted_corrected_negative': np.sum(corrected_weighted < 0),
        'robust_pos_peaks': len(pos_peaks_robust),
        'robust_neg_peaks': len(neg_peaks_robust),
        'weighted_pos_peaks': len(pos_peaks_weighted),
        'weighted_neg_peaks': len(neg_peaks_weighted)
    }


def main():
    """메인 분석 함수"""
    # 출력 디렉토리
    output_dir = Path('result/baseline_inspection')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 데이터 디렉토리
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    if len(csv_files) == 0:
        print("데이터 파일이 없습니다.")
        return

    # 처음 10개 샘플 분석
    selected_files = list(csv_files[:10])

    print("\n" + "="*80)
    print("베이스라인 점검 분석")
    print("="*80)
    print(f"총 {len(selected_files)}개 샘플 분석")
    print(f"출력 디렉토리: {output_dir}/")

    results = []
    for csv_file in selected_files:
        result = inspect_baseline(csv_file, output_dir)
        results.append(result)

    # 전체 요약
    print("\n" + "="*80)
    print("전체 분석 요약")
    print("="*80)

    summary_df = pd.DataFrame(results)

    print(f"\n[원본 신호]")
    print(f"  음수 값 포함 샘플: {summary_df['original_has_negative'].sum()}개")

    print(f"\n[베이스라인이 신호 위로 간 점 수]")
    print(f"  Robust Fit:")
    print(f"    - 평균: {summary_df['robust_baseline_above'].mean():.1f}점")
    print(f"    - 최대: {summary_df['robust_baseline_above'].max()}점 ({summary_df.loc[summary_df['robust_baseline_above'].idxmax(), 'sample']})")
    print(f"  Weighted Spline:")
    print(f"    - 평균: {summary_df['weighted_baseline_above'].mean():.1f}점")
    print(f"    - 최대: {summary_df['weighted_baseline_above'].max()}점 ({summary_df.loc[summary_df['weighted_baseline_above'].idxmax(), 'sample']})")

    print(f"\n[보정 후 음수 값 수]")
    print(f"  Robust Fit:")
    print(f"    - 평균: {summary_df['robust_corrected_negative'].mean():.1f}점")
    print(f"    - 최대: {summary_df['robust_corrected_negative'].max()}점")
    print(f"  Weighted Spline:")
    print(f"    - 평균: {summary_df['weighted_corrected_negative'].mean():.1f}점")
    print(f"    - 최대: {summary_df['weighted_corrected_negative'].max()}점")

    print(f"\n[검출된 음수 피크]")
    print(f"  Robust Fit:")
    print(f"    - 총 음수 피크: {summary_df['robust_neg_peaks'].sum()}개")
    print(f"    - 음수 피크 있는 샘플: {(summary_df['robust_neg_peaks'] > 0).sum()}개")
    print(f"  Weighted Spline:")
    print(f"    - 총 음수 피크: {summary_df['weighted_neg_peaks'].sum()}개")
    print(f"    - 음수 피크 있는 샘플: {(summary_df['weighted_neg_peaks'] > 0).sum()}개")

    print(f"\n[검출된 양수 피크]")
    print(f"  Robust Fit: 평균 {summary_df['robust_pos_peaks'].mean():.1f}개")
    print(f"  Weighted Spline: 평균 {summary_df['weighted_pos_peaks'].mean():.1f}개")

    # 상세 테이블
    print(f"\n[샘플별 상세]")
    print(f"{'샘플':<40} | R-양수 | R-음수 | W-양수 | W-음수 | R-Above | W-Above")
    print("-" * 100)
    for _, row in summary_df.iterrows():
        print(f"{row['sample'][:40]:<40} | "
              f"{row['robust_pos_peaks']:6d} | "
              f"{row['robust_neg_peaks']:6d} | "
              f"{row['weighted_pos_peaks']:6d} | "
              f"{row['weighted_neg_peaks']:6d} | "
              f"{row['robust_baseline_above']:7d} | "
              f"{row['weighted_baseline_above']:7d}")

    # CSV로 저장
    summary_file = output_dir / 'baseline_inspection_summary.csv'
    summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
    print(f"\n요약 저장: {summary_file}")

    print(f"\n모든 이미지 저장: {output_dir}/")


if __name__ == '__main__':
    main()
