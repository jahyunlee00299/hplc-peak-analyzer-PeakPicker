"""
Complete fix for baseline correction:
1. Fix negative offset in raw data
2. Apply proper baseline correction with anchor points at true valleys only
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import UnivariateSpline, interp1d
from scipy.integrate import trapezoid

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


def complete_baseline_correction():
    """Complete baseline correction with all fixes"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print("\n" + "="*80)
    print("COMPLETE BASELINE CORRECTION WITH ALL FIXES")
    print("="*80)
    print(f"Sample: {csv_file.stem}")

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity_raw = df[1].values

    print(f"\nRaw data statistics:")
    print(f"  Min intensity: {intensity_raw.min():.0f}")
    print(f"  Max intensity: {intensity_raw.max():.0f}")
    print(f"  Median intensity: {np.median(intensity_raw):.0f}")

    # Step 1: Fix negative offset
    # Shift data so that the baseline is around 0
    # Use the 10th percentile of non-peak regions as baseline estimate
    baseline_offset = np.percentile(intensity_raw, 10)
    print(f"\nBaseline offset detected: {baseline_offset:.0f}")

    # Shift data to remove offset
    intensity = intensity_raw - baseline_offset
    print(f"Data shifted by {-baseline_offset:.0f} to remove offset")

    print(f"\nCorrected data statistics:")
    print(f"  Min intensity: {intensity.min():.0f}")
    print(f"  Max intensity: {intensity.max():.0f}")
    print(f"  Median intensity: {np.median(intensity):.0f}")

    # Step 2: Find true valleys between peaks
    # Smooth the signal for peak/valley detection
    window = min(51, len(intensity) // 50)
    if window % 2 == 0:
        window += 1

    smoothed = signal.savgol_filter(intensity, window, 3)

    # Find peaks first
    peaks, peak_props = signal.find_peaks(
        smoothed,
        prominence=np.ptp(smoothed) * 0.01,
        distance=window * 2,
        height=np.percentile(smoothed, 75)  # Only significant peaks
    )

    print(f"\nFound {len(peaks)} peaks in smoothed signal")

    # Find valleys between peaks
    valleys = []

    # Add start point if it's low enough
    if intensity[0] < np.percentile(intensity[:100], 50):
        valleys.append(0)

    # Find valleys between consecutive peaks
    for i in range(len(peaks) - 1):
        left_peak = peaks[i]
        right_peak = peaks[i + 1]

        # Search for minimum between peaks
        segment = intensity[left_peak:right_peak]
        if len(segment) > 0:
            local_min_idx = left_peak + np.argmin(segment)
            valleys.append(local_min_idx)

    # Add end point if it's low enough
    if intensity[-1] < np.percentile(intensity[-100:], 50):
        valleys.append(len(intensity) - 1)

    valleys = np.array(valleys)
    print(f"Found {len(valleys)} valleys between peaks")

    # Step 3: Create baseline using only valley points
    anchor_indices = valleys
    anchor_values = intensity[valleys]

    # Add a few more points in flat regions if needed
    if len(anchor_indices) < 5:
        # Find flat regions (low gradient)
        gradient = np.abs(np.gradient(smoothed))
        flat_regions = gradient < np.percentile(gradient, 20)
        low_regions = intensity < np.percentile(intensity, 20)
        good_points = flat_regions & low_regions

        # Sample some points from good regions
        good_indices = np.where(good_points)[0]
        if len(good_indices) > 0:
            # Take evenly spaced points
            step = max(1, len(good_indices) // 5)
            extra_points = good_indices[::step][:5]

            # Combine with valleys
            anchor_indices = np.concatenate([anchor_indices, extra_points])
            anchor_values = intensity[anchor_indices]

            # Sort by index
            sort_idx = np.argsort(anchor_indices)
            anchor_indices = anchor_indices[sort_idx]
            anchor_values = anchor_values[sort_idx]

    print(f"Using {len(anchor_indices)} anchor points for baseline")

    # Create baseline with heavy smoothing
    baseline = np.zeros_like(intensity)

    if len(anchor_indices) >= 3:
        # Use very smooth spline
        # High smoothing factor to prevent overfitting
        s = len(anchor_indices) * 100.0
        try:
            # Ensure anchor values don't go above nearby intensity
            for i in range(len(anchor_values)):
                idx = anchor_indices[i]
                # Look at nearby region
                start = max(0, idx - 50)
                end = min(len(intensity), idx + 50)
                local_min = np.min(intensity[start:end])
                anchor_values[i] = min(anchor_values[i], local_min)

            spl = UnivariateSpline(anchor_indices, anchor_values, s=s, k=min(3, len(anchor_indices)-1))
            baseline = spl(np.arange(len(intensity)))
        except:
            # Fallback to linear interpolation
            f = interp1d(anchor_indices, anchor_values, kind='linear', fill_value='extrapolate')
            baseline = f(np.arange(len(intensity)))
    else:
        # Simple linear interpolation
        f = interp1d(anchor_indices, anchor_values, kind='linear', fill_value='extrapolate')
        baseline = f(np.arange(len(intensity)))

    # Step 4: Apply constraints to keep baseline low
    # Baseline should never exceed intensity
    baseline = np.minimum(baseline, intensity)

    # In peak regions, push baseline even lower
    for peak_idx in peaks:
        # Define peak region
        peak_height = intensity[peak_idx]
        threshold = peak_height * 0.1  # 10% of peak height

        # Find boundaries
        left = peak_idx
        while left > 0 and intensity[left] > threshold:
            left -= 1
        left = max(0, left - 20)  # Extend a bit

        right = peak_idx
        while right < len(intensity) - 1 and intensity[right] > threshold:
            right += 1
        right = min(len(intensity) - 1, right + 20)  # Extend a bit

        # In peak region, set baseline to minimum of surroundings
        if right > left:
            boundary_min = min(intensity[left], intensity[right])
            baseline[left:right] = np.minimum(baseline[left:right], boundary_min)

    # Smooth the baseline
    if len(baseline) > 101:
        baseline = signal.savgol_filter(baseline, 101, 3)

    # Final constraint: baseline should be mostly at or below zero (after shift)
    baseline = np.minimum(baseline, 0)

    # Step 5: Calculate corrected signal
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)  # No negative peaks

    # Detect peaks in corrected signal
    peaks_final, properties = signal.find_peaks(
        corrected,
        prominence=np.ptp(corrected) * 0.005,
        height=np.percentile(corrected[corrected > 0], 50),
        width=3
    )

    # Calculate peak areas
    peak_info = []
    for i, peak_idx in enumerate(peaks_final):
        # Find peak boundaries
        peak_height = corrected[peak_idx]
        half_height = peak_height / 2

        left_idx = peak_idx
        while left_idx > 0 and corrected[left_idx] > half_height:
            left_idx -= 1

        right_idx = peak_idx
        while right_idx < len(corrected) - 1 and corrected[right_idx] > half_height:
            right_idx += 1

        # Calculate area
        if right_idx > left_idx:
            peak_time = time[left_idx:right_idx+1]
            peak_signal = corrected[left_idx:right_idx+1]
            area = trapezoid(peak_signal, peak_time)

            peak_info.append({
                'Peak': i + 1,
                'RT': time[peak_idx],
                'Height': corrected[peak_idx],
                'Area': area
            })

    # Create comprehensive visualization
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1], hspace=0.3, wspace=0.25)

    # Plot 1: Raw data with offset
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(time, intensity_raw, 'b-', linewidth=1, alpha=0.8)
    ax1.axhline(y=baseline_offset, color='r', linestyle='--', alpha=0.5,
                label=f'Offset: {baseline_offset:.0f}')
    ax1.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax1.set_title('1. Raw Data (with negative offset)', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Time (min)')
    ax1.set_ylabel('Raw Intensity')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Shifted data
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(time, intensity, 'b-', linewidth=1, alpha=0.8)
    ax2.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax2.set_title('2. Shifted Data (offset removed)', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Time (min)')
    ax2.set_ylabel('Shifted Intensity')
    ax2.grid(True, alpha=0.3)

    # Plot 3: Anchor points selection
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(time, intensity, 'b-', linewidth=1, alpha=0.6, label='Signal')

    # Mark peaks
    if len(peaks) > 0:
        ax3.scatter(time[peaks], intensity[peaks], c='red', s=50, marker='^',
                   zorder=5, label='Peaks', alpha=0.8)

    # Mark valleys (anchor points)
    ax3.scatter(time[anchor_indices], anchor_values, c='green', s=50, marker='v',
               zorder=5, label='Valleys (anchors)', edgecolors='black', linewidths=0.5)

    ax3.set_title('3. Anchor Points (valleys only)', fontsize=12, fontweight='bold')
    ax3.set_xlabel('Time (min)')
    ax3.set_ylabel('Intensity')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Plot 4: Baseline correction
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.8, label='Signal')
    ax4.plot(time, baseline, 'r-', linewidth=1.2, label='Baseline', alpha=0.9)
    ax4.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                     alpha=0.25, color='yellow', label='Area to Remove')
    ax4.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax4.set_title('4. Final Baseline Correction', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Time (min)')
    ax4.set_ylabel('Intensity')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # Plot 5: Corrected signal
    ax5 = fig.add_subplot(gs[2, :])
    ax5.plot(time, corrected, 'g-', linewidth=1.5, alpha=0.9)
    ax5.fill_between(time, 0, corrected, alpha=0.2, color='lightgreen')

    if len(peaks_final) > 0:
        ax5.scatter(time[peaks_final], corrected[peaks_final],
                   color='red', s=80, marker='^',
                   edgecolors='darkred', linewidths=1,
                   zorder=5, label=f'{len(peaks_final)} Peaks')

        # Add peak labels
        for i, peak in enumerate(peaks_final):
            ax5.annotate(f'{i+1}\nRT: {time[peak]:.1f}',
                        xy=(time[peak], corrected[peak]),
                        xytext=(0, 10), textcoords='offset points',
                        fontsize=9, ha='center', color='darkred')

    ax5.set_title('5. Final Corrected Signal', fontsize=12, fontweight='bold')
    ax5.set_xlabel('Retention Time (min)')
    ax5.set_ylabel('Corrected Intensity')
    ax5.legend()
    ax5.grid(True, alpha=0.3)

    plt.suptitle('Complete Baseline Correction Process', fontsize=16, fontweight='bold')
    plt.tight_layout()

    # Save figure
    output_file = Path("complete_baseline_fix.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: {output_file}")

    # Print results
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(f"Peaks detected: {len(peaks_final)}")

    if len(peak_info) > 0:
        print("\nPeak Information:")
        print(f"{'Peak':<6} {'RT (min)':<10} {'Height':<12} {'Area':<12}")
        print("-" * 40)
        for p in peak_info:
            print(f"{p['Peak']:<6} {p['RT']:<10.2f} {p['Height']:<12.0f} {p['Area']:<12.0f}")

    print("\n" + "="*80)
    print("CORRECTIONS APPLIED:")
    print("="*80)
    print("1. Removed negative offset from raw data")
    print("2. Anchor points placed only at true valleys")
    print("3. Heavy smoothing to prevent baseline from climbing peaks")
    print("4. Baseline constrained to stay below signal")
    print("5. Additional lowering in peak regions")

    plt.show()


if __name__ == "__main__":
    complete_baseline_correction()