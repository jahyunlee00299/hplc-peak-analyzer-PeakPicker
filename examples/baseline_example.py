"""
Improved baseline correction examples
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Add the project path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from improved_baseline import ImprovedBaselineCorrector, process_exported_signal


def example_1_basic_usage():
    """Example 1: basic usage"""
    print("=" * 60)
    print("Example 1: basic usage")
    print("=" * 60)

    # Use the convenience function
    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    time, intensity, baseline, params = process_exported_signal(
        str(csv_file),
        method='auto',
        use_linear_peaks=True
    )

    print(f"\nFile: {csv_file.name}")
    print(f"Method: {params['method']}")
    print(f"Anchor points: {params['num_anchors']}")
    print(f"Quality score: {params['score']:.2f}")

    # Corrected signal
    corrected = np.maximum(intensity - baseline, 0)

    # Simple visualization
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
    plt.savefig('../results/example_1_basic.png', dpi=150)
    print("\nSaved: results/example_1_basic.png")
    plt.close()


def example_2_manual_control():
    """Example 2: manual control"""
    print("\n" + "=" * 60)
    print("Example 2: manual control")
    print("=" * 60)

    import pandas as pd

    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # Create the corrector
    corrector = ImprovedBaselineCorrector(time, intensity)

    # Manually configure anchor points
    anchors = corrector.find_anchors(
        valley_prominence_factor=0.01,
        local_min_percentile=10,
        min_anchor_distance=15
    )

    print(f"\nAnchor points: {len(anchors)}")
    print("\nAnchor type distribution:")
    print(f"  Valley: {sum(1 for a in anchors if a.type == 'valley')}")
    print(f"  Local Min: {sum(1 for a in anchors if a.type == 'local_min')}")
    print(f"  Boundary: {sum(1 for a in anchors if a.type == 'boundary')}")

    # Generate baselines with all three methods
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

    # Show the anchor points
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
    plt.savefig('../results/example_2_manual.png', dpi=150)
    print("\nSaved: results/example_2_manual.png")
    plt.close()


def example_3_optimization():
    """Example 3: automatic optimization"""
    print("\n" + "=" * 60)
    print("Example 3: automatic optimization")
    print("=" * 60)

    import pandas as pd

    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    corrector = ImprovedBaselineCorrector(time, intensity)

    # Automatic optimization (try multiple methods)
    baseline, params = corrector.optimize_baseline(
        methods=['adaptive_spline', 'robust_spline'],
        use_linear_peaks=True
    )

    print(f"\nBest method: {params['method']}")
    print(f"Anchor points: {params['num_anchors']}")
    print(f"Quality score: {params['score']:.2f}")
    print(f"Linear peaks applied: {params['use_linear_peaks']}")

    corrected = np.maximum(intensity - baseline, 0)

    # Detailed visualization
    fig = plt.figure(figsize=(14, 10))

    # Original + baseline
    ax1 = plt.subplot(3, 1, 1)
    ax1.plot(time, intensity, 'b-', label='Original', alpha=0.7)
    ax1.plot(time, baseline, 'r--', linewidth=2, label='Baseline')
    ax1.fill_between(time, 0, baseline, alpha=0.2, color='red')
    ax1.set_xlabel('Time (min)')
    ax1.set_ylabel('Intensity')
    ax1.set_title(f'Optimized Baseline - {params["method"]}')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # After correction
    ax2 = plt.subplot(3, 1, 2)
    ax2.plot(time, corrected, 'g-', linewidth=1.5)
    ax2.fill_between(time, 0, corrected, alpha=0.3, color='green')
    ax2.set_xlabel('Time (min)')
    ax2.set_ylabel('Intensity')
    ax2.set_title('Corrected Signal')
    ax2.grid(True, alpha=0.3)

    # Baseline detail
    ax3 = plt.subplot(3, 1, 3)
    ax3.plot(time, baseline, 'r-', linewidth=2)

    # Show the anchor points
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
    plt.savefig('../results/example_3_optimization.png', dpi=150)
    print("\nSaved: results/example_3_optimization.png")
    plt.close()


def example_4_rt_relaxation():
    """Example 4: RT-based slope relaxation"""
    print("\n" + "=" * 60)
    print("Example 4: RT-based slope relaxation")
    print("=" * 60)

    import pandas as pd

    csv_file = Path('../exported_signals').glob('*.csv').__next__()

    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    corrector = ImprovedBaselineCorrector(time, intensity)
    corrector.find_anchors()

    # Without RT relaxation
    baseline_no_relax = corrector.generate_baseline(
        method='adaptive_spline',
        apply_rt_relaxation=False
    )

    # With RT relaxation applied
    baseline_with_relax = corrector.generate_baseline(
        method='adaptive_spline',
        apply_rt_relaxation=True
    )

    print(f"\nAnchor points: {len(corrector.anchors)}")

    # Compare slopes
    slope_no_relax = np.abs(np.diff(baseline_no_relax))
    slope_with_relax = np.abs(np.diff(baseline_with_relax))

    print(f"Max slope (no relaxation): {np.max(slope_no_relax):.2f}")
    print(f"Max slope (with relaxation): {np.max(slope_with_relax):.2f}")

    # Visualization
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
    plt.savefig('../results/example_4_rt_relaxation.png', dpi=150)
    print("\nSaved: results/example_4_rt_relaxation.png")
    plt.close()


if __name__ == '__main__':
    # Create the result directory
    result_dir = Path('../result')
    result_dir.mkdir(exist_ok=True)

    # Check the exported_signals directory
    signals_dir = Path('../exported_signals')
    if not signals_dir.exists() or len(list(signals_dir.glob('*.csv'))) == 0:
        print("ERROR: no CSV files found in the exported_signals directory!")
        sys.exit(1)

    print("\n" + "="*60)
    print("Running improved baseline correction examples")
    print("="*60)

    try:
        example_1_basic_usage()
        example_2_manual_control()
        example_3_optimization()
        example_4_rt_relaxation()

        print("\n" + "="*60)
        print("All examples completed!")
        print("="*60)
        print(f"\nResults location: {result_dir.absolute()}/")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
