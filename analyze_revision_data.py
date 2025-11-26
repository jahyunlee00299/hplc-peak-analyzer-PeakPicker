"""
Analyze Revision 재실험 data with improved baseline correction
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import UnivariateSpline, interp1d
from scipy.integrate import trapezoid
import warnings
warnings.filterwarnings('ignore')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


def improved_baseline_correction(time, intensity_raw):
    """
    Apply improved baseline correction:
    1. Remove negative offset
    2. Place anchors only at true valleys
    3. Heavy smoothing
    4. Constrain baseline to stay low
    """

    # Step 1: Fix negative offset
    baseline_offset = np.percentile(intensity_raw, 10)
    intensity = intensity_raw - baseline_offset

    # Step 2: Find peaks and valleys
    window = min(51, len(intensity) // 50)
    if window % 2 == 0:
        window += 1

    smoothed = signal.savgol_filter(intensity, window, 3)

    # Find peaks
    peaks, _ = signal.find_peaks(
        smoothed,
        prominence=np.ptp(smoothed) * 0.01,
        distance=window * 2,
        height=np.percentile(smoothed, 75)
    )

    # Find valleys between peaks
    valleys = []

    if intensity[0] < np.percentile(intensity[:100], 50):
        valleys.append(0)

    for i in range(len(peaks) - 1):
        left_peak = peaks[i]
        right_peak = peaks[i + 1]
        segment = intensity[left_peak:right_peak]
        if len(segment) > 0:
            local_min_idx = left_peak + np.argmin(segment)
            valleys.append(local_min_idx)

    if intensity[-1] < np.percentile(intensity[-100:], 50):
        valleys.append(len(intensity) - 1)

    valleys = np.array(valleys) if len(valleys) > 0 else np.array([0, len(intensity)-1])

    # Add more points in flat low regions if needed
    anchor_indices = valleys
    anchor_values = intensity[valleys]

    if len(anchor_indices) < 5:
        gradient = np.abs(np.gradient(smoothed))
        flat_regions = gradient < np.percentile(gradient, 20)
        low_regions = intensity < np.percentile(intensity, 20)
        good_points = flat_regions & low_regions
        good_indices = np.where(good_points)[0]

        if len(good_indices) > 0:
            step = max(1, len(good_indices) // 5)
            extra_points = good_indices[::step][:5]
            anchor_indices = np.concatenate([anchor_indices, extra_points])
            anchor_values = intensity[anchor_indices]
            sort_idx = np.argsort(anchor_indices)
            anchor_indices = anchor_indices[sort_idx]
            anchor_values = anchor_values[sort_idx]

    # Step 3: Create baseline
    baseline = np.zeros_like(intensity)

    if len(anchor_indices) >= 3:
        # Ensure anchor values don't exceed nearby intensity
        for i in range(len(anchor_values)):
            idx = anchor_indices[i]
            start = max(0, idx - 50)
            end = min(len(intensity), idx + 50)
            local_min = np.min(intensity[start:end])
            anchor_values[i] = min(anchor_values[i], local_min)

        s = len(anchor_indices) * 100.0
        try:
            spl = UnivariateSpline(anchor_indices, anchor_values, s=s, k=min(3, len(anchor_indices)-1))
            baseline = spl(np.arange(len(intensity)))
        except:
            f = interp1d(anchor_indices, anchor_values, kind='linear', fill_value='extrapolate')
            baseline = f(np.arange(len(intensity)))
    else:
        f = interp1d(anchor_indices, anchor_values, kind='linear', fill_value='extrapolate')
        baseline = f(np.arange(len(intensity)))

    # Step 4: Constrain baseline
    baseline = np.minimum(baseline, intensity)

    # Lower baseline in peak regions
    for peak_idx in peaks:
        peak_height = intensity[peak_idx]
        threshold = peak_height * 0.1

        left = peak_idx
        while left > 0 and intensity[left] > threshold:
            left -= 1
        left = max(0, left - 20)

        right = peak_idx
        while right < len(intensity) - 1 and intensity[right] > threshold:
            right += 1
        right = min(len(intensity) - 1, right + 20)

        if right > left:
            boundary_min = min(intensity[left], intensity[right])
            baseline[left:right] = np.minimum(baseline[left:right], boundary_min)

    # Smooth baseline
    if len(baseline) > 101:
        baseline = signal.savgol_filter(baseline, 101, 3)

    # Final constraint
    baseline = np.minimum(baseline, 0)

    # Calculate corrected signal
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)

    return corrected, baseline, baseline_offset, peaks, valleys


def analyze_revision_samples():
    """Analyze Revision experiment samples"""

    data_dir = Path("result/Revision 재실험")

    if not data_dir.exists():
        print(f"Directory not found: {data_dir}")
        return

    # Get all CSV files
    csv_files = sorted(data_dir.glob("*.csv"))

    print("\n" + "="*80)
    print("REVISION 재실험 DATA ANALYSIS")
    print("="*80)
    print(f"Total CSV files: {len(csv_files)}")

    # Select a few representative samples for visualization
    sample_indices = [0, 15, 30, 45, 60]  # 5 samples
    selected_files = [csv_files[i] for i in sample_indices if i < len(csv_files)]

    print(f"\nAnalyzing {len(selected_files)} representative samples:")
    for f in selected_files:
        print(f"  - {f.stem}")

    # Analyze all samples for statistics
    all_results = []

    for csv_file in csv_files:
        try:
            # Load data
            df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
            time = df[0].values
            intensity_raw = df[1].values

            # Apply improved baseline correction
            corrected, baseline, offset, peaks, valleys = improved_baseline_correction(time, intensity_raw)

            # Detect peaks
            peaks_final, _ = signal.find_peaks(
                corrected,
                prominence=np.ptp(corrected) * 0.005,
                height=np.percentile(corrected[corrected > 0], 50) if np.any(corrected > 0) else 0,
                width=3
            )

            # Calculate statistics
            total_area = trapezoid(corrected, time)
            baseline_ratio = (np.trapz(baseline, time) / np.trapz(intensity_raw, time)) * 100 if np.trapz(intensity_raw, time) != 0 else 0

            all_results.append({
                'Sample': csv_file.stem,
                'Peaks': len(peaks_final),
                'Total_Area': total_area,
                'Baseline_Offset': offset,
                'Baseline_Ratio_%': baseline_ratio,
                'Max_Intensity': corrected.max()
            })

        except Exception as e:
            print(f"Error processing {csv_file.name}: {e}")
            continue

    # Create detailed visualization for selected samples
    n_samples = len(selected_files)
    fig, axes = plt.subplots(n_samples, 3, figsize=(18, 4*n_samples))

    if n_samples == 1:
        axes = axes.reshape(1, -1)

    for idx, csv_file in enumerate(selected_files):
        print(f"\nProcessing: {csv_file.stem}")

        # Load data
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity_raw = df[1].values

        # Apply baseline correction
        corrected, baseline, offset, peaks, valleys = improved_baseline_correction(time, intensity_raw)

        # Shift intensity for visualization
        intensity = intensity_raw - offset

        # Detect final peaks
        peaks_final, _ = signal.find_peaks(
            corrected,
            prominence=np.ptp(corrected) * 0.005,
            height=np.percentile(corrected[corrected > 0], 50) if np.any(corrected > 0) else 0,
            width=3
        )

        # Plot 1: Raw data with offset
        ax1 = axes[idx, 0]
        ax1.plot(time, intensity_raw, 'b-', linewidth=1, alpha=0.8)
        ax1.axhline(y=offset, color='r', linestyle='--', alpha=0.5, label=f'Offset: {offset:.0f}')
        ax1.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
        ax1.set_title(f'{csv_file.stem}\nRaw Data', fontsize=10)
        ax1.set_xlabel('Time (min)', fontsize=9)
        ax1.set_ylabel('Raw Intensity', fontsize=9)
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # Plot 2: Baseline correction
        ax2 = axes[idx, 1]
        ax2.plot(time, intensity, 'b-', linewidth=1, alpha=0.8, label='Signal')
        ax2.plot(time, baseline, 'r-', linewidth=1, label='Baseline')

        # Mark valleys
        if len(valleys) > 0:
            ax2.scatter(time[valleys], intensity[valleys], c='green', s=30, marker='v',
                       zorder=5, label='Valleys', edgecolors='black', linewidths=0.5)

        ax2.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                         alpha=0.2, color='yellow')
        ax2.set_title('Baseline Correction', fontsize=10)
        ax2.set_xlabel('Time (min)', fontsize=9)
        ax2.set_ylabel('Intensity', fontsize=9)
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        # Plot 3: Corrected signal
        ax3 = axes[idx, 2]
        ax3.plot(time, corrected, 'g-', linewidth=1, alpha=0.9)
        ax3.fill_between(time, 0, corrected, alpha=0.2, color='lightgreen')

        if len(peaks_final) > 0:
            ax3.scatter(time[peaks_final], corrected[peaks_final],
                       color='red', s=40, marker='^', zorder=5)

        ax3.set_title(f'Corrected Signal ({len(peaks_final)} peaks)', fontsize=10)
        ax3.set_xlabel('Time (min)', fontsize=9)
        ax3.set_ylabel('Corrected Intensity', fontsize=9)
        ax3.grid(True, alpha=0.3)

        print(f"  - Offset: {offset:.0f}")
        print(f"  - Peaks detected: {len(peaks_final)}")
        print(f"  - Valleys used: {len(valleys)}")

    plt.suptitle('Revision 재실험 - Improved Baseline Correction Analysis',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()

    # Save figure
    output_file = Path("revision_analysis_improved.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nVisualization saved to: {output_file}")

    # Save statistics to CSV
    if all_results:
        results_df = pd.DataFrame(all_results)
        stats_file = Path("revision_baseline_statistics.csv")
        results_df.to_csv(stats_file, index=False)
        print(f"Statistics saved to: {stats_file}")

        # Print summary statistics
        print("\n" + "="*80)
        print("SUMMARY STATISTICS")
        print("="*80)
        print(f"Total samples analyzed: {len(all_results)}")
        print(f"\nPeak counts:")
        print(f"  Mean: {results_df['Peaks'].mean():.1f}")
        print(f"  Median: {results_df['Peaks'].median():.0f}")
        print(f"  Range: {results_df['Peaks'].min():.0f} - {results_df['Peaks'].max():.0f}")

        print(f"\nBaseline offset:")
        print(f"  Mean: {results_df['Baseline_Offset'].mean():.0f}")
        print(f"  Median: {results_df['Baseline_Offset'].median():.0f}")
        print(f"  Range: {results_df['Baseline_Offset'].min():.0f} - {results_df['Baseline_Offset'].max():.0f}")

        print(f"\nBaseline ratio (%):")
        print(f"  Mean: {results_df['Baseline_Ratio_%'].mean():.1f}%")
        print(f"  Median: {results_df['Baseline_Ratio_%'].median():.1f}%")

        # Show first 10 results
        print(f"\nFirst 10 samples:")
        print(results_df.head(10).to_string(index=False))

    plt.show()


if __name__ == "__main__":
    analyze_revision_samples()