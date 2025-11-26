"""
Regenerate the baseline correction plot with the improved algorithm
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


def regenerate_plot():
    """Regenerate the baseline correction plot"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print(f"Regenerating baseline correction plot for: {csv_file.name}")

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

    # Create figure with better layout
    fig = plt.figure(figsize=(16, 10))

    # Create grid: 2 rows
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3)

    # ===== TOP PLOT: Baseline Correction =====
    ax1 = fig.add_subplot(gs[0])

    # Plot original signal
    ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.8)

    # Plot baseline
    ax1.plot(time, baseline, 'r-', linewidth=1.2, label='Baseline', alpha=0.9)

    # Fill area between baseline and signal
    ax1.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                      alpha=0.25, color='yellow', label='Area to Remove')

    # Add grid
    ax1.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

    # Add method info box
    info_text = f'Method: robust_fit\nBaseline Ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.2f}%'
    ax1.text(0.02, 0.95, info_text,
             transform=ax1.transAxes, fontsize=11, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.7))

    # Formatting
    ax1.set_title(f'250829_RIBA_PH_SP6_18H - Baseline Correction', fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('Intensity', fontsize=13)
    ax1.set_xlim(time[0], time[-1])

    # Set y-axis to show full range with some padding
    y_min = min(baseline.min(), intensity.min()) * 1.1 if baseline.min() < 0 else -500
    y_max = intensity.max() * 1.05
    ax1.set_ylim(y_min, y_max)

    # Legend
    ax1.legend(loc='upper right', fontsize=11, framealpha=0.9)

    # Remove top and right spines
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # ===== BOTTOM PLOT: Corrected Signal =====
    ax2 = fig.add_subplot(gs[1])

    # Plot corrected signal
    ax2.plot(time, corrected, 'g-', linewidth=1.5, label='Corrected Signal', alpha=0.9)

    # Fill under curve
    ax2.fill_between(time, 0, corrected, alpha=0.2, color='lightgreen')

    # Mark detected peaks with better visibility
    if len(peaks) > 0:
        ax2.scatter(time[peaks], corrected[peaks],
                   color='red', s=80, marker='^',
                   edgecolors='darkred', linewidths=1,
                   zorder=5, label=f'Detected Peaks ({len(peaks)})', alpha=0.9)

        # Add peak labels with RT values
        for i, peak in enumerate(peaks):
            ax2.annotate(f'RT: {time[peak]:.1f}',
                        xy=(time[peak], corrected[peak]),
                        xytext=(0, 10), textcoords='offset points',
                        fontsize=9, ha='center', color='darkred',
                        fontweight='bold')

    # Add grid
    ax2.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

    # Add horizontal line at y=0
    ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.8, alpha=0.5)

    # Formatting
    ax2.set_title(f'250829_RIBA_PH_SP6_18H - After Baseline Correction', fontsize=16, fontweight='bold', pad=20)
    ax2.set_xlabel('Retention Time (min)', fontsize=13)
    ax2.set_ylabel('Intensity', fontsize=13)
    ax2.set_xlim(time[0], time[-1])

    # Set y-axis to show full range with some padding
    y_max_corrected = corrected.max() * 1.05
    ax2.set_ylim(-500, y_max_corrected)

    # Legend
    ax2.legend(loc='upper right', fontsize=11, framealpha=0.9)

    # Remove top and right spines
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    # Overall figure adjustments
    plt.suptitle('HPLC Chromatogram Analysis - Improved Baseline Correction',
                 fontsize=18, fontweight='bold', y=0.98)

    # Adjust layout
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    # Save the figure with high quality
    output_file = Path("baseline_correction_regenerated.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f"\nHigh-quality plot saved to: {output_file}")

    # Also save as PDF for even better quality
    pdf_file = Path("baseline_correction_regenerated.pdf")
    plt.savefig(pdf_file, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f"PDF version saved to: {pdf_file}")

    # Print detailed statistics
    print("\n" + "="*60)
    print("BASELINE CORRECTION DETAILS")
    print("="*60)
    print(f"File: {csv_file.name}")
    print(f"\nPeak Detection Results:")
    print(f"  - Number of peaks: {len(peaks)}")
    if len(peaks) > 0:
        print(f"  - Peak retention times: {[f'{time[p]:.2f}' for p in peaks]}")
        print(f"  - Peak heights: {[f'{corrected[p]:.0f}' for p in peaks]}")

    print(f"\nBaseline Statistics:")
    print(f"  - Baseline area: {np.trapz(baseline, time):.2f}")
    print(f"  - Signal area: {np.trapz(intensity, time):.2f}")
    print(f"  - Baseline/Signal ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.2f}%")
    print(f"  - Min baseline value: {baseline.min():.2f}")
    print(f"  - Max baseline value: {baseline.max():.2f}")

    print(f"\nCorrected Signal Statistics:")
    print(f"  - Total corrected area: {np.trapz(corrected, time):.2f}")
    print(f"  - Max corrected intensity: {corrected.max():.2f}")
    print(f"  - Noise level estimate: {noise_level:.2f}")

    # Show the plot
    plt.show()


if __name__ == "__main__":
    regenerate_plot()