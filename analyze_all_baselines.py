"""
모든 샘플에 대해 베이스라인 방법별 차이 분석
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import signal
import sys
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector
from improved_baseline import ImprovedBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


def detect_peaks_from_corrected(corrected_signal, time):
    """보정된 신호에서 피크 검출"""
    if len(corrected_signal) == 0 or np.max(corrected_signal) == 0:
        return [], {}

    noise_level = np.percentile(corrected_signal, 25) * 1.5

    peaks, props = signal.find_peaks(
        corrected_signal,
        prominence=np.ptp(corrected_signal) * 0.005,
        height=max(noise_level * 3, np.std(corrected_signal) * 2),
        width=0
    )

    return peaks, props


def analyze_single_file(csv_file):
    """단일 파일 분석"""
    # 데이터 로드
    try:
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity = df[1].values

        # 음수 처리
        if np.min(intensity) < 0:
            intensity = intensity - np.min(intensity)
    except Exception as e:
        print(f"Error loading {csv_file.name}: {e}")
        return None

    results = {}

    # 1. HybridBaselineCorrector - weighted_spline
    try:
        corrector_old = HybridBaselineCorrector(time, intensity)
        baseline_hybrid, params_hybrid = corrector_old.optimize_baseline_with_linear_peaks()
        corrected_hybrid = np.maximum(intensity - baseline_hybrid, 0)
        peaks_hybrid, props_hybrid = detect_peaks_from_corrected(corrected_hybrid, time)

        results['hybrid'] = {
            'baseline': baseline_hybrid,
            'corrected': corrected_hybrid,
            'peaks': peaks_hybrid,
            'props': props_hybrid,
            'num_peaks': len(peaks_hybrid),
            'method': params_hybrid.get('method', 'unknown'),
            'avg_height': np.mean(corrected_hybrid[peaks_hybrid]) if len(peaks_hybrid) > 0 else 0,
            'total_area': np.trapz(corrected_hybrid, time),
            'avg_width': np.mean(props_hybrid['widths']) if 'widths' in props_hybrid and len(props_hybrid['widths']) > 0 else 0
        }
    except Exception as e:
        print(f"Error in hybrid method for {csv_file.name}: {e}")
        results['hybrid'] = None

    # 2. ImprovedBaselineCorrector - adaptive_spline
    try:
        corrector_new = ImprovedBaselineCorrector(time, intensity)
        baseline_adaptive, params_adaptive = corrector_new.optimize_baseline(
            methods=['adaptive_spline'],
            use_linear_peaks=True
        )
        corrected_adaptive = np.maximum(intensity - baseline_adaptive, 0)
        peaks_adaptive, props_adaptive = detect_peaks_from_corrected(corrected_adaptive, time)

        results['adaptive'] = {
            'baseline': baseline_adaptive,
            'corrected': corrected_adaptive,
            'peaks': peaks_adaptive,
            'props': props_adaptive,
            'num_peaks': len(peaks_adaptive),
            'score': params_adaptive.get('score', 0),
            'avg_height': np.mean(corrected_adaptive[peaks_adaptive]) if len(peaks_adaptive) > 0 else 0,
            'total_area': np.trapz(corrected_adaptive, time),
            'avg_width': np.mean(props_adaptive['widths']) if 'widths' in props_adaptive and len(props_adaptive['widths']) > 0 else 0
        }
    except Exception as e:
        print(f"Error in adaptive method for {csv_file.name}: {e}")
        results['adaptive'] = None

    # 3. ImprovedBaselineCorrector - robust_spline
    try:
        corrector_new2 = ImprovedBaselineCorrector(time, intensity)
        corrector_new2.find_anchors()
        baseline_robust = corrector_new2.generate_baseline(
            method='robust_spline',
            apply_rt_relaxation=True
        )
        baseline_robust = corrector_new2.apply_linear_to_peaks(baseline_robust)
        corrected_robust = np.maximum(intensity - baseline_robust, 0)
        peaks_robust, props_robust = detect_peaks_from_corrected(corrected_robust, time)

        results['robust'] = {
            'baseline': baseline_robust,
            'corrected': corrected_robust,
            'peaks': peaks_robust,
            'props': props_robust,
            'num_peaks': len(peaks_robust),
            'avg_height': np.mean(corrected_robust[peaks_robust]) if len(peaks_robust) > 0 else 0,
            'total_area': np.trapz(corrected_robust, time),
            'avg_width': np.mean(props_robust['widths']) if 'widths' in props_robust and len(props_robust['widths']) > 0 else 0
        }
    except Exception as e:
        print(f"Error in robust method for {csv_file.name}: {e}")
        results['robust'] = None

    # 4. ImprovedBaselineCorrector - linear
    try:
        corrector_new3 = ImprovedBaselineCorrector(time, intensity)
        corrector_new3.find_anchors()
        baseline_linear = corrector_new3.generate_baseline(
            method='linear',
            apply_rt_relaxation=True
        )
        baseline_linear = corrector_new3.apply_linear_to_peaks(baseline_linear)
        corrected_linear = np.maximum(intensity - baseline_linear, 0)
        peaks_linear, props_linear = detect_peaks_from_corrected(corrected_linear, time)

        results['linear'] = {
            'baseline': baseline_linear,
            'corrected': corrected_linear,
            'peaks': peaks_linear,
            'props': props_linear,
            'num_peaks': len(peaks_linear),
            'avg_height': np.mean(corrected_linear[peaks_linear]) if len(peaks_linear) > 0 else 0,
            'total_area': np.trapz(corrected_linear, time),
            'avg_width': np.mean(props_linear['widths']) if 'widths' in props_linear and len(props_linear['widths']) > 0 else 0
        }
    except Exception as e:
        print(f"Error in linear method for {csv_file.name}: {e}")
        results['linear'] = None

    return {
        'file': csv_file.name,
        'time': time,
        'intensity': intensity,
        'results': results
    }


def calculate_differences(file_results):
    """방법 간 차이 계산"""
    results = file_results['results']
    methods = ['hybrid', 'adaptive', 'robust', 'linear']

    # 유효한 결과만 필터링
    valid_methods = [m for m in methods if results.get(m) is not None]

    if len(valid_methods) < 2:
        return None

    # 피크 수 차이
    peak_counts = [results[m]['num_peaks'] for m in valid_methods]
    peak_count_diff = max(peak_counts) - min(peak_counts)
    peak_count_std = np.std(peak_counts)

    # 평균 높이 차이
    heights = [results[m]['avg_height'] for m in valid_methods if results[m]['avg_height'] > 0]
    if len(heights) >= 2:
        height_diff_pct = (max(heights) - min(heights)) / np.mean(heights) * 100 if np.mean(heights) > 0 else 0
        height_std = np.std(heights)
    else:
        height_diff_pct = 0
        height_std = 0

    # 총 면적 차이
    areas = [results[m]['total_area'] for m in valid_methods]
    area_diff_pct = (max(areas) - min(areas)) / np.mean(areas) * 100 if np.mean(areas) > 0 else 0

    # 평균 너비 차이
    widths = [results[m]['avg_width'] for m in valid_methods if results[m]['avg_width'] > 0]
    if len(widths) >= 2:
        width_diff_pct = (max(widths) - min(widths)) / np.mean(widths) * 100 if np.mean(widths) > 0 else 0
    else:
        width_diff_pct = 0

    # 종합 차이 점수 (높을수록 방법 간 차이가 큼)
    total_diff_score = (
        peak_count_diff * 10 +  # 피크 수 차이에 높은 가중치
        height_diff_pct +
        area_diff_pct * 0.5 +
        width_diff_pct * 0.3
    )

    return {
        'file': file_results['file'],
        'peak_count_diff': peak_count_diff,
        'peak_count_std': peak_count_std,
        'height_diff_pct': height_diff_pct,
        'height_std': height_std,
        'area_diff_pct': area_diff_pct,
        'width_diff_pct': width_diff_pct,
        'total_diff_score': total_diff_score,
        'peak_counts': {m: results[m]['num_peaks'] for m in valid_methods},
        'avg_heights': {m: results[m]['avg_height'] for m in valid_methods},
        'total_areas': {m: results[m]['total_area'] for m in valid_methods}
    }


def visualize_top_differences(all_file_results, diff_summary, output_dir, top_n=5):
    """차이가 가장 큰 파일들 시각화"""
    # 차이 점수로 정렬
    sorted_diffs = sorted(diff_summary, key=lambda x: x['total_diff_score'], reverse=True)
    top_files = sorted_diffs[:top_n]

    print(f"\n차이가 가장 큰 {top_n}개 파일:")
    for i, diff in enumerate(top_files, 1):
        print(f"{i}. {diff['file']}")
        print(f"   총 차이 점수: {diff['total_diff_score']:.2f}")
        print(f"   피크 수: {diff['peak_counts']}")
        print(f"   높이 차이: {diff['height_diff_pct']:.2f}%")
        print(f"   면적 차이: {diff['area_diff_pct']:.2f}%\n")

    # 각 파일에 대해 상세 시각화
    for idx, diff in enumerate(top_files, 1):
        file_name = diff['file']

        # 해당 파일의 결과 찾기
        file_result = next((f for f in all_file_results if f['file'] == file_name), None)
        if file_result is None:
            continue

        time = file_result['time']
        intensity = file_result['intensity']
        results = file_result['results']

        # 시각화
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.25)

        methods_info = [
            ('hybrid', 'Hybrid (기존)', 'red'),
            ('adaptive', 'Adaptive Spline (개선)', 'blue'),
            ('robust', 'Robust Spline (개선)', 'green'),
            ('linear', 'Linear (개선)', 'orange')
        ]

        # Panel 1-4: 각 방법의 베이스라인
        for i, (method, label, color) in enumerate(methods_info):
            if results.get(method) is None:
                continue

            ax = fig.add_subplot(gs[i // 2, i % 2])
            r = results[method]

            ax.plot(time, intensity, 'gray', alpha=0.5, linewidth=1, label='원본')
            ax.plot(time, r['baseline'], color=color, linestyle='--', linewidth=2, label='베이스라인')
            ax.plot(time, r['corrected'], color, alpha=0.7, linewidth=1.5, label='보정 후')

            if len(r['peaks']) > 0:
                ax.scatter(time[r['peaks']], r['corrected'][r['peaks']],
                          color='red', s=100, zorder=5, marker='^', edgecolors='black', linewidths=1)

            ax.set_xlabel('시간 (min)', fontweight='bold')
            ax.set_ylabel('강도', fontweight='bold')
            ax.set_title(f'{label}\n피크: {r["num_peaks"]}개, 평균 높이: {r["avg_height"]:.0f}',
                        fontweight='bold', fontsize=11)
            ax.legend(loc='upper right')
            ax.grid(True, alpha=0.3)

        # Panel 5: 베이스라인 비교
        ax5 = fig.add_subplot(gs[2, 0])
        for method, label, color in methods_info:
            if results.get(method) is None:
                continue
            ax5.plot(time, results[method]['baseline'], color=color, linewidth=2, label=label, alpha=0.7)

        ax5.set_xlabel('시간 (min)', fontweight='bold')
        ax5.set_ylabel('베이스라인 강도', fontweight='bold')
        ax5.set_title('베이스라인 비교', fontweight='bold', fontsize=11)
        ax5.legend(loc='upper right')
        ax5.grid(True, alpha=0.3)

        # Panel 6: 비교 테이블
        ax6 = fig.add_subplot(gs[2, 1])

        table_data = []
        for method, label, color in methods_info:
            if results.get(method) is None:
                continue
            r = results[method]
            table_data.append([
                label,
                f"{r['num_peaks']}",
                f"{r['avg_height']:.0f}",
                f"{r['total_area']:.0f}",
                f"{r['avg_width']:.1f}" if r['avg_width'] > 0 else "N/A"
            ])

        table = ax6.table(
            cellText=table_data,
            colLabels=['방법', '피크 수', '평균 높이', '총 면적', '평균 너비'],
            cellLoc='center',
            loc='center',
            colWidths=[0.25, 0.15, 0.2, 0.2, 0.2]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2.5)

        # 헤더 스타일
        for i in range(5):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')

        ax6.axis('off')
        ax6.set_title('방법별 비교 요약', fontweight='bold', fontsize=11, pad=20)

        # 전체 제목
        fig.suptitle(f'Top {idx}: {file_name}\n(총 차이 점수: {diff["total_diff_score"]:.2f})',
                     fontsize=14, fontweight='bold', y=0.995)

        # 저장
        output_file = output_dir / f'top_{idx}_{Path(file_name).stem}.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"저장: {output_file.name}")


def create_summary_visualization(diff_summary, output_dir):
    """전체 요약 시각화"""
    # 차이 점수로 정렬
    sorted_diffs = sorted(diff_summary, key=lambda x: x['total_diff_score'], reverse=True)

    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3)

    # 1. 총 차이 점수 분포
    ax1 = fig.add_subplot(gs[0, :])
    scores = [d['total_diff_score'] for d in sorted_diffs]
    files = [d['file'][:40] for d in sorted_diffs]  # 파일명 40자로 제한

    colors = ['red' if i < 5 else 'orange' if i < 10 else 'blue' for i in range(len(scores))]
    bars = ax1.barh(range(len(scores)), scores, color=colors, alpha=0.7)
    ax1.set_yticks(range(len(files)))
    ax1.set_yticklabels(files, fontsize=7)
    ax1.set_xlabel('총 차이 점수', fontweight='bold')
    ax1.set_title('파일별 베이스라인 방법 차이 점수 (높을수록 방법 간 차이 큼)', fontweight='bold', fontsize=12)
    ax1.grid(True, alpha=0.3, axis='x')
    ax1.invert_yaxis()

    # 범례
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='red', alpha=0.7, label='Top 5'),
        Patch(facecolor='orange', alpha=0.7, label='Top 6-10'),
        Patch(facecolor='blue', alpha=0.7, label='나머지')
    ]
    ax1.legend(handles=legend_elements, loc='lower right')

    # 2. 피크 수 차이 분포
    ax2 = fig.add_subplot(gs[1, 0])
    peak_diffs = [d['peak_count_diff'] for d in sorted_diffs]
    ax2.hist(peak_diffs, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
    ax2.set_xlabel('피크 수 차이', fontweight='bold')
    ax2.set_ylabel('파일 수', fontweight='bold')
    ax2.set_title('피크 수 차이 분포', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.axvline(np.mean(peak_diffs), color='red', linestyle='--', linewidth=2, label=f'평균: {np.mean(peak_diffs):.1f}')
    ax2.legend()

    # 3. 높이 차이 분포
    ax3 = fig.add_subplot(gs[1, 1])
    height_diffs = [d['height_diff_pct'] for d in sorted_diffs if d['height_diff_pct'] > 0]
    ax3.hist(height_diffs, bins=20, color='lightcoral', edgecolor='black', alpha=0.7)
    ax3.set_xlabel('평균 높이 차이 (%)', fontweight='bold')
    ax3.set_ylabel('파일 수', fontweight='bold')
    ax3.set_title('평균 높이 차이 분포', fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.axvline(np.mean(height_diffs), color='red', linestyle='--', linewidth=2, label=f'평균: {np.mean(height_diffs):.1f}%')
    ax3.legend()

    # 4. 면적 차이 분포
    ax4 = fig.add_subplot(gs[2, 0])
    area_diffs = [d['area_diff_pct'] for d in sorted_diffs]
    ax4.hist(area_diffs, bins=20, color='lightgreen', edgecolor='black', alpha=0.7)
    ax4.set_xlabel('총 면적 차이 (%)', fontweight='bold')
    ax4.set_ylabel('파일 수', fontweight='bold')
    ax4.set_title('총 면적 차이 분포', fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.axvline(np.mean(area_diffs), color='red', linestyle='--', linewidth=2, label=f'평균: {np.mean(area_diffs):.1f}%')
    ax4.legend()

    # 5. 너비 차이 분포
    ax5 = fig.add_subplot(gs[2, 1])
    width_diffs = [d['width_diff_pct'] for d in sorted_diffs if d['width_diff_pct'] > 0]
    ax5.hist(width_diffs, bins=20, color='plum', edgecolor='black', alpha=0.7)
    ax5.set_xlabel('평균 너비 차이 (%)', fontweight='bold')
    ax5.set_ylabel('파일 수', fontweight='bold')
    ax5.set_title('평균 너비 차이 분포', fontweight='bold')
    ax5.grid(True, alpha=0.3)
    ax5.axvline(np.mean(width_diffs), color='red', linestyle='--', linewidth=2, label=f'평균: {np.mean(width_diffs):.1f}%')
    ax5.legend()

    fig.suptitle(f'베이스라인 방법 비교 - 전체 분석 ({len(sorted_diffs)}개 파일)',
                 fontsize=14, fontweight='bold', y=0.995)

    output_file = output_dir / 'summary_all_files.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n전체 요약 저장: {output_file.name}")


if __name__ == '__main__':
    # 출력 디렉토리
    output_dir = Path('result/baseline_method_comparison')
    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV 파일 찾기
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    print(f"총 {len(csv_files)}개 파일 분석 시작...")

    # 모든 파일 분석
    all_file_results = []
    for idx, csv_file in enumerate(csv_files, 1):
        print(f"[{idx}/{len(csv_files)}] {csv_file.name}")
        result = analyze_single_file(csv_file)
        if result is not None:
            all_file_results.append(result)

    print(f"\n분석 완료: {len(all_file_results)}개 파일")

    # 차이 계산
    diff_summary = []
    for file_result in all_file_results:
        diff = calculate_differences(file_result)
        if diff is not None:
            diff_summary.append(diff)

    print(f"차이 계산 완료: {len(diff_summary)}개 파일")

    # 결과 저장 (CSV)
    summary_df = pd.DataFrame([
        {
            'file': d['file'],
            'total_diff_score': d['total_diff_score'],
            'peak_count_diff': d['peak_count_diff'],
            'height_diff_pct': d['height_diff_pct'],
            'area_diff_pct': d['area_diff_pct'],
            'width_diff_pct': d['width_diff_pct'],
            'peak_counts': str(d['peak_counts'])
        }
        for d in diff_summary
    ])
    summary_df = summary_df.sort_values('total_diff_score', ascending=False)
    summary_df.to_csv(output_dir / 'method_comparison_summary.csv', index=False, encoding='utf-8-sig')
    print(f"\n요약 CSV 저장: method_comparison_summary.csv")

    # 시각화
    print("\n시각화 생성 중...")
    visualize_top_differences(all_file_results, diff_summary, output_dir, top_n=5)
    create_summary_visualization(diff_summary, output_dir)

    print(f"\n모든 결과가 저장되었습니다: {output_dir}/")
    print("\n분석 완료!")
