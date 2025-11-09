"""
개선된 베이스라인 보정 예제
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from improved_baseline import ImprovedBaselineCorrector, process_exported_signal


def example_1_basic_usage():
    """예제 1: 기본 사용법"""
    print("=" * 60)
    print("예제 1: 기본 사용법")
    print("=" * 60)

    # 간편 함수 사용
    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    time, intensity, baseline, params = process_exported_signal(
        str(csv_file),
        method='auto',
        use_linear_peaks=True
    )

    print(f"\n파일: {csv_file.name}")
    print(f"방법: {params['method']}")
    print(f"앵커 포인트: {params['num_anchors']}개")
    print(f"품질 점수: {params['score']:.2f}")

    # 보정된 신호
    corrected = np.maximum(intensity - baseline, 0)

    # 간단한 시각화
    plt.figure(figsize=(12, 6))

    plt.subplot(2, 1, 1)
    plt.plot(time, intensity, 'b-', label='Original', alpha=0.7)
    plt.plot(time, baseline, 'r--', label='Baseline', linewidth=2)
    plt.xlabel('Time (min)')
    plt.ylabel('Intensity')
    plt.title('Baseline Detection')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 1, 2)
    plt.plot(time, corrected, 'g-', label='Corrected')
    plt.fill_between(time, 0, corrected, alpha=0.3, color='green')
    plt.xlabel('Time (min)')
    plt.ylabel('Intensity')
    plt.title('Baseline Corrected Signal')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('../result/example_1_basic.png', dpi=150)
    print("\n저장: result/example_1_basic.png")
    plt.close()


def example_2_manual_control():
    """예제 2: 수동 제어"""
    print("\n" + "=" * 60)
    print("예제 2: 수동 제어")
    print("=" * 60)

    import pandas as pd

    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # Corrector 생성
    corrector = ImprovedBaselineCorrector(time, intensity)

    # 앵커 포인트 수동 설정
    anchors = corrector.find_anchors(
        valley_prominence_factor=0.01,
        local_min_percentile=10,
        min_anchor_distance=15
    )

    print(f"\n앵커 포인트: {len(anchors)}개")
    print("\n앵커 타입 분포:")
    print(f"  Valley: {sum(1 for a in anchors if a.type == 'valley')}개")
    print(f"  Local Min: {sum(1 for a in anchors if a.type == 'local_min')}개")
    print(f"  Boundary: {sum(1 for a in anchors if a.type == 'boundary')}개")

    # 세 가지 방법으로 베이스라인 생성
    methods = {
        'adaptive_spline': 'Adaptive Spline',
        'robust_spline': 'Robust Spline',
        'linear': 'Linear'
    }

    plt.figure(figsize=(14, 8))

    for idx, (method, label) in enumerate(methods.items(), 1):
        baseline = corrector.generate_baseline(
            method=method,
            apply_rt_relaxation=True
        )

        corrected = np.maximum(intensity - baseline, 0)

        plt.subplot(2, 2, idx)
        plt.plot(time, intensity, 'b-', alpha=0.5, label='Original')
        plt.plot(time, baseline, 'r--', linewidth=2, label='Baseline')
        plt.plot(time, corrected, 'g-', alpha=0.7, label='Corrected')
        plt.xlabel('Time (min)')
        plt.ylabel('Intensity')
        plt.title(f'{label} Method')
        plt.legend()
        plt.grid(True, alpha=0.3)

    # 앵커 포인트 표시
    plt.subplot(2, 2, 4)
    plt.plot(time, intensity, 'b-', alpha=0.6, label='Signal')

    for anchor in anchors:
        if anchor.type == 'valley':
            color, marker = 'red', 'v'
        elif anchor.type == 'local_min':
            color, marker = 'green', 'o'
        else:
            color, marker = 'orange', 's'

        plt.scatter(anchor.rt, anchor.value,
                   c=color, marker=marker,
                   s=100 * anchor.confidence,
                   edgecolors='black', linewidths=0.5,
                   alpha=0.8)

    plt.xlabel('Time (min)')
    plt.ylabel('Intensity')
    plt.title(f'Anchor Points ({len(anchors)})')
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('../result/example_2_manual.png', dpi=150)
    print("\n저장: result/example_2_manual.png")
    plt.close()


def example_3_optimization():
    """예제 3: 자동 최적화"""
    print("\n" + "=" * 60)
    print("예제 3: 자동 최적화")
    print("=" * 60)

    import pandas as pd

    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    corrector = ImprovedBaselineCorrector(time, intensity)

    # 자동 최적화 (여러 방법 시도)
    baseline, params = corrector.optimize_baseline(
        methods=['adaptive_spline', 'robust_spline'],
        use_linear_peaks=True
    )

    print(f"\n최적 방법: {params['method']}")
    print(f"앵커 포인트: {params['num_anchors']}개")
    print(f"품질 점수: {params['score']:.2f}")
    print(f"직선 피크 적용: {params['use_linear_peaks']}")

    corrected = np.maximum(intensity - baseline, 0)

    # 상세 시각화
    fig = plt.figure(figsize=(14, 10))

    # 원본 + 베이스라인
    ax1 = plt.subplot(3, 1, 1)
    ax1.plot(time, intensity, 'b-', label='Original', alpha=0.7)
    ax1.plot(time, baseline, 'r--', linewidth=2, label='Baseline')
    ax1.fill_between(time, 0, baseline, alpha=0.2, color='red')
    ax1.set_xlabel('Time (min)')
    ax1.set_ylabel('Intensity')
    ax1.set_title(f'Optimized Baseline - {params["method"]}')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 보정 후
    ax2 = plt.subplot(3, 1, 2)
    ax2.plot(time, corrected, 'g-', linewidth=1.5)
    ax2.fill_between(time, 0, corrected, alpha=0.3, color='green')
    ax2.set_xlabel('Time (min)')
    ax2.set_ylabel('Intensity')
    ax2.set_title('Corrected Signal')
    ax2.grid(True, alpha=0.3)

    # 베이스라인 상세
    ax3 = plt.subplot(3, 1, 3)
    ax3.plot(time, baseline, 'r-', linewidth=2)

    # 앵커 포인트 표시
    for anchor in corrector.anchors:
        if anchor.type == 'valley':
            color, marker, label = 'red', 'v', 'Valley'
        elif anchor.type == 'local_min':
            color, marker, label = 'green', 'o', 'Local Min'
        else:
            color, marker, label = 'orange', 's', 'Boundary'

        ax3.scatter(anchor.rt, anchor.value,
                   c=color, marker=marker, s=80,
                   edgecolors='black', linewidths=0.5,
                   alpha=0.8, zorder=5)

    ax3.set_xlabel('Time (min)')
    ax3.set_ylabel('Intensity')
    ax3.set_title(f'Baseline with Anchors ({len(corrector.anchors)})')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('../result/example_3_optimization.png', dpi=150)
    print("\n저장: result/example_3_optimization.png")
    plt.close()


def example_4_rt_relaxation():
    """예제 4: RT 기반 슬로프 완화"""
    print("\n" + "=" * 60)
    print("예제 4: RT 기반 슬로프 완화")
    print("=" * 60)

    import pandas as pd

    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    corrector = ImprovedBaselineCorrector(time, intensity)
    corrector.find_anchors()

    # RT 완화 없이
    baseline_no_relax = corrector.generate_baseline(
        method='adaptive_spline',
        apply_rt_relaxation=False
    )

    # RT 완화 적용
    baseline_with_relax = corrector.generate_baseline(
        method='adaptive_spline',
        apply_rt_relaxation=True
    )

    print(f"\n앵커 포인트: {len(corrector.anchors)}개")

    # 기울기 비교
    slope_no_relax = np.abs(np.diff(baseline_no_relax))
    slope_with_relax = np.abs(np.diff(baseline_with_relax))

    print(f"최대 기울기 (완화 없음): {np.max(slope_no_relax):.2f}")
    print(f"최대 기울기 (완화 적용): {np.max(slope_with_relax):.2f}")

    # 시각화
    plt.figure(figsize=(14, 8))

    plt.subplot(2, 1, 1)
    plt.plot(time, intensity, 'b-', alpha=0.5, label='Original')
    plt.plot(time, baseline_no_relax, 'orange', linestyle='--',
             linewidth=2, label='No RT Relaxation')
    plt.plot(time, baseline_with_relax, 'r-',
             linewidth=2, label='With RT Relaxation')
    plt.xlabel('Time (min)')
    plt.ylabel('Intensity')
    plt.title('Baseline Comparison: RT Relaxation Effect')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 1, 2)
    plt.plot(time[:-1], slope_no_relax, 'orange', alpha=0.7,
             label='Slope (No Relaxation)')
    plt.plot(time[:-1], slope_with_relax, 'r', alpha=0.7,
             label='Slope (With Relaxation)')
    plt.xlabel('Time (min)')
    plt.ylabel('Absolute Slope')
    plt.title('Baseline Slope Comparison')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('../result/example_4_rt_relaxation.png', dpi=150)
    print("\n저장: result/example_4_rt_relaxation.png")
    plt.close()


if __name__ == '__main__':
    # 결과 디렉토리 생성
    result_dir = Path('../result')
    result_dir.mkdir(exist_ok=True)

    # exported_signals 디렉토리 확인
    signals_dir = Path('../exported_signals')
    if not signals_dir.exists() or len(list(signals_dir.glob('*.csv'))) == 0:
        print("ERROR: exported_signals 디렉토리에 CSV 파일이 없습니다!")
        sys.exit(1)

    print("\n" + "="*60)
    print("개선된 베이스라인 보정 예제 실행")
    print("="*60)

    try:
        example_1_basic_usage()
        example_2_manual_control()
        example_3_optimization()
        example_4_rt_relaxation()

        print("\n" + "="*60)
        print("모든 예제 실행 완료!")
        print("="*60)
        print(f"\n결과 위치: {result_dir.absolute()}/")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
