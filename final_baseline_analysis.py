"""
Final analysis with improved baseline correction
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.integrate import trapezoid

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector


def analyze_with_improved_baseline():
    """Complete analysis with improved baseline correction"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print("\n" + "="*80)
    print("FINAL BASELINE CORRECTION ANALYSIS")
    print("="*80)
    print(f"Sample: {csv_file.stem}")

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # Apply IMPROVED baseline correction
    print("\nApplying improved baseline correction...")
    corrector = HybridBaselineCorrector(time, intensity)

    # Use optimized parameters
    corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=2)
    baseline = corrector.generate_hybrid_baseline(method='robust_fit', enhanced_smoothing=True)

    # Calculate corrected signal
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)

    # Peak detection with optimized parameters
    noise_level = np.percentile(corrected[corrected > 0], 25) * 1.5
    peaks, properties = signal.find_peaks(
        corrected,
        prominence=np.ptp(corrected) * 0.005,
        height=noise_level * 3,
        width=3  # Minimum width
    )

    # Calculate peak areas
    peak_areas = []
    peak_info = []

    for i, peak_idx in enumerate(peaks):
        # Find peak boundaries using half-height method
        peak_height = corrected[peak_idx]
        half_height = peak_height / 2

        # Find left boundary
        left_idx = peak_idx
        while left_idx > 0 and corrected[left_idx] > half_height:
            left_idx -= 1

        # Find right boundary
        right_idx = peak_idx
        while right_idx < len(corrected) - 1 and corrected[right_idx] > half_height:
            right_idx += 1

        # Calculate area
        if right_idx > left_idx:
            peak_time = time[left_idx:right_idx+1]
            peak_signal = corrected[left_idx:right_idx+1]
            area = trapezoid(peak_signal, peak_time)
            peak_areas.append(area)

            # Store peak information
            peak_info.append({
                'Peak': i + 1,
                'RT (min)': time[peak_idx],
                'Height': corrected[peak_idx],
                'Area': area,
                'Width (min)': time[right_idx] - time[left_idx],
                'Start RT': time[left_idx],
                'End RT': time[right_idx]
            })

    # Create comprehensive visualization
    fig = plt.figure(figsize=(18, 12))

    # Create grid: 2x2 layout
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.8], width_ratios=[1, 1], hspace=0.3, wspace=0.25)

    # ===== TOP LEFT: Original vs Baseline =====
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.8)
    ax1.plot(time, baseline, 'r-', linewidth=1.2, label='Baseline', alpha=0.9)
    ax1.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                      alpha=0.25, color='yellow', label='Area to Remove')

    # Mark anchor points
    anchor_indices = [p.index for p in corrector.baseline_points]
    anchor_values = [p.value for p in corrector.baseline_points]
    ax1.scatter(time[anchor_indices], anchor_values, c='red', s=30, zorder=5,
                marker='o', edgecolors='black', linewidths=0.5, alpha=0.8, label='Anchor Points')

    ax1.set_title('Baseline Correction', fontsize=13, fontweight='bold')
    ax1.set_xlabel('Retention Time (min)')
    ax1.set_ylabel('Intensity')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # ===== TOP RIGHT: Corrected Signal with Peaks =====
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(time, corrected, 'g-', linewidth=1.5, alpha=0.9)
    ax2.fill_between(time, 0, corrected, alpha=0.2, color='lightgreen')

    # Mark peaks
    if len(peaks) > 0:
        ax2.scatter(time[peaks], corrected[peaks], color='red', s=60, marker='^',
                   edgecolors='darkred', linewidths=1, zorder=5)

        # Add peak numbers
        for i, peak in enumerate(peaks):
            ax2.annotate(f'{i+1}', xy=(time[peak], corrected[peak]),
                        xytext=(0, 5), textcoords='offset points',
                        fontsize=9, ha='center', fontweight='bold', color='darkred')

    ax2.set_title('Peak Detection', fontsize=13, fontweight='bold')
    ax2.set_xlabel('Retention Time (min)')
    ax2.set_ylabel('Corrected Intensity')
    ax2.grid(True, alpha=0.3)

    # ===== BOTTOM LEFT: Zoom on major peaks =====
    ax3 = fig.add_subplot(gs[1, 0])

    # Find the region with most peaks (usually 8-15 min)
    zoom_start = 6
    zoom_end = 15
    zoom_mask = (time >= zoom_start) & (time <= zoom_end)

    ax3.plot(time[zoom_mask], corrected[zoom_mask], 'g-', linewidth=1.5, alpha=0.9)
    ax3.fill_between(time[zoom_mask], 0, corrected[zoom_mask], alpha=0.2, color='lightgreen')

    # Mark peaks in zoom region
    peaks_in_zoom = peaks[(time[peaks] >= zoom_start) & (time[peaks] <= zoom_end)]
    if len(peaks_in_zoom) > 0:
        ax3.scatter(time[peaks_in_zoom], corrected[peaks_in_zoom],
                   color='red', s=60, marker='^', edgecolors='darkred', linewidths=1, zorder=5)

        # Add detailed labels
        for peak in peaks_in_zoom:
            peak_num = np.where(peaks == peak)[0][0] + 1
            ax3.annotate(f'Peak {peak_num}\nRT: {time[peak]:.2f}\nH: {corrected[peak]:.0f}',
                        xy=(time[peak], corrected[peak]),
                        xytext=(10, 10), textcoords='offset points',
                        fontsize=8, bbox=dict(boxstyle='round,pad=0.3',
                        facecolor='yellow', alpha=0.6),
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    ax3.set_title(f'Zoomed View ({zoom_start}-{zoom_end} min)', fontsize=13, fontweight='bold')
    ax3.set_xlabel('Retention Time (min)')
    ax3.set_ylabel('Corrected Intensity')
    ax3.grid(True, alpha=0.3)

    # ===== BOTTOM RIGHT: Peak Area Visualization =====
    ax4 = fig.add_subplot(gs[1, 1])

    # Show peak areas as bars
    if len(peak_info) > 0:
        peak_numbers = [p['Peak'] for p in peak_info]
        peak_areas_list = [p['Area'] for p in peak_info]
        peak_rts = [p['RT (min)'] for p in peak_info]

        bars = ax4.bar(peak_numbers, peak_areas_list, color='skyblue', edgecolor='navy', linewidth=1)

        # Add value labels on bars
        for i, (bar, area, rt) in enumerate(zip(bars, peak_areas_list, peak_rts)):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{area:.0f}\n(RT: {rt:.1f})',
                    ha='center', va='bottom', fontsize=9)

        # Calculate relative areas
        total_area = sum(peak_areas_list)
        rel_areas = [a/total_area*100 for a in peak_areas_list]

        # Add percentage as secondary label
        for i, (bar, rel_area) in enumerate(zip(bars, rel_areas)):
            ax4.text(bar.get_x() + bar.get_width()/2., 0,
                    f'{rel_area:.1f}%',
                    ha='center', va='top', fontsize=8, color='darkred')

    ax4.set_title('Peak Areas', fontsize=13, fontweight='bold')
    ax4.set_xlabel('Peak Number')
    ax4.set_ylabel('Area')
    ax4.grid(True, alpha=0.3, axis='y')

    # ===== BOTTOM: Data Table =====
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('tight')
    ax5.axis('off')

    # Create table data
    if len(peak_info) > 0:
        table_data = []
        for p in peak_info:
            table_data.append([
                f"{p['Peak']}",
                f"{p['RT (min)']:.2f}",
                f"{p['Height']:.0f}",
                f"{p['Area']:.0f}",
                f"{p['Area']/sum(peak_areas_list)*100:.1f}%",
                f"{p['Width (min)']:.2f}",
                f"{p['Start RT']:.2f}-{p['End RT']:.2f}"
            ])

        # Create table
        table = ax5.table(cellText=table_data,
                         colLabels=['Peak', 'RT (min)', 'Height', 'Area', 'Area %', 'Width (min)', 'RT Range'],
                         cellLoc='center',
                         loc='center',
                         colWidths=[0.08, 0.12, 0.12, 0.15, 0.12, 0.12, 0.2])

        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.5)

        # Style the header
        for i in range(7):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')

        # Alternate row colors
        for i in range(1, len(table_data) + 1):
            for j in range(7):
                if i % 2 == 0:
                    table[(i, j)].set_facecolor('#f0f0f0')

    # Main title
    fig.suptitle(f'Complete HPLC Analysis - {csv_file.stem}', fontsize=16, fontweight='bold', y=0.98)

    # Add analysis summary text box
    summary_text = (
        f"Baseline Method: robust_fit (improved)\n"
        f"Total Peaks: {len(peaks)}\n"
        f"Baseline Ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.1f}%\n"
        f"Total Corrected Area: {np.trapz(corrected, time):.0f}"
    )

    fig.text(0.02, 0.02, summary_text, fontsize=10,
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout(rect=[0, 0.05, 1, 0.96])

    # Save figure
    output_file = Path("final_baseline_analysis.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nAnalysis plot saved to: {output_file}")

    # Print detailed report
    print("\n" + "="*80)
    print("PEAK ANALYSIS REPORT")
    print("="*80)

    print(f"\nTotal peaks detected: {len(peaks)}")
    print(f"Baseline correction ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.1f}%")
    print(f"Total corrected signal area: {np.trapz(corrected, time):.0f}")

    if len(peak_info) > 0:
        print("\nDetailed Peak Information:")
        print("-" * 80)
        print(f"{'Peak':<6} {'RT (min)':<10} {'Height':<10} {'Area':<12} {'Area %':<10} {'Width (min)':<12}")
        print("-" * 80)

        total_area = sum([p['Area'] for p in peak_info])
        for p in peak_info:
            print(f"{p['Peak']:<6} {p['RT (min)']:<10.2f} {p['Height']:<10.0f} "
                  f"{p['Area']:<12.0f} {p['Area']/total_area*100:<10.1f}% {p['Width (min)']:<12.2f}")

        print("-" * 80)
        print(f"{'TOTAL':<6} {'':<10} {'':<10} {total_area:<12.0f} {'100.0%':<10}")

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

    plt.show()


if __name__ == "__main__":
    analyze_with_improved_baseline()