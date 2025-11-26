"""
Test the improved baseline correction on the specific file from the user's image
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


def test_specific_file():
    """Test on the specific file the user showed"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print(f"Testing baseline correction on: {csv_file.name}")

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # Create corrector with IMPROVED parameters
    corrector = HybridBaselineCorrector(time, intensity)

    # Use lower percentile (5 instead of 10) for better valley detection
    corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=5)

    # Generate baseline with enhanced smoothing
    baseline = corrector.generate_hybrid_baseline(method='robust_fit', smooth_factor=0.5, enhanced_smoothing=True)

    # Calculate corrected signal
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)

    # Detect peaks
    noise_level = np.percentile(corrected[corrected > 0], 25) * 1.5
    peaks, properties = signal.find_peaks(
        corrected,
        prominence=np.ptp(corrected) * 0.005,
        height=noise_level * 3,
        width=0
    )

    # Create visualization similar to user's image
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [1, 1]})

    # Top plot: Baseline correction visualization
    ax1.plot(time, intensity, 'b-', linewidth=1, label='Original Signal', alpha=0.8)
    ax1.plot(time, baseline, 'r-', linewidth=1, label='Baseline', alpha=0.8)
    ax1.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                      alpha=0.3, color='yellow', label='Area to Remove')

    # Add method info
    ax1.text(0.02, 0.98, f'Method: robust_fit\nBaseline Ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.2f}%',
             transform=ax1.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax1.set_title(f'{csv_file.stem} - Baseline Correction', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Intensity', fontsize=12)
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Bottom plot: Corrected signal
    ax2.plot(time, corrected, 'g-', linewidth=1, label='Corrected Signal')
    ax2.fill_between(time, 0, corrected, alpha=0.3, color='lightgreen')

    # Mark detected peaks
    if len(peaks) > 0:
        ax2.scatter(time[peaks], corrected[peaks], color='red', s=50, marker='^', zorder=5, label=f'{len(peaks)} peaks')

    ax2.set_title(f'{csv_file.stem} - After Baseline Correction', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Retention Time (min)', fontsize=12)
    ax2.set_ylabel('Intensity', fontsize=12)
    ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    ax2.legend(loc='upper right', fontsize=10)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save the figure
    output_file = Path(f"improved_baseline_{csv_file.stem}.png")
    plt.savefig(output_file, dpi=100, bbox_inches='tight')
    print(f"\nPlot saved to: {output_file}")

    # Print statistics
    print("\n" + "="*60)
    print("BASELINE CORRECTION STATISTICS")
    print("="*60)
    print(f"File: {csv_file.name}")
    print(f"Number of peaks detected: {len(peaks)}")
    print(f"Baseline area ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.2f}%")

    # Check how well baseline preserves peak bases
    if len(peaks) > 0:
        peak_base_ratios = []
        for peak in peaks:
            # Find peak boundaries (half-height method)
            peak_height = corrected[peak]
            half_height = peak_height / 2

            # Find left boundary
            left_idx = peak
            while left_idx > 0 and corrected[left_idx] > half_height:
                left_idx -= 1

            # Check baseline at left boundary
            if left_idx >= 0:
                baseline_at_left = baseline[left_idx]
                signal_at_left = intensity[left_idx]
                ratio = baseline_at_left / signal_at_left if signal_at_left > 0 else 0
                peak_base_ratios.append(ratio)

        avg_base_ratio = np.mean(peak_base_ratios)
        print(f"Average baseline/signal ratio at peak bases: {avg_base_ratio:.2%}")

        if avg_base_ratio > 0.9:
            print("WARNING: Baseline may still be cutting into peak bases")
        else:
            print("SUCCESS: Baseline is well below peak bases")

    print("\n" + "="*60)
    print("IMPROVEMENTS SUMMARY")
    print("="*60)
    print("✓ Lower percentile (5%) for better valley detection")
    print("✓ Enhanced smoothing (5x factor) for smoother baseline")
    print("✓ Local minimum constraint (80%) to protect peak bases")
    print("✓ Final constraint to keep baseline below 90% of signal")

    plt.show()


if __name__ == "__main__":
    test_specific_file()