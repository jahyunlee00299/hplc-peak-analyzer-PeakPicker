"""
Test the improved baseline correction algorithm
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector


def test_baseline_improvements():
    """Test the improved baseline correction"""

    # Find recent CSV files to test
    result_dir = Path("result")
    if not result_dir.exists():
        print("No result directory found. Please run the workflow first.")
        return

    # Look for CSV files in recent result directories
    csv_files = []
    for subdir in result_dir.iterdir():
        if subdir.is_dir():
            csv_subdir = subdir / "csv"
            if csv_subdir.exists():
                csv_files.extend(list(csv_subdir.glob("*.csv"))[:5])  # Take up to 5 files

    if not csv_files:
        print("No CSV files found in result directory")
        return

    print(f"Testing baseline correction on {len(csv_files)} files")

    # Create figure for comparison
    n_files = min(3, len(csv_files))  # Show up to 3 examples
    fig, axes = plt.subplots(n_files, 2, figsize=(15, 5*n_files))
    if n_files == 1:
        axes = axes.reshape(1, -1)

    for idx, csv_file in enumerate(csv_files[:n_files]):
        print(f"\nProcessing: {csv_file.name}")

        # Load data
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity = df[1].values

        # OLD METHOD (percentile=10, less smoothing)
        corrector_old = HybridBaselineCorrector(time, intensity)
        corrector_old.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
        baseline_old = corrector_old.generate_hybrid_baseline(method='robust_fit', smooth_factor=0.5, enhanced_smoothing=False)
        corrected_old = intensity - baseline_old
        corrected_old = np.maximum(corrected_old, 0)

        # NEW METHOD (percentile=5, more smoothing, better constraints)
        corrector_new = HybridBaselineCorrector(time, intensity)
        corrector_new.find_baseline_anchor_points(valley_prominence=0.01, percentile=5)
        baseline_new = corrector_new.generate_hybrid_baseline(method='robust_fit', smooth_factor=0.5, enhanced_smoothing=True)
        corrected_new = intensity - baseline_new
        corrected_new = np.maximum(corrected_new, 0)

        # Plot OLD method
        ax1 = axes[idx, 0]
        ax1.plot(time, intensity, 'b-', alpha=0.6, label='Original Signal')
        ax1.plot(time, baseline_old, 'r-', linewidth=1, label='OLD Baseline')
        ax1.fill_between(time, baseline_old, intensity, where=(intensity >= baseline_old),
                         alpha=0.2, color='yellow', label='Area to Remove')

        # Highlight areas where baseline cuts into peaks
        problem_areas = (baseline_old > intensity * 0.95) & (intensity > np.percentile(intensity, 80))
        if np.any(problem_areas):
            ax1.scatter(time[problem_areas], intensity[problem_areas],
                       color='red', s=10, alpha=0.5, label='Baseline Too High')

        ax1.set_title(f'OLD Method - {csv_file.stem}')
        ax1.set_xlabel('Retention Time (min)')
        ax1.set_ylabel('Intensity')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # Plot NEW method
        ax2 = axes[idx, 1]
        ax2.plot(time, intensity, 'b-', alpha=0.6, label='Original Signal')
        ax2.plot(time, baseline_new, 'g-', linewidth=1, label='NEW Baseline')
        ax2.fill_between(time, baseline_new, intensity, where=(intensity >= baseline_new),
                         alpha=0.2, color='lightgreen', label='Area to Remove')

        # Check if new method still has issues (should be much less)
        problem_areas_new = (baseline_new > intensity * 0.95) & (intensity > np.percentile(intensity, 80))
        if np.any(problem_areas_new):
            ax2.scatter(time[problem_areas_new], intensity[problem_areas_new],
                       color='red', s=10, alpha=0.5, label='Baseline Too High')

        ax2.set_title(f'NEW Method (Improved) - {csv_file.stem}')
        ax2.set_xlabel('Retention Time (min)')
        ax2.set_ylabel('Intensity')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        # Print statistics
        print(f"  OLD Method:")
        print(f"    - Max baseline/signal ratio: {np.max(baseline_old/np.maximum(intensity, 1)):.2%}")
        print(f"    - Points where baseline > 95% signal: {np.sum(baseline_old > intensity * 0.95)}")
        print(f"  NEW Method:")
        print(f"    - Max baseline/signal ratio: {np.max(baseline_new/np.maximum(intensity, 1)):.2%}")
        print(f"    - Points where baseline > 95% signal: {np.sum(baseline_new > intensity * 0.95)}")

        # Calculate peak areas to show difference
        peaks, _ = signal.find_peaks(corrected_old, prominence=np.ptp(corrected_old)*0.01)
        if len(peaks) > 0:
            print(f"  Peak count OLD: {len(peaks)}")

        peaks_new, _ = signal.find_peaks(corrected_new, prominence=np.ptp(corrected_new)*0.01)
        if len(peaks_new) > 0:
            print(f"  Peak count NEW: {len(peaks_new)}")

    plt.suptitle('Baseline Correction Comparison: OLD vs NEW Method', fontsize=14, y=1.02)
    plt.tight_layout()

    # Save the figure
    output_file = Path("baseline_improvement_comparison.png")
    plt.savefig(output_file, dpi=100, bbox_inches='tight')
    print(f"\nComparison plot saved to: {output_file}")

    plt.show()

    print("\n" + "="*60)
    print("IMPROVEMENTS APPLIED:")
    print("="*60)
    print("1. Lower percentile for anchor points (10% -> 5%)")
    print("2. Increased smoothing factor (3x -> 5x)")
    print("3. More conservative local constraints (80% of local min)")
    print("4. Final constraint to keep baseline below 90% of signal")
    print("\nThese changes should prevent the baseline from cutting into peak bases.")


if __name__ == "__main__":
    test_baseline_improvements()