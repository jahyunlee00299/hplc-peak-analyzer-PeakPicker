"""
Regenerate only the baseline plots with fixed flat baseline and y-axis
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
from scipy.signal import find_peaks
import matplotlib.ticker as ticker

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Setup
data_dir = Path("result/Revision 재실험")
baseline_plots_dir = data_dir / "baseline_plots"
baseline_plots_dir.mkdir(exist_ok=True)

# Get all CSV files
csv_files = sorted(data_dir.glob("*.csv"))

print("=" * 80)
print("REGENERATING BASELINE PLOTS")
print("=" * 80)
print(f"\nFound {len(csv_files)} CSV files")
print(f"Output directory: {baseline_plots_dir}\n")

success_count = 0

for i, csv_file in enumerate(csv_files, 1):
    sample_name = csv_file.stem

    if i % 10 == 0 or i == 1 or i == len(csv_files):
        print(f"  Progress: {i}/{len(csv_files)} files processed...")

    try:
        # Load data
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity = df[1].values

        if np.min(intensity) < 0:
            intensity = intensity - np.min(intensity)

        # Apply baseline correction with flat peaks
        corrector = HybridBaselineCorrector(time, intensity)
        baseline, params = corrector.optimize_baseline_with_linear_peaks()
        method = params.get('method', 'unknown')

        # Calculate metrics
        total_intensity = np.trapz(intensity, time)
        baseline_intensity = np.trapz(baseline, time)
        baseline_ratio = baseline_intensity / total_intensity if total_intensity > 0 else 0

        # Calculate corrected signal
        corrected = intensity - baseline
        corrected = np.maximum(corrected, 0)

        # Find peaks for axis break
        peaks, properties = find_peaks(intensity, height=intensity.max() * 0.01, prominence=intensity.max() * 0.005)

        # Determine break range - ALWAYS apply break
        if len(peaks) > 0:
            peak_heights = intensity[peaks]
            max_peak = peak_heights.max()

            # Always use break: set break_start at 1% of max peak, break_end at 85%
            break_start = max_peak * 0.01
            break_end = max_peak * 0.85
        else:
            # Even if no peaks detected, still create a break based on signal max
            max_signal = intensity.max()
            break_start = max_signal * 0.01
            break_end = max_signal * 0.85

        # Create figure
        fig = plt.figure(figsize=(16, 10))

        # ALWAYS use broken axis
        if True:
            # Broken axis
            height_ratios = [2, 0.25, 0, 6]
            gs = fig.add_gridspec(4, 2, height_ratios=height_ratios, hspace=0.25, wspace=0.3)

            total_height = sum(height_ratios)
            break_mark_ratio = height_ratios[1] / total_height
            d = 0.015

            # Left column
            ax1_top = fig.add_subplot(gs[0, 0])
            ax1_bottom = fig.add_subplot(gs[3, 0])

            for ax in [ax1_top, ax1_bottom]:
                ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
                ax.plot(time, baseline, 'r-', linewidth=0.5, label='Baseline', alpha=0.8)
                ax.fill_between(time, baseline, intensity, alpha=0.2, color='yellow', label='Area to Remove')
                ax.grid(True, alpha=0.3)

            ax1_top.set_ylim(break_end, intensity.max() * 1.01)
            # Set y-axis minimum for original signal: use -500 unless signal goes lower
            if intensity.min() < -500:
                y_min_original = intensity.min() * 1.1  # 10% margin
            else:
                y_min_original = -500
            ax1_bottom.set_ylim(y_min_original, break_start)

            ax1_top.spines['bottom'].set_visible(False)
            ax1_bottom.spines['top'].set_visible(False)
            ax1_top.xaxis.set_visible(False)
            ax1_top.tick_params(labeltop=False)

            kwargs = dict(transform=ax1_top.transAxes, color='k', clip_on=False, linewidth=1)
            ax1_top.plot((-d, +d), (-break_mark_ratio/2, +break_mark_ratio/2), **kwargs)
            ax1_top.plot((1 - d, 1 + d), (-break_mark_ratio/2, +break_mark_ratio/2), **kwargs)
            kwargs.update(transform=ax1_bottom.transAxes)
            ax1_bottom.plot((-d, +d), (1 - break_mark_ratio/2, 1 + break_mark_ratio/2), **kwargs)
            ax1_bottom.plot((1 - d, 1 + d), (1 - break_mark_ratio/2, 1 + break_mark_ratio/2), **kwargs)

            ax1_top.set_title(f'{sample_name} - Original Signal', fontsize=14, fontweight='bold', pad=20)
            ax1_top.legend(fontsize=10, loc='upper right')
            ax1_top.set_ylabel('Intensity', fontsize=12)
            ax1_bottom.set_ylabel('Intensity', fontsize=12)
            ax1_bottom.set_xlabel('Retention Time (min)', fontsize=12)
            ax1_bottom.yaxis.set_major_locator(ticker.MaxNLocator(nbins=10, integer=False))

            # Add method info to bottom left plot (same as right)
            info_text = f'Method: {method}\nBaseline Ratio: {baseline_ratio*100:.2f}%'
            ax1_bottom.text(0.02, 0.98, info_text, transform=ax1_bottom.transAxes,
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            # Right column
            ax2_top = fig.add_subplot(gs[0, 1])
            ax2_bottom = fig.add_subplot(gs[3, 1])

            for ax in [ax2_top, ax2_bottom]:
                ax.plot(time, corrected, 'g-', linewidth=1.5, label='Corrected Signal', alpha=0.7)
                ax.grid(True, alpha=0.3)

            ax2_top.set_ylim(break_end, corrected.max() * 1.01)
            # Set y-axis minimum: use -500 unless signal goes lower
            if corrected.min() < -500:
                y_min_corrected = corrected.min() * 1.1  # 10% margin
            else:
                y_min_corrected = -500
            ax2_bottom.set_ylim(y_min_corrected, break_start)  # FIXED: Start from -500

            ax2_top.spines['bottom'].set_visible(False)
            ax2_bottom.spines['top'].set_visible(False)
            ax2_top.xaxis.set_visible(False)
            ax2_top.tick_params(labeltop=False)

            kwargs = dict(transform=ax2_top.transAxes, color='k', clip_on=False, linewidth=1)
            ax2_top.plot((-d, +d), (-break_mark_ratio/2, +break_mark_ratio/2), **kwargs)
            ax2_top.plot((1 - d, 1 + d), (-break_mark_ratio/2, +break_mark_ratio/2), **kwargs)
            kwargs.update(transform=ax2_bottom.transAxes)
            ax2_bottom.plot((-d, +d), (1 - break_mark_ratio/2, 1 + break_mark_ratio/2), **kwargs)
            ax2_bottom.plot((1 - d, 1 + d), (1 - break_mark_ratio/2, 1 + break_mark_ratio/2), **kwargs)

            ax2_top.set_title(f'{sample_name} - Baseline Corrected', fontsize=14, fontweight='bold', pad=20)
            ax2_top.legend(fontsize=10, loc='upper right')
            ax2_top.set_ylabel('Intensity', fontsize=12)
            ax2_bottom.set_ylabel('Intensity', fontsize=12)
            ax2_bottom.set_xlabel('Retention Time (min)', fontsize=12)
            ax2_bottom.yaxis.set_major_locator(ticker.MaxNLocator(nbins=10, integer=False))

            info_text = f'Method: {method}\nBaseline Ratio: {baseline_ratio*100:.2f}%'
            ax2_bottom.text(0.02, 0.98, info_text, transform=ax2_bottom.transAxes,
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()
        output_file = baseline_plots_dir / f"{sample_name}_baseline.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        success_count += 1

    except Exception as e:
        print(f"  [ERROR] {sample_name}: {e}")
        continue

print("\n" + "=" * 80)
print("BASELINE PLOTS REGENERATION COMPLETE")
print("=" * 80)
print(f"\nTotal files processed: {len(csv_files)}")
print(f"Successful: {success_count}")
print(f"Failed: {len(csv_files) - success_count}")
print(f"\nPlots saved to: {baseline_plots_dir}")
print()
