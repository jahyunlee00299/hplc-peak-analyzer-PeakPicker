"""
Per-sample chromatogram plots for batch quantification
======================================================

Matplotlib reports used by ``scripts/quantify_peaks.PeakQuantifier``:

* ``plot_peak_information``          - summary panels for generic (non-standard-curve) samples
* ``create_individual_chromatograms`` - one multi-panel figure per sample
* ``create_overlay_chromatograms``    - replicate overlays (groups of >= 2 samples)

``sample_details`` is a list of dicts with keys ``name``, ``time``, ``intensity``, ``baseline``, ``corrected``
and ``peaks`` (peak dicts with ``index``, ``left_idx``, ``right_idx``, ``rt``, ``height``, ``area``, ``width``,
``prominence``). Fonts are taken from the caller's matplotlib rcParams.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def plot_peak_information(df, output_dir):
    """Visualize generic sample peak information"""
    # Main peak (rank 1) info per sample
    main_peaks = df[df['peak_rank'] == 1].copy()

    if len(main_peaks) == 0:
        print("No main peaks to display.")
        return

    # Per-sample statistics
    print("\nMain peak info per sample:")
    print(f"{'Sample':<40} {'RT':>8} {'Height':>12} {'Area':>15} {'Width':>8}")
    print("-" * 90)

    for _, row in main_peaks.iterrows():
        print(f"{row['sample']:<40} {row['rt']:>8.2f} {row['height']:>12.1f} {row['area']:>15.1f} {row['width']:>8.4f}")

    # Visualization
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Panel 1: RT distribution
    ax1 = axes[0, 0]
    ax1.bar(range(len(main_peaks)), main_peaks['rt'].values, color='steelblue', alpha=0.7)
    ax1.set_xlabel('Sample #', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Retention Time (min)', fontsize=12, fontweight='bold')
    ax1.set_title('Main Peak RT Distribution', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')

    # RT mean line
    rt_mean = main_peaks['rt'].mean()
    ax1.axhline(rt_mean, color='red', linestyle='--', linewidth=2,
               label=f'Mean: {rt_mean:.2f} min')
    ax1.legend(fontsize=10)

    # Panel 2: area distribution
    ax2 = axes[0, 1]
    ax2.bar(range(len(main_peaks)), main_peaks['area'].values, color='forestgreen', alpha=0.7)
    ax2.set_xlabel('Sample #', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Peak Area', fontsize=12, fontweight='bold')
    ax2.set_title('Main Peak Area Distribution', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')

    # Area mean and standard deviation
    area_mean = main_peaks['area'].mean()
    area_std = main_peaks['area'].std()
    ax2.axhline(area_mean, color='red', linestyle='--', linewidth=2,
               label=f'Mean: {area_mean:.1f}')
    ax2.axhline(area_mean + area_std, color='orange', linestyle=':', linewidth=1.5,
               label=f'±1 SD: {area_std:.1f}')
    ax2.axhline(area_mean - area_std, color='orange', linestyle=':', linewidth=1.5)
    ax2.legend(fontsize=10)

    # Panel 3: height vs. area scatter plot
    ax3 = axes[1, 0]
    scatter = ax3.scatter(main_peaks['height'].values, main_peaks['area'].values,
                        s=100, c=main_peaks['rt'].values, cmap='viridis',
                        alpha=0.7, edgecolors='black', linewidth=1)
    ax3.set_xlabel('Peak Height (mAU)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Peak Area', fontsize=12, fontweight='bold')
    ax3.set_title('Height vs. Area Correlation', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    # Colorbar (RT)
    cbar = plt.colorbar(scatter, ax=ax3)
    cbar.set_label('RT (min)', fontsize=10)

    # Panel 4: statistics summary table
    ax4 = axes[1, 1]
    ax4.axis('off')

    # Compute statistics
    stats = {
        'Item': ['Sample count', 'RT mean', 'RT std dev', 'RT range',
                'Area mean', 'Area std dev', 'Area CV%', 'Area range',
                'Height mean', 'Height std dev'],
        'Value': [
            f"{len(main_peaks)}",
            f"{main_peaks['rt'].mean():.2f} min",
            f"{main_peaks['rt'].std():.4f} min",
            f"{main_peaks['rt'].min():.2f} ~ {main_peaks['rt'].max():.2f} min",
            f"{main_peaks['area'].mean():.1f}",
            f"{main_peaks['area'].std():.1f}",
            f"{main_peaks['area'].std() / main_peaks['area'].mean() * 100:.1f}%",
            f"{main_peaks['area'].min():.1f} ~ {main_peaks['area'].max():.1f}",
            f"{main_peaks['height'].mean():.1f}",
            f"{main_peaks['height'].std():.1f}"
        ]
    }

    table_data = [[stats['Item'][i], stats['Value'][i]] for i in range(len(stats['Item']))]

    table = ax4.table(cellText=table_data, colLabels=['Item', 'Value'],
                     cellLoc='left', loc='center',
                     colWidths=[0.4, 0.6])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2.5)

    # Header style
    for i in range(2):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')

    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        for j in range(2):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#f0f0f0')

    ax4.set_title('Statistics Summary', fontsize=13, fontweight='bold', pad=20)

    plt.tight_layout()
    plot_file = output_dir / 'peak_information_summary.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"Peak information graph saved: {plot_file}")
    plt.close()


def create_individual_chromatograms(sample_details, output_dir):
    """Visualize the chromatogram for each sample"""
    if sample_details is None or len(sample_details) == 0:
        print("No chromatograms to generate.")
        return []

    output_dir = Path(output_dir) / 'chromatograms'
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []

    print(f"\n{'='*80}")
    print("Generating individual chromatograms...")
    print(f"{'='*80}")

    for sample in sample_details:
        sample_name = sample['name']
        time = sample['time']
        intensity = sample['intensity']
        baseline = sample['baseline']
        corrected = sample['corrected']
        peaks = sample['peaks']

        # Detect the peak-containing region (for setting the x-axis range)
        xlim_min, xlim_max = None, None
        if len(peaks) > 0:
            # Find the boundaries of all peaks
            all_left_times = [time[p['left_idx']] for p in peaks]
            all_right_times = [time[p['right_idx']] for p in peaks]

            # Add margin (10% before/after the peaks)
            time_span = time[-1] - time[0]
            margin = time_span * 0.05
            xlim_min = max(time[0], min(all_left_times) - margin)
            xlim_max = min(time[-1], max(all_right_times) + margin)

        # 6-panel layout (with a log-scale panel added)
        fig = plt.figure(figsize=(18, 14))
        gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.3,
                             left=0.06, right=0.97, top=0.95, bottom=0.04)

        # Panel 1: original signal + baseline (linear)
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='Original signal')
        ax1.plot(time, baseline, 'r--', linewidth=2, label='Baseline')

        # Mark peak positions
        for i, peak in enumerate(peaks[:5], 1):  # top 5 only
            peak_idx = peak['index']
            ax1.axvline(time[peak_idx], color='green', linestyle=':', alpha=0.5)
            ax1.text(time[peak_idx], intensity[peak_idx], f'P{i}',
                    fontsize=9, ha='center', va='bottom', color='green', fontweight='bold')

        ax1.set_xlabel('Time (min)', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Intensity (mAU)', fontsize=11, fontweight='bold')
        ax1.set_title(f'Original Chromatogram: {sample_name}', fontsize=12, fontweight='bold')
        ax1.legend(fontsize=10, loc='upper right')
        ax1.grid(True, alpha=0.3)
        if xlim_min is not None:
            ax1.set_xlim(xlim_min, xlim_max)

        # Panel 2: original signal + baseline (log scale)
        ax1_log = fig.add_subplot(gs[1, :])
        # Shift to positive values for the log scale
        intensity_shifted = intensity - np.min(intensity) + 1
        baseline_shifted = baseline - np.min(intensity) + 1

        ax1_log.plot(time, intensity_shifted, 'b-', linewidth=1, alpha=0.7, label='Original signal')
        ax1_log.plot(time, baseline_shifted, 'r--', linewidth=2, label='Baseline')
        ax1_log.set_yscale('log')

        # Mark peak positions
        for i, peak in enumerate(peaks[:5], 1):
            peak_idx = peak['index']
            ax1_log.axvline(time[peak_idx], color='green', linestyle=':', alpha=0.5)

        ax1_log.set_xlabel('Time (min)', fontsize=11, fontweight='bold')
        ax1_log.set_ylabel('Intensity (mAU, log scale)', fontsize=11, fontweight='bold')
        ax1_log.set_title('Original Chromatogram (log scale)', fontsize=12, fontweight='bold')
        ax1_log.legend(fontsize=10, loc='upper right')
        ax1_log.grid(True, alpha=0.3, which='both')
        if xlim_min is not None:
            ax1_log.set_xlim(xlim_min, xlim_max)

        # Panel 3: corrected signal (linear)
        ax2 = fig.add_subplot(gs[2, :])
        ax2.plot(time, corrected, 'g-', linewidth=1.5, label='Corrected signal')
        ax2.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)

        # Fill the peak regions
        for i, peak in enumerate(peaks[:5], 1):
            left_idx = peak['left_idx']
            right_idx = peak['right_idx']
            ax2.fill_between(time[left_idx:right_idx+1], 0, corrected[left_idx:right_idx+1],
                            alpha=0.3, label=f'P{i}' if i <= 3 else None)

            # Show peak info
            peak_idx = peak['index']
            ax2.plot(time[peak_idx], corrected[peak_idx], 'ro', markersize=8)
            ax2.text(time[peak_idx], corrected[peak_idx] * 1.05,
                    f"P{i}\nRT={peak['rt']:.2f}",
                    fontsize=8, ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

        ax2.set_xlabel('Time (min)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Intensity (mAU)', fontsize=11, fontweight='bold')
        ax2.set_title('After Baseline Correction', fontsize=12, fontweight='bold')
        if len(peaks) <= 3:
            ax2.legend(fontsize=9, loc='upper right')
        ax2.grid(True, alpha=0.3)
        if xlim_min is not None:
            ax2.set_xlim(xlim_min, xlim_max)

        # Panel 4: peak info table
        ax3 = fig.add_subplot(gs[3, 0])
        ax3.axis('off')

        if len(peaks) > 0:
            table_data = []
            for i, peak in enumerate(peaks[:10], 1):  # top 10
                table_data.append([
                    f'P{i}',
                    f"{peak['rt']:.2f}",
                    f"{peak['height']:.1f}",
                    f"{peak['area']:.1f}",
                    f"{peak['width']:.4f}",
                    f"{peak['prominence']:.1f}"
                ])

            table = ax3.table(
                cellText=table_data,
                colLabels=['#', 'RT\n(min)', 'Height\n(mAU)', 'Area', 'Width\n(min)', 'Prominence'],
                cellLoc='center',
                loc='center',
                colWidths=[0.08, 0.15, 0.18, 0.22, 0.15, 0.22]
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 2.2)

            # Header style
            for i in range(6):
                table[(0, i)].set_facecolor('#2196F3')
                table[(0, i)].set_text_props(weight='bold', color='white')

            # Alternate row colors
            for i in range(1, len(table_data) + 1):
                for j in range(6):
                    if i % 2 == 0:
                        table[(i, j)].set_facecolor('#f0f0f0')

            ax3.set_title(f'Detected Peaks (top {min(len(peaks), 10)})',
                        fontsize=11, fontweight='bold', pad=10)

        # Panel 5: statistics summary
        ax4 = fig.add_subplot(gs[3, 1])
        ax4.axis('off')

        stats_data = [
            ['Total peaks', f"{len(peaks)}"],
            ['Data points', f"{len(time)}"],
            ['Time range', f"{time[0]:.2f} ~ {time[-1]:.2f} min"],
            ['Intensity range (original)', f"{np.min(intensity):.1f} ~ {np.max(intensity):.1f}"],
            ['Intensity range (corrected)', f"{np.min(corrected):.1f} ~ {np.max(corrected):.1f}"],
        ]

        if len(peaks) > 0:
            main_peak = peaks[0]
            stats_data.extend([
                ['', ''],
                ['[Main peak]', ''],
                ['RT', f"{main_peak['rt']:.2f} min"],
                ['Height', f"{main_peak['height']:.1f} mAU"],
                ['Area', f"{main_peak['area']:.1f}"],
                ['Width', f"{main_peak['width']:.4f} min"],
            ])

        stats_table = ax4.table(
            cellText=stats_data,
            cellLoc='left',
            loc='center',
            colWidths=[0.45, 0.55]
        )
        stats_table.auto_set_font_size(False)
        stats_table.set_fontsize(9)
        stats_table.scale(1, 1.8)

        # Highlight the main peak section
        if len(peaks) > 0:
            stats_table[(6, 0)].set_facecolor('#4CAF50')
            stats_table[(6, 1)].set_facecolor('#4CAF50')
            stats_table[(6, 0)].set_text_props(weight='bold', color='white')

        ax4.set_title('Sample Statistics', fontsize=11, fontweight='bold', pad=10)

        plt.suptitle(f'Chromatogram Analysis: {sample_name}',
                    fontsize=14, fontweight='bold', y=0.995)

        # Save
        output_file = output_dir / f'{sample_name}_chromatogram.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        saved_files.append(output_file)
        print(f"  Saved: {sample_name}_chromatogram.png")

    print(f"\n{len(saved_files)} chromatograms generated in total")
    print(f"Saved to: {output_dir}/")

    return saved_files


def create_overlay_chromatograms(sample_details, output_dir):
    """Overlay the chromatograms of similar samples"""
    if sample_details is None or len(sample_details) == 0:
        print("No overlays to generate.")
        return []

    output_dir = Path(output_dir) / 'overlays'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Smart grouping of similar samples
    import re
    groups = {}

    for sample in sample_details:
        sample_name = sample['name']

        # Try grouping by various patterns
        base_name = None

        # Pattern 1: strip a trailing _number_ or _number (e.g. _1_, _2_, _3_)
        match = re.search(r'(.+?)_\d+_?$', sample_name)
        if match:
            base_name = match.group(1)
        # Pattern 2: strip only a trailing number (e.g. sample1, sample2)
        elif re.search(r'\d+$', sample_name):
            base_name = re.sub(r'\d+$', '', sample_name).rstrip('_')
        # Pattern 3: use as-is (cannot be grouped)
        else:
            base_name = sample_name

        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(sample)

    # Only overlay groups with 2 or more samples
    saved_files = []

    print(f"\n{'='*80}")
    print("Generating overlay chromatograms...")
    print(f"{'='*80}")

    for base_name, samples in groups.items():
        if len(samples) < 2:
            continue

        print(f"  Group: {base_name} ({len(samples)} samples)")

        # Detect the peak-containing region (considering all samples' peaks)
        xlim_min, xlim_max = None, None
        all_peak_times = []
        for sample in samples:
            if len(sample['peaks']) > 0:
                for peak in sample['peaks']:
                    all_peak_times.append(sample['time'][peak['left_idx']])
                    all_peak_times.append(sample['time'][peak['right_idx']])

        if len(all_peak_times) > 0:
            time_span = samples[0]['time'][-1] - samples[0]['time'][0]
            margin = time_span * 0.05
            xlim_min = max(samples[0]['time'][0], min(all_peak_times) - margin)
            xlim_max = min(samples[0]['time'][-1], max(all_peak_times) + margin)

        # 4-panel layout (with a log-scale panel added)
        fig = plt.figure(figsize=(18, 12))
        gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3,
                             left=0.06, right=0.97, top=0.93, bottom=0.05)

        # Panel 1: original signal overlay (linear) + area data points
        ax1 = fig.add_subplot(gs[0, :])
        colors = plt.cm.tab10(np.linspace(0, 1, len(samples)))

        for i, (sample, color) in enumerate(zip(samples, colors), 1):
            time = sample['time']
            intensity = sample['intensity']
            peaks = sample['peaks']
            label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
            ax1.plot(time, intensity, linewidth=1.5, alpha=0.7,
                    color=color, label=label)

            # Show the area value as a data point at every peak position
            for peak in peaks:
                peak_idx = peak['index']
                peak_rt = time[peak_idx]
                peak_intensity = intensity[peak_idx]
                area = peak['area']

                # Show the data point
                ax1.scatter(peak_rt, peak_intensity, s=80, color=color,
                          edgecolors='black', linewidths=1.5, zorder=10, alpha=0.9)

                # Show the area value as text (small font)
                ax1.annotate(f'{area:.0f}',
                           xy=(peak_rt, peak_intensity),
                           xytext=(0, 8), textcoords='offset points',
                           fontsize=7, color=color, fontweight='bold',
                           ha='center',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                                   edgecolor=color, alpha=0.7))

        ax1.set_xlabel('Time (min)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Intensity (mAU)', fontsize=12, fontweight='bold')
        ax1.set_title(f'Original Chromatogram Overlay (area shown per timepoint): {base_name}',
                     fontsize=13, fontweight='bold')
        ax1.legend(fontsize=10, ncol=min(len(samples), 5), loc='upper left')
        ax1.grid(True, alpha=0.3)
        if xlim_min is not None:
            ax1.set_xlim(xlim_min, xlim_max)

        # Panel 2: original signal overlay (log scale)
        ax1_log = fig.add_subplot(gs[1, :])

        for i, (sample, color) in enumerate(zip(samples, colors), 1):
            time = sample['time']
            intensity = sample['intensity']
            # Shift to positive values for the log scale
            intensity_shifted = intensity - np.min(intensity) + 1
            label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
            ax1_log.plot(time, intensity_shifted, linewidth=1.5, alpha=0.7,
                       color=color, label=label)

        ax1_log.set_yscale('log')
        ax1_log.set_xlabel('Time (min)', fontsize=12, fontweight='bold')
        ax1_log.set_ylabel('Intensity (mAU, log scale)', fontsize=12, fontweight='bold')
        ax1_log.set_title(f'Original Chromatogram Overlay (log scale): {base_name}',
                        fontsize=13, fontweight='bold')
        ax1_log.legend(fontsize=10, ncol=min(len(samples), 5))
        ax1_log.grid(True, alpha=0.3, which='both')
        if xlim_min is not None:
            ax1_log.set_xlim(xlim_min, xlim_max)

        # Panel 3: overlay after baseline correction
        ax2 = fig.add_subplot(gs[2, 0])

        for i, (sample, color) in enumerate(zip(samples, colors), 1):
            time = sample['time']
            corrected = sample['corrected']
            label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
            ax2.plot(time, corrected, linewidth=1.5, alpha=0.7,
                    color=color, label=label)

        ax2.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
        ax2.set_xlabel('Time (min)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Intensity (mAU)', fontsize=11, fontweight='bold')
        ax2.set_title('Overlay After Correction', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=9, ncol=min(len(samples), 3))
        ax2.grid(True, alpha=0.3)
        if xlim_min is not None:
            ax2.set_xlim(xlim_min, xlim_max)

        # Panel 4: main peak comparison table
        ax3 = fig.add_subplot(gs[2, 1])
        ax3.axis('off')

        table_data = []
        for i, sample in enumerate(samples, 1):
            peaks = sample['peaks']
            if len(peaks) > 0:
                main_peak = peaks[0]
                label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
                table_data.append([
                    label,
                    f"{main_peak['rt']:.2f}",
                    f"{main_peak['height']:.1f}",
                    f"{main_peak['area']:.1f}",
                    f"{len(peaks)}"
                ])

        if len(table_data) > 0:
            table = ax3.table(
                cellText=table_data,
                colLabels=['Sample', 'RT\n(min)', 'Height\n(mAU)', 'Area', 'Total\npeaks'],
                cellLoc='center',
                loc='center',
                colWidths=[0.15, 0.15, 0.25, 0.25, 0.15]
            )
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2.5)

            # Header style
            for i in range(5):
                table[(0, i)].set_facecolor('#FF9800')
                table[(0, i)].set_text_props(weight='bold', color='white')

            # Alternate row colors
            for i in range(1, len(table_data) + 1):
                for j in range(5):
                    if i % 2 == 0:
                        table[(i, j)].set_facecolor('#f0f0f0')

            ax3.set_title('Main Peak Comparison', fontsize=12, fontweight='bold', pad=10)

        plt.suptitle(f'Replicate Comparison: {base_name}',
                    fontsize=14, fontweight='bold')

        # Save
        output_file = output_dir / f'{base_name}_overlay.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        saved_files.append(output_file)
        print(f"    Saved: {base_name}_overlay.png")

    print(f"\n{len(saved_files)} overlays generated in total")
    print(f"Saved to: {output_dir}/")

    return saved_files
