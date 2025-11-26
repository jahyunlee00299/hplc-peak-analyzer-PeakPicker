"""
Test baseline going below actual baseline
"""
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Load a sample file - try a few to find the issue
data_dir = Path("result/Revision 재실험")
csv_files = sorted(data_dir.glob("*.csv"))

# Test first 5 files
for i, csv_file in enumerate(csv_files[:10]):
    sample_name = csv_file.stem
    print(f"\n{'='*80}")
    print(f"Testing: {sample_name}")
    print(f"{'='*80}")

    try:
        # Load data
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity = df[1].values

        if np.min(intensity) < 0:
            intensity = intensity - np.min(intensity)

        # Apply baseline correction
        corrector = HybridBaselineCorrector(time, intensity)
        baseline, params = corrector.optimize_baseline_with_linear_peaks()

        # Check if baseline goes below signal
        # Find regions where baseline < intensity (should always be true)
        below_signal = baseline < intensity

        # But check if baseline goes below the "floor" of the signal
        # Calculate local minima in non-peak regions
        from scipy.signal import find_peaks

        # Find peaks
        peaks, _ = find_peaks(intensity, height=intensity.max() * 0.01, prominence=intensity.max() * 0.005)

        # Create mask for non-peak regions (more than 100 points away from any peak)
        non_peak_mask = np.ones(len(intensity), dtype=bool)
        for peak in peaks:
            start = max(0, peak - 100)
            end = min(len(intensity), peak + 100)
            non_peak_mask[start:end] = False

        if np.sum(non_peak_mask) > 0:
            # In non-peak regions, baseline should be close to signal
            non_peak_intensity = intensity[non_peak_mask]
            non_peak_baseline = baseline[non_peak_mask]

            # Calculate how much baseline is below signal in non-peak regions
            diff = non_peak_intensity - non_peak_baseline

            print(f"Non-peak regions:")
            print(f"  Signal range: {non_peak_intensity.min():.1f} - {non_peak_intensity.max():.1f}")
            print(f"  Baseline range: {non_peak_baseline.min():.1f} - {non_peak_baseline.max():.1f}")
            print(f"  Difference (signal - baseline):")
            print(f"    Mean: {diff.mean():.1f}")
            print(f"    Min: {diff.min():.1f}")
            print(f"    Max: {diff.max():.1f}")
            print(f"    Std: {diff.std():.1f}")

            # Check if baseline is significantly below signal floor
            if diff.mean() > 100:  # Baseline is more than 100 units below signal on average
                print(f"  WARNING: Baseline appears to be below actual baseline!")
                print(f"  Creating diagnostic plot...")

                # Create diagnostic plot
                fig, axes = plt.subplots(2, 1, figsize=(16, 10))

                # Full view
                ax = axes[0]
                ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
                ax.plot(time, baseline, 'r-', linewidth=1.5, label='Baseline', alpha=0.8)
                ax.plot(time[peaks], intensity[peaks], 'go', markersize=8, label='Detected Peaks')
                ax.set_xlabel('Time (min)')
                ax.set_ylabel('Intensity')
                ax.set_title(f'{sample_name} - Full View')
                ax.legend()
                ax.grid(True, alpha=0.3)

                # Zoomed to bottom (0-500 range)
                ax = axes[1]
                ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
                ax.plot(time, baseline, 'r-', linewidth=1.5, label='Baseline', alpha=0.8)
                ax.fill_between(time, baseline, intensity, where=(baseline < intensity),
                               alpha=0.3, color='yellow', label='Area to Remove')
                ax.set_xlabel('Time (min)')
                ax.set_ylabel('Intensity')
                ax.set_title(f'{sample_name} - Bottom View (zoomed)')
                ax.set_ylim(-500, 500)
                ax.legend()
                ax.grid(True, alpha=0.3)

                plt.tight_layout()
                plt.savefig(f'diagnostic_baseline_{sample_name}.png', dpi=150)
                print(f"  Saved: diagnostic_baseline_{sample_name}.png")
                plt.close()

                break  # Stop after finding first problematic case

    except Exception as e:
        print(f"Error processing {sample_name}: {e}")
        import traceback
        traceback.print_exc()
        continue

print(f"\n{'='*80}")
print("Diagnostic complete")
print(f"{'='*80}")
