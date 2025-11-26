"""
Test improved y-axis break to ensure no peaks are cut
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


def improved_break_detection(intensity):
    """
    Improved break detection that ensures NO peak is cut
    Returns (break_start, break_end) or (None, None)
    """
    # Find peaks
    peaks, properties = signal.find_peaks(
        intensity,
        height=intensity.max() * 0.01,
        prominence=intensity.max() * 0.005
    )

    if len(peaks) == 0:
        return None, None

    peak_heights = intensity[peaks]
    sorted_heights = np.sort(peak_heights)[::-1]  # Descending order

    if len(sorted_heights) <= 1:
        return None, None

    # Look for the biggest gap in peak heights
    gaps = sorted_heights[:-1] - sorted_heights[1:]

    if len(gaps) == 0 or gaps.max() <= sorted_heights[0] * 0.3:
        # No significant gap
        return None, None

    gap_idx = np.argmax(gaps)

    # IMPROVED: Ensure break does NOT include ANY peak
    smaller_peaks = sorted_heights[gap_idx + 1:]
    taller_peaks = sorted_heights[:gap_idx + 1]

    # Set break_start above the tallest of smaller peaks
    break_start = np.max(smaller_peaks) * 1.1  # 10% margin above

    # Set break_end below the shortest of taller peaks
    break_end = np.min(taller_peaks) * 0.9  # 10% margin below

    # Ensure there's actually a gap
    if break_start >= break_end:
        return None, None

    return break_start, break_end


def test_break_on_sample():
    """Test improved break detection on a sample"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print("\n" + "="*80)
    print("TESTING IMPROVED Y-AXIS BREAK")
    print("="*80)
    print(f"Sample: {csv_file.stem}")

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity_raw = df[1].values

    # Apply baseline correction
    baseline_offset = np.percentile(intensity_raw, 10)
    intensity = intensity_raw - baseline_offset

    corrector = HybridBaselineCorrector(time, intensity)
    corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=2)
    baseline = corrector.generate_hybrid_baseline(method='robust_fit', enhanced_smoothing=True)

    # Find peaks
    peaks, properties = signal.find_peaks(
        intensity,
        height=intensity.max() * 0.01,
        prominence=intensity.max() * 0.005
    )

    peak_heights = intensity[peaks]

    print(f"\nPeak detection:")
    print(f"  Total peaks: {len(peaks)}")
    if len(peaks) > 0:
        sorted_peaks = np.sort(peak_heights)[::-1]
        print(f"  Peak heights (sorted):")
        for i, h in enumerate(sorted_peaks):
            print(f"    Peak {i+1}: {h:.0f}")

    # Calculate break with improved method
    break_start, break_end = improved_break_detection(intensity)

    if break_start is not None and break_end is not None:
        print(f"\nBreak region:")
        print(f"  Break start: {break_start:.0f}")
        print(f"  Break end: {break_end:.0f}")
        print(f"  Break gap: {break_end - break_start:.0f}")

        # Verify NO peak is in break region
        peaks_in_break = []
        for i, peak_h in enumerate(peak_heights):
            if break_start <= peak_h <= break_end:
                peaks_in_break.append((i+1, peak_h))

        if len(peaks_in_break) > 0:
            print(f"\n  WARNING: {len(peaks_in_break)} peaks in break region!")
            for peak_num, peak_h in peaks_in_break:
                print(f"    Peak {peak_num}: {peak_h:.0f}")
        else:
            print(f"\n  SUCCESS: NO peaks in break region!")

        # Show which peaks are below/above break
        below_break = sum(1 for h in peak_heights if h < break_start)
        above_break = sum(1 for h in peak_heights if h > break_end)
        print(f"\n  Peaks below break: {below_break}")
        print(f"  Peaks above break: {above_break}")
    else:
        print(f"\nNo break needed (no significant gap or too few peaks)")

    # Create visualization
    fig = plt.figure(figsize=(16, 10))

    if break_start is not None and break_end is not None:
        # With break
        gs = fig.add_gridspec(3, 1, height_ratios=[2, 1, 1.5], hspace=0.15)

        ax1_top = fig.add_subplot(gs[0])
        ax1_bottom = fig.add_subplot(gs[1])

        # Plot on both axes
        for ax in [ax1_top, ax1_bottom]:
            ax.plot(time, intensity, 'b-', linewidth=1.5, label='Signal', alpha=0.7)
            ax.plot(time, baseline, 'r-', linewidth=1, label='Baseline', alpha=0.8)
            ax.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                           alpha=0.2, color='yellow')

            # Mark all peaks
            ax.scatter(time[peaks], intensity[peaks], c='red', s=60, marker='^',
                      zorder=5, edgecolors='darkred', linewidths=1)

            # Add peak numbers
            for i, peak in enumerate(peaks):
                ax.annotate(f'{i+1}', xy=(time[peak], intensity[peak]),
                           xytext=(0, 5), textcoords='offset points',
                           fontsize=9, ha='center', fontweight='bold', color='darkred')

            ax.grid(True, alpha=0.3)

        # Set different y-limits for top and bottom
        ax1_top.set_ylim(break_end, intensity.max() * 1.05)
        ax1_bottom.set_ylim(intensity.min(), break_start)

        # Highlight break region
        ax1_top.axhline(y=break_end, color='orange', linestyle='--', linewidth=2, alpha=0.7)
        ax1_bottom.axhline(y=break_start, color='orange', linestyle='--', linewidth=2, alpha=0.7)

        # Add break region annotation
        ax1_top.text(0.5, 0.02, f'Break region: {break_start:.0f} - {break_end:.0f}',
                    transform=ax1_top.transAxes, ha='center',
                    bbox=dict(boxstyle='round', facecolor='orange', alpha=0.5),
                    fontsize=10)

        # Hide x-axis on top plot
        ax1_top.set_xticklabels([])
        ax1_top.tick_params(axis='x', which='both', bottom=False, top=False)
        ax1_top.spines['bottom'].set_visible(False)

        # Hide top border of bottom plot
        ax1_bottom.spines['top'].set_visible(False)
        ax1_bottom.tick_params(axis='x', which='both', top=False)

        ax1_bottom.set_xlabel('Retention Time (min)', fontsize=12)
        ax1_top.set_ylabel('Intensity', fontsize=12)
        ax1_bottom.set_ylabel('Intensity', fontsize=12)

        ax1_top.set_title(f'{csv_file.stem} - Improved Y-Axis Break (NO peaks cut)',
                         fontsize=14, fontweight='bold')
        ax1_top.legend(fontsize=10, loc='upper right')

        # Add break marks
        d = 0.015
        kwargs = dict(transform=ax1_top.transAxes, color='k', clip_on=False, linewidth=1)
        ax1_top.plot((-d, +d), (-d, +d), **kwargs)
        ax1_top.plot((1 - d, 1 + d), (-d, +d), **kwargs)

        kwargs.update(transform=ax1_bottom.transAxes)
        ax1_bottom.plot((-d, +d), (1 - d, 1 + d), **kwargs)
        ax1_bottom.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)

        # Bottom plot: corrected signal
        ax2 = fig.add_subplot(gs[2])
    else:
        # Without break
        gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3)

        ax1 = fig.add_subplot(gs[0])
        ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Signal', alpha=0.7)
        ax1.plot(time, baseline, 'r-', linewidth=1, label='Baseline', alpha=0.8)
        ax1.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                        alpha=0.2, color='yellow')

        # Mark all peaks
        ax1.scatter(time[peaks], intensity[peaks], c='red', s=60, marker='^',
                   zorder=5, edgecolors='darkred', linewidths=1)

        for i, peak in enumerate(peaks):
            ax1.annotate(f'{i+1}', xy=(time[peak], intensity[peak]),
                        xytext=(0, 5), textcoords='offset points',
                        fontsize=9, ha='center', fontweight='bold', color='darkred')

        ax1.set_title(f'{csv_file.stem} - No Break Needed', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Retention Time (min)', fontsize=12)
        ax1.set_ylabel('Intensity', fontsize=12)
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)

        ax2 = fig.add_subplot(gs[1])

    # Corrected signal (common for both cases)
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)

    ax2.plot(time, corrected, 'g-', linewidth=1.5, alpha=0.9)
    ax2.fill_between(time, 0, corrected, alpha=0.2, color='lightgreen')

    peaks_final, _ = signal.find_peaks(corrected, prominence=np.ptp(corrected)*0.005, height=np.percentile(corrected[corrected>0], 50))

    if len(peaks_final) > 0:
        ax2.scatter(time[peaks_final], corrected[peaks_final],
                   color='red', s=60, marker='^', zorder=5)

    ax2.set_title('Corrected Signal', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Retention Time (min)', fontsize=12)
    ax2.set_ylabel('Corrected Intensity', fontsize=12)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save figure
    output_file = Path("test_improved_break.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nVisualization saved to: {output_file}")

    plt.show()


if __name__ == "__main__":
    test_break_on_sample()