"""
Example: Baseline Correction and Peak Splitting
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).parent.parent))

from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector
from modules.baseline_handler import BaselineHandler, PeakSplitter


def example_baseline_methods():
    """Example 1: Compare different baseline methods"""
    print("\n" + "="*60)
    print("Example 1: Baseline Methods Comparison")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent.parent / "examples" / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    print(f"✓ Loaded data: {len(time)} points")

    # Create handler
    handler = BaselineHandler(time, intensity)

    # Test different methods
    methods = {
        'Linear': lambda: handler.calculate_linear_baseline(),
        'Polynomial (deg=3)': lambda: handler.calculate_polynomial_baseline(degree=3),
        'ALS': lambda: handler.calculate_als_baseline(lam=1e6, p=0.01),
    }

    results = {}
    for name, method in methods.items():
        baseline = method()
        corrected = handler.apply_baseline_correction()

        results[name] = {
            'baseline': baseline.copy(),
            'corrected': corrected.copy()
        }

        print(f"\n{name}:")
        print(f"  Baseline range: {baseline.min():.2f} - {baseline.max():.2f}")
        print(f"  Corrected range: {corrected.min():.2f} - {corrected.max():.2f}")

    # Visualize
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Baseline Correction Methods Comparison', fontsize=16, fontweight='bold')

    # Original
    axes[0, 0].plot(time, intensity, 'b-', linewidth=1.5)
    axes[0, 0].set_title('Original Chromatogram')
    axes[0, 0].set_xlabel('Time (min)')
    axes[0, 0].set_ylabel('Intensity')
    axes[0, 0].grid(True, alpha=0.3)

    # Methods
    plot_idx = [(0, 1), (1, 0), (1, 1)]
    for (name, result), (i, j) in zip(results.items(), plot_idx):
        axes[i, j].plot(time, intensity, 'b-', alpha=0.3, label='Original')
        axes[i, j].plot(time, result['baseline'], 'r--', linewidth=2, label='Baseline')
        axes[i, j].plot(time, result['corrected'], 'g-', linewidth=1.5, label='Corrected')
        axes[i, j].set_title(name)
        axes[i, j].set_xlabel('Time (min)')
        axes[i, j].set_ylabel('Intensity')
        axes[i, j].legend()
        axes[i, j].grid(True, alpha=0.3)

    plt.tight_layout()

    output_file = Path(__file__).parent / "baseline_methods_comparison.png"
    plt.savefig(output_file, dpi=300)
    print(f"\n✓ Saved comparison to: {output_file}")


def example_manual_baseline():
    """Example 2: Manual baseline with anchor points"""
    print("\n" + "="*60)
    print("Example 2: Manual Baseline")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent.parent / "examples" / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    handler = BaselineHandler(time, intensity)

    # Define anchor points
    anchor_points = [
        (0.0, 12.5),
        (2.0, 200.0),
        (4.0, 100.0),
        (6.0, 271.5)
    ]

    print(f"✓ Using {len(anchor_points)} anchor points:")
    for i, (t, val) in enumerate(anchor_points, 1):
        print(f"  {i}. Time={t:.1f}, Intensity={val:.1f}")

    # Create manual baseline
    baseline = handler.manual_baseline(anchor_points)
    corrected = handler.apply_baseline_correction()

    print(f"\n✓ Manual baseline created")
    print(f"  Corrected range: {corrected.min():.2f} - {corrected.max():.2f}")

    # Visualize
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Original with anchor points
    ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Original')
    ax1.plot(time, baseline, 'r--', linewidth=2, label='Manual Baseline')

    # Plot anchor points
    anchor_times = [p[0] for p in anchor_points]
    anchor_vals = [p[1] for p in anchor_points]
    ax1.scatter(anchor_times, anchor_vals, c='red', s=100, zorder=5,  label='Anchor Points')

    ax1.set_title('Manual Baseline with Anchor Points')
    ax1.set_ylabel('Intensity')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Corrected
    ax2.plot(time, corrected, 'g-', linewidth=1.5)
    ax2.set_title('Baseline-Corrected Chromatogram')
    ax2.set_xlabel('Time (min)')
    ax2.set_ylabel('Intensity')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    output_file = Path(__file__).parent / "manual_baseline.png"
    plt.savefig(output_file, dpi=300)
    print(f"✓ Saved plot to: {output_file}")


def example_peak_splitting():
    """Example 3: Peak splitting"""
    print("\n" + "="*60)
    print("Example 3: Peak Splitting")
    print("="*60)

    # Create synthetic overlapping peaks
    time = np.linspace(0, 10, 500)
    peak1 = 100 * np.exp(-((time - 3) ** 2) / 0.3)
    peak2 = 80 * np.exp(-((time - 4) ** 2) / 0.3)
    intensity = peak1 + peak2 + 10

    print("✓ Created synthetic overlapping peaks")

    # Detect the overlapping peak
    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    print(f"✓ Detected {len(peaks)} peak(s)")

    if len(peaks) > 0:
        # Split the peak
        splitter = PeakSplitter(time, intensity)
        peak1_split, peak2_split = splitter.split_peak_at_minimum(peaks[0])

        print(f"\n✓ Peak split successful:")
        print(f"  Peak 1: RT={peak1_split.rt:.3f} min, Area={peak1_split.area:.2f}")
        print(f"  Peak 2: RT={peak2_split.rt:.3f} min, Area={peak2_split.area:.2f}")

        # Visualize
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # Before splitting
        axes[0].plot(time, intensity, 'b-', linewidth=1.5)
        axes[0].axvline(peaks[0].rt, color='r', linestyle='--', alpha=0.5, label='Peak RT')
        axes[0].set_title('Before Splitting (1 peak detected)')
        axes[0].set_ylabel('Intensity')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # After splitting
        axes[1].plot(time, intensity, 'b-', linewidth=1.5, alpha=0.3)

        # Highlight split peaks
        mask1 = (time >= peak1_split.rt_start) & (time <= peak1_split.rt_end)
        axes[1].fill_between(time[mask1], intensity[mask1], alpha=0.3, color='red', label='Peak 1')

        mask2 = (time >= peak2_split.rt_start) & (time <= peak2_split.rt_end)
        axes[1].fill_between(time[mask2], intensity[mask2], alpha=0.3, color='green', label='Peak 2')

        axes[1].axvline(peak1_split.rt, color='red', linestyle='--', alpha=0.5)
        axes[1].axvline(peak2_split.rt, color='green', linestyle='--', alpha=0.5)

        axes[1].set_title('After Splitting (2 peaks)')
        axes[1].set_xlabel('Time (min)')
        axes[1].set_ylabel('Intensity')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()

        output_file = Path(__file__).parent / "peak_splitting.png"
        plt.savefig(output_file, dpi=300)
        print(f"✓ Saved plot to: {output_file}")


def example_overlap_detection():
    """Example 4: Overlap detection"""
    print("\n" + "="*60)
    print("Example 4: Overlap Detection")
    print("="*60)

    # Create synthetic data with multiple overlapping peaks
    time = np.linspace(0, 10, 500)
    peak1 = 100 * np.exp(-((time - 3) ** 2) / 0.3)
    peak2 = 80 * np.exp(-((time - 3.5) ** 2) / 0.3)
    peak3 = 90 * np.exp(-((time - 7) ** 2) / 0.4)
    intensity = peak1 + peak2 + peak3 + 10

    print("✓ Created synthetic data with overlapping peaks")

    # Detect peaks
    detector = PeakDetector(time, intensity, prominence=20, min_height=15, auto_threshold=False)
    peaks = detector.detect_peaks()

    print(f"✓ Detected {len(peaks)} peaks")

    # Check for overlaps
    splitter = PeakSplitter(time, intensity)
    overlapping = splitter.detect_overlapping_peaks(peaks, overlap_threshold=0.3)

    print(f"✓ Found {len(overlapping)} overlapping peak pair(s):")
    for peak1_idx, peak2_idx in overlapping:
        print(f"  - Peak {peak1_idx+1} (RT={peaks[peak1_idx].rt:.3f}) overlaps with Peak {peak2_idx+1} (RT={peaks[peak2_idx].rt:.3f})")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("BASELINE CORRECTION AND PEAK SPLITTING EXAMPLES")
    print("="*70)

    example_baseline_methods()
    example_manual_baseline()
    example_peak_splitting()
    example_overlap_detection()

    print("\n" + "="*70)
    print("All examples completed!")
    print("="*70)


if __name__ == "__main__":
    main()
