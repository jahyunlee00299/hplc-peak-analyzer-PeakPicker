"""
Hybrid Baseline Visualization with Y-axis Break
================================================

베이스라인 보정 과정을 시각화하며, 큰 피크와 작은 피크를
동시에 효과적으로 표시하기 위해 Y축 브레이크를 자동 적용.

Author: PeakPicker Project
Date: 2025-11-26
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'solid' / 'infrastructure' / 'visualization'))

from hybrid_baseline import HybridBaselineCorrector

# Import broken axis components
try:
    from broken_axis_plotter import (
        PeakHeightAnalyzer, BrokenAxisPlotter, BreakStrategy, BreakPoint,
        BROKENAXES_AVAILABLE
    )
    if BROKENAXES_AVAILABLE:
        from brokenaxes import brokenaxes
except ImportError:
    BROKENAXES_AVAILABLE = False
    print("Warning: BrokenAxisPlotter not available")


def detect_peaks_simple(time, intensity, min_prominence_ratio=0.02):
    """
    간단한 피크 탐지

    Parameters
    ----------
    time : np.ndarray
        시간 배열
    intensity : np.ndarray
        강도 배열
    min_prominence_ratio : float
        최소 prominence 비율 (최대값 대비)

    Returns
    -------
    tuple
        (peak_indices, peak_heights)
    """
    from scipy import signal as sig

    min_prominence = np.max(intensity) * min_prominence_ratio
    peaks, properties = sig.find_peaks(
        intensity,
        prominence=min_prominence,
        distance=20
    )

    if len(peaks) == 0:
        return np.array([np.argmax(intensity)]), np.array([np.max(intensity)])

    return peaks, intensity[peaks]


def visualize_baseline_correction(csv_file, output_dir, use_break=True, language='en'):
    """
    베이스라인 보정 과정 시각화 (Y축 브레이크 포함)

    Parameters
    ----------
    csv_file : Path
        입력 CSV 파일 경로
    output_dir : Path
        출력 디렉토리
    use_break : bool
        Y축 브레이크 사용 여부
    language : str
        'en' for English, 'ko' for Korean

    Returns
    -------
    dict
        분석 결과 요약
    """
    # Labels based on language
    if language == 'ko':
        labels = {
            'original': '원본 크로마토그램',
            'anchor': '앵커 포인트',
            'baseline': '베이스라인',
            'corrected': '보정 후',
            'removed': '제거된 베이스라인',
            'time': '시간 (min)',
            'intensity': '강도',
            'peak_rank': '피크 순위 (높이순)',
            'peak_height': '피크 높이',
            'title1': '1. 원본 + 앵커 포인트',
            'title2': '2. 베이스라인 방법 비교',
            'title3': '3. 원본 + 베이스라인',
            'title4': '4. 보정 후',
            'title5': '5. 보정 전후 비교',
            'title6': '6. 피크 높이 분포',
            'optimal': '최적',
            'break_applied': 'Y축 브레이크 적용',
            'break_lower': '브레이크 하한',
            'break_upper': '브레이크 상한'
        }
    else:
        labels = {
            'original': 'Original Chromatogram',
            'anchor': 'Anchor Points',
            'baseline': 'Baseline',
            'corrected': 'Corrected',
            'removed': 'Removed Baseline',
            'time': 'Time (min)',
            'intensity': 'Intensity',
            'peak_rank': 'Peak Rank (by height)',
            'peak_height': 'Peak Height',
            'title1': '1. Original + Anchor Points',
            'title2': '2. Baseline Method Comparison',
            'title3': '3. Original + Baseline',
            'title4': '4. After Correction',
            'title5': '5. Before vs After',
            'title6': '6. Peak Height Distribution',
            'optimal': 'Optimal',
            'break_applied': 'Y-axis break applied',
            'break_lower': 'Break lower',
            'break_upper': 'Break upper'
        }

    # CSV 파일 읽기
    try:
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    except:
        df = pd.read_csv(csv_file, header=None)

    time = df[0].values
    intensity = df[1].values

    # 음수 값 처리
    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    sample_name = Path(csv_file).stem

    print(f"\nAnalyzing: {sample_name}")
    print(f"  Data points: {len(time)}")
    print(f"  Time range: {time[0]:.2f} - {time[-1]:.2f} min")
    print(f"  Intensity range: {intensity.min():.2f} - {intensity.max():.2f}")

    # 하이브리드 베이스라인 보정
    corrector = HybridBaselineCorrector(time, intensity)

    # 앵커 포인트 찾기
    anchor_points = corrector.find_baseline_anchor_points()
    print(f"  Anchor points: {len(anchor_points)}")

    # 세 가지 방법으로 베이스라인 생성
    baseline_methods = {}
    for method in ['weighted_spline', 'adaptive_connect', 'robust_fit']:
        baseline = corrector.generate_hybrid_baseline(method=method)
        baseline_methods[method] = baseline

    # 최적 베이스라인 선택
    best_baseline, best_params = corrector.optimize_baseline()
    best_method = best_params.get('method', 'unknown')
    print(f"  Best method: {best_method}")

    # 보정된 신호
    corrected = intensity - best_baseline
    corrected = np.maximum(corrected, 0)

    # 피크 탐지
    peak_indices, peak_heights = detect_peaks_simple(time, corrected)
    print(f"  Peaks detected: {len(peak_indices)}")

    # Y축 브레이크 분석
    break_point = None
    corrected_break = None

    if use_break and BROKENAXES_AVAILABLE:
        analyzer = PeakHeightAnalyzer(min_gap_ratio=2.5)
        break_point = analyzer.find_optimal_break_point(
            intensity, peak_heights, strategy=BreakStrategy.AUTO
        )
        corrected_break = analyzer.find_optimal_break_point(
            corrected, peak_heights, strategy=BreakStrategy.AUTO
        )

        if break_point:
            print(f"  Y-axis break: {break_point.lower_range[1]:.0f} ~ {break_point.upper_range[0]:.0f}")
        else:
            print(f"  Y-axis break: Not needed")

    # 시각화
    fig = plt.figure(figsize=(16, 14))
    gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.25)

    # === Panel 1: 원본 + 앵커 포인트 ===
    if break_point and BROKENAXES_AVAILABLE:
        bax1 = brokenaxes(ylims=break_point.ylims, subplot_spec=gs[0, 0],
                         hspace=0.05, despine=False)
        bax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label=labels['original'])

        # 앵커 포인트 (confidence별 색상)
        for ap in anchor_points:
            conf = getattr(ap, 'confidence', 0.5)
            color = plt.cm.RdYlGn(conf)
            size = 30 + conf * 50
            bax1.scatter([time[ap.index]], [ap.value],
                        c=[color], s=size, zorder=5, edgecolors='black', linewidths=0.5)

        bax1.set_title(f"{labels['title1']}\n[{labels['break_applied']}]", fontsize=10)
        bax1.set_xlabel(labels['time'])
        bax1.set_ylabel(labels['intensity'])
    else:
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label=labels['original'])

        anchor_times = [time[ap.index] for ap in anchor_points]
        anchor_intensities = [ap.value for ap in anchor_points]

        # Confidence 기반 색상
        confidences = [getattr(ap, 'confidence', 0.5) for ap in anchor_points]
        colors = [plt.cm.RdYlGn(c) for c in confidences]
        sizes = [30 + c * 50 for c in confidences]

        ax1.scatter(anchor_times, anchor_intensities,
                   c=colors, s=sizes, zorder=5, edgecolors='black', linewidths=0.5,
                   label=f"{labels['anchor']} ({len(anchor_points)})")

        ax1.set_title(labels['title1'], fontsize=10)
        ax1.set_xlabel(labels['time'])
        ax1.set_ylabel(labels['intensity'])
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

    # === Panel 2: 베이스라인 방법 비교 ===
    if break_point and BROKENAXES_AVAILABLE:
        bax2 = brokenaxes(ylims=break_point.ylims, subplot_spec=gs[0, 1],
                         hspace=0.05, despine=False)
        bax2.plot(time, intensity, 'gray', linewidth=1, alpha=0.3, label=labels['original'])

        colors = {'weighted_spline': 'orange', 'adaptive_connect': 'green', 'robust_fit': 'red'}
        for method, baseline in baseline_methods.items():
            linestyle = '-' if method == best_method else '--'
            linewidth = 2 if method == best_method else 1
            method_label = f'{method}' + (f' ({labels["optimal"]})' if method == best_method else '')
            bax2.plot(time, baseline, color=colors[method],
                     linestyle=linestyle, linewidth=linewidth, label=method_label)

        bax2.set_title(labels['title2'], fontsize=10)
        bax2.set_xlabel(labels['time'])
        bax2.set_ylabel(labels['intensity'])
        bax2.legend(loc='upper right', fontsize=8)
    else:
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.plot(time, intensity, 'gray', linewidth=1, alpha=0.3, label=labels['original'])

        colors = {'weighted_spline': 'orange', 'adaptive_connect': 'green', 'robust_fit': 'red'}
        for method, baseline in baseline_methods.items():
            linestyle = '-' if method == best_method else '--'
            linewidth = 2 if method == best_method else 1
            method_label = f'{method}' + (f' ({labels["optimal"]})' if method == best_method else '')
            ax2.plot(time, baseline, color=colors[method],
                    linestyle=linestyle, linewidth=linewidth, label=method_label)

        ax2.set_title(labels['title2'], fontsize=10)
        ax2.set_xlabel(labels['time'])
        ax2.set_ylabel(labels['intensity'])
        ax2.legend(loc='upper right', fontsize=8)
        ax2.grid(True, alpha=0.3)

    # === Panel 3: 원본 + 베이스라인 ===
    if break_point and BROKENAXES_AVAILABLE:
        bax3 = brokenaxes(ylims=break_point.ylims, subplot_spec=gs[1, 0],
                         hspace=0.05, despine=False)
        bax3.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label=labels['original'])
        bax3.plot(time, best_baseline, 'r-', linewidth=2, label=f"{labels['baseline']} ({best_method})")
        bax3.set_title(f"{labels['title3']} ({best_method})", fontsize=10)
        bax3.set_xlabel(labels['time'])
        bax3.set_ylabel(labels['intensity'])
        bax3.legend(loc='upper right')
    else:
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label=labels['original'])
        ax3.plot(time, best_baseline, 'r-', linewidth=2, label=f"{labels['baseline']} ({best_method})")
        ax3.fill_between(time, 0, best_baseline, alpha=0.2, color='red')
        ax3.set_title(f"{labels['title3']} ({best_method})", fontsize=10)
        ax3.set_xlabel(labels['time'])
        ax3.set_ylabel(labels['intensity'])
        ax3.legend(loc='upper right')
        ax3.grid(True, alpha=0.3)

    # === Panel 4: 보정 후 ===
    if corrected_break and BROKENAXES_AVAILABLE:
        bax4 = brokenaxes(ylims=corrected_break.ylims, subplot_spec=gs[1, 1],
                         hspace=0.05, despine=False)
        bax4.plot(time, corrected, 'g-', linewidth=1, label=labels['corrected'])
        bax4.set_title(f"{labels['title4']}\n[{labels['break_applied']}]", fontsize=10)
        bax4.set_xlabel(labels['time'])
        bax4.set_ylabel(labels['intensity'])
        bax4.legend(loc='upper right')
    else:
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.plot(time, corrected, 'g-', linewidth=1, label=labels['corrected'])
        ax4.fill_between(time, 0, corrected, alpha=0.3, color='green')
        ax4.set_title(labels['title4'], fontsize=10)
        ax4.set_xlabel(labels['time'])
        ax4.set_ylabel(labels['intensity'])
        ax4.legend(loc='upper right')
        ax4.grid(True, alpha=0.3)

    # === Panel 5: 보정 전후 비교 ===
    ax5 = fig.add_subplot(gs[2, 0])
    ax5.plot(time, intensity, 'b-', linewidth=1, alpha=0.4, label=labels['original'])
    ax5.plot(time, corrected, 'g-', linewidth=1.2, label=labels['corrected'])
    ax5.set_title(labels['title5'], fontsize=10)
    ax5.set_xlabel(labels['time'])
    ax5.set_ylabel(labels['intensity'])
    ax5.legend(loc='upper right')
    ax5.grid(True, alpha=0.3)

    # === Panel 6: 피크 높이 분포 ===
    ax6 = fig.add_subplot(gs[2, 1])

    if len(peak_heights) > 0:
        sorted_heights = np.sort(peak_heights)[::-1]
        x_pos = np.arange(len(sorted_heights))

        # 높이별 색상 분류
        q90 = np.percentile(peak_heights, 90) if len(peak_heights) > 1 else peak_heights[0]
        q75 = np.percentile(peak_heights, 75) if len(peak_heights) > 1 else peak_heights[0]

        colors = ['red' if h >= q90 else 'orange' if h >= q75 else 'blue'
                  for h in sorted_heights]

        ax6.bar(x_pos, sorted_heights, color=colors, alpha=0.7, edgecolor='black')
        ax6.set_xlabel(labels['peak_rank'])
        ax6.set_ylabel(labels['peak_height'])
        ax6.set_title(labels['title6'], fontsize=10)

        # 브레이크 포인트 표시
        if break_point:
            ax6.axhline(y=break_point.lower_range[1], color='gray',
                       linestyle='--', linewidth=1.5, label=labels['break_lower'])
            ax6.axhline(y=break_point.upper_range[0], color='gray',
                       linestyle='-.', linewidth=1.5, label=labels['break_upper'])

            # 생략 영역 표시
            ax6.axhspan(break_point.lower_range[1], break_point.upper_range[0],
                       alpha=0.1, color='gray', label='Break region')
            ax6.legend(loc='upper right', fontsize=8)
    else:
        ax6.text(0.5, 0.5, 'No peaks detected', ha='center', va='center',
                transform=ax6.transAxes, fontsize=12)

    ax6.grid(True, alpha=0.3)

    # 전체 제목
    break_info = ""
    if break_point:
        break_info = f" [Y-break: {break_point.gap_ratio:.0%} gap]"
    fig.suptitle(f'{sample_name} - Baseline Analysis{break_info}',
                fontsize=14, fontweight='bold', y=0.98)

    # 저장
    output_file = output_dir / f'{sample_name}_baseline_visualization.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  Saved: {output_file.name}")
    plt.close()

    return {
        'sample': sample_name,
        'method': best_method,
        'anchor_points': len(anchor_points),
        'peaks_detected': len(peak_indices),
        'original_max': intensity.max(),
        'corrected_max': corrected.max(),
        'baseline_max': best_baseline.max(),
        'break_applied': break_point is not None,
        'break_gap_ratio': break_point.gap_ratio if break_point else 0
    }


def visualize_baseline_simple(time, intensity, baseline, anchor_points=None,
                               peak_heights=None, sample_name="Sample",
                               output_path=None, use_break=True):
    """
    간단한 베이스라인 시각화 (외부 호출용)

    Parameters
    ----------
    time : np.ndarray
        시간 배열
    intensity : np.ndarray
        강도 배열
    baseline : np.ndarray
        베이스라인 배열
    anchor_points : list, optional
        앵커 포인트 리스트
    peak_heights : np.ndarray, optional
        피크 높이 배열
    sample_name : str
        샘플 이름
    output_path : str, optional
        저장 경로
    use_break : bool
        Y축 브레이크 사용 여부

    Returns
    -------
    Figure
        Matplotlib 피규어
    """
    # 피크 높이가 없으면 탐지
    if peak_heights is None:
        _, peak_heights = detect_peaks_simple(time, intensity)

    # 브레이크 포인트 계산
    break_point = None
    if use_break and BROKENAXES_AVAILABLE:
        analyzer = PeakHeightAnalyzer()
        break_point = analyzer.find_optimal_break_point(
            intensity, peak_heights, strategy=BreakStrategy.AUTO
        )

    corrected = np.maximum(intensity - baseline, 0)

    # 플롯 생성
    fig = plt.figure(figsize=(14, 10))
    gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.25)

    # Panel 1: Original + Baseline
    if break_point and BROKENAXES_AVAILABLE:
        bax1 = brokenaxes(ylims=break_point.ylims, subplot_spec=gs[0, 0],
                         hspace=0.05, despine=False)
        bax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='Original')
        bax1.plot(time, baseline, 'r-', linewidth=2, label='Baseline')
        bax1.set_title('Original + Baseline [Y-break]', fontsize=10)
        bax1.set_xlabel('Time (min)')
        bax1.set_ylabel('Intensity')
        bax1.legend(loc='upper right')
    else:
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='Original')
        ax1.plot(time, baseline, 'r-', linewidth=2, label='Baseline')
        ax1.set_title('Original + Baseline', fontsize=10)
        ax1.set_xlabel('Time (min)')
        ax1.set_ylabel('Intensity')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

    # Panel 2: Corrected
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(time, corrected, 'g-', linewidth=1)
    ax2.fill_between(time, 0, corrected, alpha=0.3, color='green')
    ax2.set_title('After Correction', fontsize=10)
    ax2.set_xlabel('Time (min)')
    ax2.set_ylabel('Intensity')
    ax2.grid(True, alpha=0.3)

    # Panel 3: Comparison
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(time, intensity, 'b-', linewidth=1, alpha=0.4, label='Original')
    ax3.plot(time, corrected, 'g-', linewidth=1.2, label='Corrected')
    ax3.set_title('Before vs After', fontsize=10)
    ax3.set_xlabel('Time (min)')
    ax3.set_ylabel('Intensity')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    # Panel 4: Peak Height Distribution
    ax4 = fig.add_subplot(gs[1, 1])
    if len(peak_heights) > 0:
        sorted_heights = np.sort(peak_heights)[::-1]
        x_pos = np.arange(len(sorted_heights))
        ax4.bar(x_pos, sorted_heights, color='steelblue', alpha=0.7, edgecolor='black')

        if break_point:
            ax4.axhline(y=break_point.lower_range[1], color='gray', linestyle='--')
            ax4.axhline(y=break_point.upper_range[0], color='gray', linestyle='-.')

    ax4.set_xlabel('Peak Rank')
    ax4.set_ylabel('Peak Height')
    ax4.set_title('Peak Height Distribution', fontsize=10)
    ax4.grid(True, alpha=0.3)

    fig.suptitle(f'{sample_name} - Baseline Analysis', fontsize=14, fontweight='bold')

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {output_path}")

    return fig


if __name__ == '__main__':
    # 출력 디렉토리
    output_dir = Path('result/baseline_visualization')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 분석할 샘플 선택
    csv_dir = Path('exported_signals')

    if csv_dir.exists():
        csv_files = sorted(csv_dir.glob('*.csv'))

        if len(csv_files) > 0:
            # 처음 3개, 중간, 마지막 선택
            selected_files = list(csv_files[:3])
            if len(csv_files) > 5:
                selected_files.append(csv_files[len(csv_files) // 2])
            if len(csv_files) > 1:
                selected_files.append(csv_files[-1])

            print("=" * 80)
            print("Hybrid Baseline Visualization with Y-axis Break")
            print("=" * 80)
            print(f"Total {len(selected_files)} samples to visualize\n")

            results = []
            for csv_file in selected_files:
                result = visualize_baseline_correction(csv_file, output_dir, use_break=True)
                results.append(result)

            # 요약
            print("\n" + "=" * 80)
            print("Summary")
            print("=" * 80)
            for r in results:
                print(f"{r['sample'][:40]:40s}")
                print(f"  Method: {r['method']}")
                print(f"  Anchors: {r['anchor_points']}, Peaks: {r['peaks_detected']}")
                print(f"  Break applied: {r['break_applied']}")
                if r['break_applied']:
                    print(f"  Break gap: {r['break_gap_ratio']:.1%}")
                print()

            print(f"All images saved to: {output_dir}/")
        else:
            print("No CSV files found in exported_signals/")
    else:
        print("exported_signals/ directory not found")
        print("\nRunning with synthetic test data...")

        # 합성 데이터로 테스트
        np.random.seed(42)
        time = np.linspace(0, 30, 3000)

        signal = np.zeros_like(time)
        signal += 50000 * np.exp(-((time - 8)**2) / 0.5)
        signal += 2500 * np.exp(-((time - 12)**2) / 0.3)
        signal += 1800 * np.exp(-((time - 16)**2) / 0.4)
        signal += 2200 * np.exp(-((time - 20)**2) / 0.35)
        signal += np.random.normal(0, 50, len(time))
        signal = np.maximum(signal, 0)

        baseline = 100 + 30 * np.sin(time / 5) + time * 3

        peak_heights = np.array([50000, 2500, 1800, 2200])

        fig = visualize_baseline_simple(
            time, signal, baseline,
            peak_heights=peak_heights,
            sample_name="Synthetic_Test",
            output_path=output_dir / "synthetic_test_baseline.png",
            use_break=True
        )
        plt.close()

        print(f"\nSynthetic test saved to: {output_dir}/synthetic_test_baseline.png")
