"""
직선 베이스라인 방법과 Robust vs Weighted 비교 시각화
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


def visualize_linear_baseline_comparison(csv_file: Path, output_dir: Path):
    """
    직선 베이스라인 적용 전후 비교 시각화
    """
    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # 음수 값 처리
    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    # HybridBaselineCorrector 초기화
    corrector = HybridBaselineCorrector(time, intensity)

    # 1. 기존 방법 (optimize_baseline)
    baseline_old, params_old = corrector.optimize_baseline()
    corrected_old = np.maximum(intensity - baseline_old, 0)

    # 2. 새로운 방법 (optimize_baseline_with_linear_peaks)
    baseline_new, params_new = corrector.optimize_baseline_with_linear_peaks()
    corrected_new = np.maximum(intensity - baseline_new, 0)

    # 3. Robust와 Weighted 개별 생성
    corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
    baseline_robust = corrector.generate_hybrid_baseline(method='robust_fit')
    baseline_weighted = corrector.generate_hybrid_baseline(method='weighted_spline')

    corrected_robust = np.maximum(intensity - baseline_robust, 0)
    corrected_weighted = np.maximum(intensity - baseline_weighted, 0)

    # 피크 검출
    def detect_peaks(corrected_signal):
        noise_level = np.percentile(corrected_signal, 25) * 1.5
        peaks, props = signal.find_peaks(
            corrected_signal,
            prominence=np.ptp(corrected_signal) * 0.005,
            height=noise_level * 3,
            width=0
        )
        return peaks, props

    peaks_old, _ = detect_peaks(corrected_old)
    peaks_new, _ = detect_peaks(corrected_new)
    peaks_robust, props_robust = detect_peaks(corrected_robust)
    peaks_weighted, props_weighted = detect_peaks(corrected_weighted)

    # 시각화
    fig = plt.figure(figsize=(20, 12))

    # 6-panel layout
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

    # Panel 1: 기존 방법 (optimize_baseline)
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.7)
    ax1.plot(time, baseline_old, 'k--', linewidth=2.5, label='베이스라인 (기존)')
    ax1.fill_between(time, 0, baseline_old, alpha=0.2, color='gray')
    ax1.scatter(time[peaks_old], intensity[peaks_old], color='green', s=100,
                zorder=5, label=f'검출 피크 ({len(peaks_old)}개)')
    ax1.set_xlabel('시간 (min)', fontweight='bold', fontsize=11)
    ax1.set_ylabel('강도', fontweight='bold', fontsize=11)
    ax1.set_title(f'기존 방법: {params_old.get("method", "optimize_baseline")}',
                  fontweight='bold', fontsize=12)
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Panel 2: 새로운 방법 (linear peaks)
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.7)
    ax2.plot(time, baseline_new, 'r--', linewidth=2.5, label='베이스라인 (직선 피크)')
    ax2.fill_between(time, 0, baseline_new, alpha=0.2, color='pink')
    ax2.scatter(time[peaks_new], intensity[peaks_new], color='green', s=100,
                zorder=5, label=f'검출 피크 ({len(peaks_new)}개)')
    ax2.set_xlabel('시간 (min)', fontweight='bold', fontsize=11)
    ax2.set_ylabel('강도', fontweight='bold', fontsize=11)

    if 'selection_info' in params_new:
        info = params_new['selection_info']
        title = f'새로운 방법: hybrid_linear_peaks\n(robust={info["robust_selected_count"]}, weighted={info["weighted_selected_count"]})'
    else:
        title = '새로운 방법: hybrid_linear_peaks'
    ax2.set_title(title, fontweight='bold', fontsize=12)
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    # Panel 3: Robust 방법
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.7)
    ax3.plot(time, baseline_robust, 'purple', linestyle='--', linewidth=2.5, label='베이스라인 (robust)')
    ax3.fill_between(time, 0, baseline_robust, alpha=0.2, color='purple')
    ax3.scatter(time[peaks_robust], intensity[peaks_robust], color='green', s=100,
                zorder=5, label=f'검출 피크 ({len(peaks_robust)}개)')

    # 피크 너비 표시
    if 'widths' in props_robust and len(props_robust['widths']) > 0:
        avg_width = np.mean(props_robust['widths'])
        ax3.text(0.02, 0.98, f'평균 너비: {avg_width:.2f}',
                transform=ax3.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax3.set_xlabel('시간 (min)', fontweight='bold', fontsize=11)
    ax3.set_ylabel('강도', fontweight='bold', fontsize=11)
    ax3.set_title('Robust Fit 방법', fontweight='bold', fontsize=12)
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    # Panel 4: Weighted 방법
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(time, intensity, 'b-', linewidth=1, label='원본 신호', alpha=0.7)
    ax4.plot(time, baseline_weighted, 'orange', linestyle='--', linewidth=2.5, label='베이스라인 (weighted)')
    ax4.fill_between(time, 0, baseline_weighted, alpha=0.2, color='orange')
    ax4.scatter(time[peaks_weighted], intensity[peaks_weighted], color='green', s=100,
                zorder=5, label=f'검출 피크 ({len(peaks_weighted)}개)')

    # 피크 너비 표시
    if 'widths' in props_weighted and len(props_weighted['widths']) > 0:
        avg_width = np.mean(props_weighted['widths'])
        ax4.text(0.02, 0.98, f'평균 너비: {avg_width:.2f}',
                transform=ax4.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax4.set_xlabel('시간 (min)', fontweight='bold', fontsize=11)
    ax4.set_ylabel('강도', fontweight='bold', fontsize=11)
    ax4.set_title('Weighted Spline 방법', fontweight='bold', fontsize=12)
    ax4.legend(loc='upper right')
    ax4.grid(True, alpha=0.3)

    # Panel 5: 베이스라인 차이 (새로운 - 기존)
    ax5 = fig.add_subplot(gs[2, 0])
    baseline_diff = baseline_new - baseline_old
    ax5.plot(time, baseline_diff, 'g-', linewidth=2)
    ax5.axhline(y=0, color='k', linestyle='--', alpha=0.5)
    ax5.fill_between(time, 0, baseline_diff, where=(baseline_diff > 0),
                     alpha=0.3, color='green', label='새 방법이 더 높음')
    ax5.fill_between(time, 0, baseline_diff, where=(baseline_diff < 0),
                     alpha=0.3, color='red', label='기존 방법이 더 높음')
    ax5.set_xlabel('시간 (min)', fontweight='bold', fontsize=11)
    ax5.set_ylabel('차이', fontweight='bold', fontsize=11)
    ax5.set_title('베이스라인 차이 (새로운 - 기존)', fontweight='bold', fontsize=12)
    ax5.legend(loc='upper right')
    ax5.grid(True, alpha=0.3)

    # Panel 6: 보정된 신호 비교
    ax6 = fig.add_subplot(gs[2, 1])
    ax6.plot(time, corrected_old, 'b-', linewidth=1.5, alpha=0.5, label='기존 방법')
    ax6.plot(time, corrected_new, 'r-', linewidth=1.5, alpha=0.5, label='새로운 방법')
    ax6.set_xlabel('시간 (min)', fontweight='bold', fontsize=11)
    ax6.set_ylabel('강도 (보정 후)', fontweight='bold', fontsize=11)
    ax6.set_title('베이스라인 보정 후 신호 비교', fontweight='bold', fontsize=12)
    ax6.legend(loc='upper right')
    ax6.grid(True, alpha=0.3)

    # 전체 제목
    sample_name = csv_file.stem
    fig.suptitle(f'{sample_name}\n직선 베이스라인 방법 비교',
                 fontsize=14, fontweight='bold')

    # 저장
    output_file = output_dir / f'{sample_name}_linear_baseline_comparison.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  시각화 저장: {output_file.name}")

    return {
        'sample': sample_name,
        'peaks_old': len(peaks_old),
        'peaks_new': len(peaks_new),
        'peaks_robust': len(peaks_robust),
        'peaks_weighted': len(peaks_weighted),
        'method_old': params_old.get('method', 'unknown'),
        'selection_info': params_new.get('selection_info', {})
    }


if __name__ == '__main__':
    # 출력 디렉토리 생성
    output_dir = Path('result/linear_baseline_comparison')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 분석할 샘플 선택
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    # 처음 50개 샘플로 시각화
    selected_files = list(csv_files[:50])

    print("\n" + "="*80)
    print("직선 베이스라인 방법 비교 시각화")
    print("="*80)
    print(f"총 {len(selected_files)}개 샘플 시각화\n")

    results = []
    for csv_file in selected_files:
        print(f"\n샘플: {csv_file.stem}")
        result = visualize_linear_baseline_comparison(csv_file, output_dir)
        results.append(result)

    # 결과 요약
    print("\n" + "="*80)
    print("시각화 완료 요약")
    print("="*80)

    for result in results:
        print(f"\n{result['sample']}")
        print(f"  기존 방법 ({result['method_old']}): {result['peaks_old']}개 피크")
        print(f"  새로운 방법 (linear_peaks): {result['peaks_new']}개 피크")
        print(f"  Robust: {result['peaks_robust']}개, Weighted: {result['peaks_weighted']}개")

        if result['selection_info']:
            info = result['selection_info']
            print(f"  선택: robust={info.get('robust_selected_count', 0)}개, "
                  f"weighted={info.get('weighted_selected_count', 0)}개")

    print(f"\n모든 이미지 저장: {output_dir}/")
