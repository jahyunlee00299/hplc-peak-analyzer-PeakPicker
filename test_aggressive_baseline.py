"""
Test more aggressive baseline correction to avoid cutting peak bases
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.ndimage import minimum_filter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector


def apply_peak_protection(time, intensity, baseline):
    """
    Apply additional peak protection by lowering baseline near peaks
    """
    protected_baseline = baseline.copy()

    # Find potential peak regions (where intensity is significantly above local minimum)
    window_size = 51
    local_min = minimum_filter(intensity, size=window_size, mode='nearest')

    # Identify peak regions: where signal is 2x above local minimum
    peak_regions = intensity > (local_min * 2)

    # Extend peak regions to include shoulders
    from scipy.ndimage import binary_dilation
    structure = np.ones(101)  # Extend by ~0.5 minutes on each side
    extended_peak_regions = binary_dilation(peak_regions, structure=structure)

    # In peak regions, set baseline to minimum of local minimum or current baseline
    protected_baseline[extended_peak_regions] = np.minimum(
        protected_baseline[extended_peak_regions],
        local_min[extended_peak_regions] * 0.3  # Use only 30% of local minimum
    )

    return protected_baseline


def test_aggressive_baseline():
    """Test aggressive baseline correction"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print(f"Testing AGGRESSIVE baseline correction on: {csv_file.name}")

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # Create corrector with MORE AGGRESSIVE parameters
    corrector = HybridBaselineCorrector(time, intensity)

    # Use very low percentile (2 instead of 5) for lower valley detection
    corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=2)

    # Generate baseline with maximum smoothing
    baseline = corrector.generate_hybrid_baseline(method='robust_fit', smooth_factor=1.0, enhanced_smoothing=True)

    # Apply additional peak protection
    baseline = apply_peak_protection(time, intensity, baseline)

    # Further lower the baseline in peak regions
    # Find peaks first
    temp_corrected = np.maximum(intensity - baseline, 0)
    peaks_prelim, _ = signal.find_peaks(temp_corrected, prominence=np.ptp(temp_corrected)*0.001)

    # For each peak, ensure baseline is low enough
    for peak_idx in peaks_prelim:
        # Find peak boundaries
        peak_height = intensity[peak_idx] - baseline[peak_idx]
        half_height = baseline[peak_idx] + peak_height / 2

        # Find left boundary
        left_idx = peak_idx
        while left_idx > 0 and intensity[left_idx] > half_height * 0.5:  # Use 50% of half height for wider range
            left_idx -= 1
        left_idx = max(0, left_idx - 50)  # Extend further left

        # Find right boundary
        right_idx = peak_idx
        while right_idx < len(intensity) - 1 and intensity[right_idx] > half_height * 0.5:
            right_idx += 1
        right_idx = min(len(intensity) - 1, right_idx + 50)  # Extend further right

        # Set baseline to minimum value in this region
        if right_idx > left_idx:
            min_baseline_in_region = np.min(baseline[left_idx:right_idx+1])
            # Make it even lower
            flat_value = min(min_baseline_in_region, intensity[left_idx] * 0.1, intensity[right_idx] * 0.1)
            baseline[left_idx:right_idx+1] = flat_value

    # Final safety: ensure baseline is never above 50% of signal
    baseline = np.minimum(baseline, intensity * 0.5)

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

    # Create visualization
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3)

    # ===== TOP PLOT: Baseline Correction =====
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.8)
    ax1.plot(time, baseline, 'r-', linewidth=1.2, label='Baseline (Aggressive)', alpha=0.9)
    ax1.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                      alpha=0.25, color='yellow', label='Area to Remove')
    ax1.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

    # Add method info
    info_text = f'Method: Aggressive robust_fit\nBaseline Ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.2f}%'
    ax1.text(0.02, 0.95, info_text,
             transform=ax1.transAxes, fontsize=11, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))

    ax1.set_title(f'250829_RIBA_PH_SP6_18H - AGGRESSIVE Baseline Correction', fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('Intensity', fontsize=13)
    ax1.set_xlim(time[0], time[-1])
    ax1.legend(loc='upper right', fontsize=11, framealpha=0.9)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # ===== BOTTOM PLOT: Corrected Signal =====
    ax2 = fig.add_subplot(gs[1])
    ax2.plot(time, corrected, 'g-', linewidth=1.5, label='Corrected Signal', alpha=0.9)
    ax2.fill_between(time, 0, corrected, alpha=0.2, color='lightgreen')

    if len(peaks) > 0:
        ax2.scatter(time[peaks], corrected[peaks],
                   color='red', s=80, marker='^',
                   edgecolors='darkred', linewidths=1,
                   zorder=5, label=f'Detected Peaks ({len(peaks)})', alpha=0.9)

        for i, peak in enumerate(peaks):
            ax2.annotate(f'RT: {time[peak]:.1f}',
                        xy=(time[peak], corrected[peak]),
                        xytext=(0, 10), textcoords='offset points',
                        fontsize=9, ha='center', color='darkred',
                        fontweight='bold')

    ax2.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.8, alpha=0.5)
    ax2.set_title(f'250829_RIBA_PH_SP6_18H - After AGGRESSIVE Baseline Correction', fontsize=16, fontweight='bold', pad=20)
    ax2.set_xlabel('Retention Time (min)', fontsize=13)
    ax2.set_ylabel('Intensity', fontsize=13)
    ax2.set_xlim(time[0], time[-1])
    ax2.legend(loc='upper right', fontsize=11, framealpha=0.9)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.suptitle('HPLC Analysis - AGGRESSIVE Baseline Correction (Peak Protection Enhanced)',
                 fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    # Save the figure
    output_file = Path("aggressive_baseline_correction.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f"\nPlot saved to: {output_file}")

    # Print statistics
    print("\n" + "="*60)
    print("AGGRESSIVE BASELINE CORRECTION RESULTS")
    print("="*60)
    print(f"File: {csv_file.name}")
    print(f"\nPeak Detection:")
    print(f"  - Number of peaks: {len(peaks)}")
    if len(peaks) > 0:
        print(f"  - Peak RTs: {[f'{time[p]:.2f}' for p in peaks]}")

    print(f"\nBaseline Statistics:")
    print(f"  - Baseline/Signal ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.2f}%")
    print(f"  - Min baseline: {baseline.min():.2f}")
    print(f"  - Max baseline: {baseline.max():.2f}")

    # Check baseline at peak bases
    if len(peaks) > 0:
        print(f"\nPeak Base Analysis:")
        for i, peak in enumerate(peaks[:5]):  # Check first 5 peaks
            peak_val = intensity[peak]
            baseline_at_peak = baseline[peak]
            ratio = baseline_at_peak / peak_val if peak_val > 0 else 0
            print(f"  Peak at RT {time[peak]:.1f}: baseline/signal = {ratio:.1%}")

    print("\n" + "="*60)
    print("AGGRESSIVE CORRECTIONS APPLIED:")
    print("="*60)
    print("1. Very low percentile (2%) for anchor points")
    print("2. Maximum smoothing factor")
    print("3. Peak region protection (30% of local minimum)")
    print("4. Extended peak boundaries with flat baseline")
    print("5. Final constraint: baseline < 50% of signal")

    plt.show()


if __name__ == "__main__":
    test_aggressive_baseline()