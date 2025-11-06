"""
하이브리드 베이스라인 시각화
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def visualize_baseline_correction(csv_file, output_dir):
    """베이스라인 보정 과정 시각화"""
    
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
    print(f"  시간 범위: {time[0]:.2f} - {time[-1]:.2f} min")
    print(f"  강도 범위: {intensity.min():.2f} - {intensity.max():.2f}")
    
    # 하이브리드 베이스라인 보정
    corrector = HybridBaselineCorrector(time, intensity)
    
    # 앵커 포인트 찾기
    anchor_points = corrector.find_baseline_anchor_points()
    print(f"  베이스라인 앵커 포인트: {len(anchor_points)}개")
    
    # 세 가지 방법으로 베이스라인 생성
    baseline_methods = {}
    for method in ['weighted_spline', 'adaptive_connect', 'robust_fit']:
        baseline = corrector.generate_hybrid_baseline(method=method)
        baseline_methods[method] = baseline
    
    # 최적 베이스라인 선택
    best_baseline, best_params = corrector.optimize_baseline()
    best_method = best_params.get('method', 'unknown')
    print(f"  최적 베이스라인 방법: {best_method}")
    
    # 보정된 신호
    corrected = intensity - best_baseline
    corrected = np.maximum(corrected, 0)
    
    # 시각화
    fig = plt.figure(figsize=(16, 12))
    
    # 1. 원본 데이터 + 앵커 포인트
    ax1 = plt.subplot(3, 2, 1)
    ax1.plot(time, intensity, 'b-', linewidth=1, label='원본 크로마토그램', alpha=0.7)
    
    # 앵커 포인트 표시
    anchor_times = [time[ap.index] for ap in anchor_points]
    anchor_intensities = [ap.value for ap in anchor_points]
    ax1.scatter(anchor_times, anchor_intensities, 
                c='red', s=50, zorder=5, label=f'앵커 포인트 ({len(anchor_points)}개)')
    
    ax1.set_xlabel('시간 (min)')
    ax1.set_ylabel('강도')
    ax1.set_title('1. 원본 데이터 + 베이스라인 앵커 포인트')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 세 가지 베이스라인 방법 비교
    ax2 = plt.subplot(3, 2, 2)
    ax2.plot(time, intensity, 'gray', linewidth=1, alpha=0.3, label='원본')
    
    colors = {'weighted_spline': 'orange', 'adaptive_connect': 'green', 'robust_fit': 'red'}
    for method, baseline in baseline_methods.items():
        linestyle = '-' if method == best_method else '--'
        linewidth = 2 if method == best_method else 1
        label = f'{method}' + (' ✓최적' if method == best_method else '')
        ax2.plot(time, baseline, color=colors[method], 
                linestyle=linestyle, linewidth=linewidth, label=label)
    
    ax2.set_xlabel('시간 (min)')
    ax2.set_ylabel('강도')
    ax2.set_title('2. 세 가지 베이스라인 방법 비교')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. 원본 + 최적 베이스라인
    ax3 = plt.subplot(3, 2, 3)
    ax3.plot(time, intensity, 'b-', linewidth=1, label='원본', alpha=0.7)
    ax3.plot(time, best_baseline, 'r-', linewidth=2, label=f'베이스라인 ({best_method})')
    ax3.fill_between(time, 0, best_baseline, alpha=0.2, color='red', label='베이스라인 영역')
    
    ax3.set_xlabel('시간 (min)')
    ax3.set_ylabel('강도')
    ax3.set_title(f'3. 원본 + 최적 베이스라인 ({best_method})')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. 보정 후 신호
    ax4 = plt.subplot(3, 2, 4)
    ax4.plot(time, corrected, 'g-', linewidth=1, label='보정 후')
    ax4.fill_between(time, 0, corrected, alpha=0.3, color='green')
    
    ax4.set_xlabel('시간 (min)')
    ax4.set_ylabel('강도')
    ax4.set_title('4. 베이스라인 보정 후')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. 원본 vs 보정 후 비교
    ax5 = plt.subplot(3, 2, 5)
    ax5.plot(time, intensity, 'b-', linewidth=1, alpha=0.5, label='원본')
    ax5.plot(time, corrected, 'g-', linewidth=1.5, label='보정 후')
    
    ax5.set_xlabel('시간 (min)')
    ax5.set_ylabel('강도')
    ax5.set_title('5. 보정 전후 비교')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # 6. 제거된 베이스라인 (차이)
    ax6 = plt.subplot(3, 2, 6)
    baseline_diff = intensity - corrected
    ax6.plot(time, baseline_diff, 'r-', linewidth=1, label='제거된 베이스라인')
    ax6.fill_between(time, 0, baseline_diff, alpha=0.3, color='red')
    
    ax6.set_xlabel('시간 (min)')
    ax6.set_ylabel('강도')
    ax6.set_title('6. 제거된 베이스라인 성분')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 저장
    output_file = output_dir / f'{sample_name}_baseline_visualization.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  저장: {output_file.name}")
    plt.close()
    
    return {
        'sample': sample_name,
        'method': best_method,
        'anchor_points': len(anchor_points),
        'original_max': intensity.max(),
        'corrected_max': corrected.max(),
        'baseline_max': best_baseline.max()
    }


if __name__ == '__main__':
    # 출력 디렉토리
    output_dir = Path('result/baseline_visualization')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 분석할 샘플 선택 (다양한 패턴)
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))
    
    # 처음 5개, 중간 2개, 마지막 1개 선택
    selected_files = (
        list(csv_files[:3]) +  # 처음 3개
        [csv_files[25]] +       # 중간
        [csv_files[-1]]         # 마지막
    )
    
    print("=" * 80)
    print("하이브리드 베이스라인 시각화")
    print("=" * 80)
    print(f"총 {len(selected_files)}개 샘플 시각화\n")
    
    results = []
    for csv_file in selected_files:
        result = visualize_baseline_correction(csv_file, output_dir)
        results.append(result)
    
    # 요약
    print("\n" + "=" * 80)
    print("시각화 완료 요약")
    print("=" * 80)
    for r in results:
        print(f"{r['sample'][:40]:40s}")
        print(f"  방법: {r['method']}")
        print(f"  앵커: {r['anchor_points']}개")
        print(f"  원본 최대: {r['original_max']:.1f}")
        print(f"  보정 최대: {r['corrected_max']:.1f}")
        print(f"  베이스라인 최대: {r['baseline_max']:.1f}")
        print()
    
    print(f"모든 이미지 저장: {output_dir}/")
