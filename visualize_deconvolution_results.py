"""
Visualize Deconvolution Results from Analysis
==============================================

Creates visualization plots from analysis results.

Author: PeakPicker Project
Date: 2025-11-10
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

# Set Korean font
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from peak_models import gaussian


def load_analysis_results(excel_file):
    """Load analysis results from Excel file."""
    try:
        # Load sheets
        df_peaks = pd.read_excel(excel_file, sheet_name='Peaks')

        try:
            df_deconv = pd.read_excel(excel_file, sheet_name='Deconvolved_Peaks')
            has_deconv = True
        except:
            df_deconv = None
            has_deconv = False

        return df_peaks, df_deconv, has_deconv
    except Exception as e:
        print(f"Error loading {excel_file}: {e}")
        return None, None, False


def load_chromatogram(csv_file):
    """Load chromatogram data from CSV."""
    try:
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity = df[1].values
        return time, intensity
    except Exception as e:
        print(f"Error loading CSV {csv_file}: {e}")
        return None, None


def visualize_deconvolution(csv_file, excel_file, output_file):
    """Create visualization for a single sample."""

    # Load data
    time, intensity = load_chromatogram(csv_file)
    df_peaks, df_deconv, has_deconv = load_analysis_results(excel_file)

    if time is None or df_peaks is None:
        print(f"Failed to load data for {csv_file}")
        return False

    sample_name = Path(csv_file).stem

    # Create figure
    if has_deconv and len(df_deconv) > 0:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(14, 6))
        ax2 = None

    # Plot 1: Full chromatogram with detected peaks
    ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Chromatogram', alpha=0.7)

    # Mark detected peaks
    for idx, row in df_peaks.iterrows():
        rt = row['retention_time']
        height = row['height']
        ax1.plot(rt, height, 'ro', markersize=8, alpha=0.7)
        ax1.text(rt, height * 1.1, f"{idx+1}", ha='center', fontsize=9)

    ax1.set_xlabel('Retention Time (min)', fontsize=12)
    ax1.set_ylabel('Intensity', fontsize=12)
    ax1.set_title(f'{sample_name} - Peak Detection', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Plot 2: Deconvolved peaks (if available)
    if has_deconv and len(df_deconv) > 0 and ax2 is not None:
        ax2.plot(time, intensity, 'gray', linewidth=1.5, label='Original', alpha=0.5)

        colors = plt.cm.tab10(np.linspace(0, 1, 10))

        # Group by original peak
        grouped = df_deconv.groupby('Original_Peak_Number')

        for peak_num, group in grouped:
            if len(group) > 1:  # Only show if actually deconvolved
                # Plot each component
                for idx, row in group.iterrows():
                    rt = row['Component_RT']
                    amp = row['Component_Height']
                    sigma = row['Sigma']

                    # Generate Gaussian curve
                    t_range = np.linspace(rt - 3*sigma, rt + 3*sigma, 100)
                    gaussian_curve = gaussian(t_range, amp, rt, sigma)

                    color = colors[int(peak_num - 1) % 10]
                    label = f"Peak {int(peak_num)}.{int(row['Component_Number'])}"
                    if row['Is_Shoulder']:
                        label += " (shoulder)"

                    ax2.plot(t_range, gaussian_curve, '--', color=color,
                            linewidth=2, alpha=0.8, label=label)
                    ax2.plot(rt, amp, 'o', color=color, markersize=8)

        ax2.set_xlabel('Retention Time (min)', fontsize=12)
        ax2.set_ylabel('Intensity', fontsize=12)
        ax2.set_title(f'{sample_name} - Deconvolved Components', fontsize=14, fontweight='bold')
        ax2.legend(fontsize=9, ncol=2)
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  Saved: {output_file}")
    plt.close()

    return True


def create_summary_plot(analysis_dir):
    """Create summary plot showing deconvolution statistics."""

    excel_files = list(Path(analysis_dir).glob("*_peaks.xlsx"))

    if not excel_files:
        print("No Excel files found")
        return

    stats = []

    for excel_file in excel_files:
        sample_name = excel_file.stem.replace('_peaks', '')
        df_peaks, df_deconv, has_deconv = load_analysis_results(excel_file)

        if df_peaks is not None:
            n_peaks = len(df_peaks)
            n_deconvolved = 0
            n_components = 0

            if has_deconv and df_deconv is not None:
                # Count original peaks that were deconvolved
                grouped = df_deconv.groupby('Original_Peak_Number')
                n_deconvolved = sum(1 for _, g in grouped if len(g) > 1)
                n_components = len(df_deconv)

            stats.append({
                'sample': sample_name,
                'n_peaks': n_peaks,
                'n_deconvolved': n_deconvolved,
                'n_components': n_components
            })

    if not stats:
        print("No valid data found")
        return

    df_stats = pd.DataFrame(stats)

    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: Number of peaks detected
    samples_to_show = df_stats.head(10)
    x_pos = np.arange(len(samples_to_show))

    ax1.bar(x_pos, samples_to_show['n_peaks'], alpha=0.7, color='blue', label='Total Peaks')
    ax1.bar(x_pos, samples_to_show['n_deconvolved'], alpha=0.7, color='red', label='Deconvolved')

    ax1.set_xlabel('Sample', fontsize=12)
    ax1.set_ylabel('Number of Peaks', fontsize=12)
    ax1.set_title('Peak Detection Statistics', fontsize=14, fontweight='bold')
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(samples_to_show['sample'], rotation=45, ha='right', fontsize=8)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3, axis='y')

    # Plot 2: Deconvolution summary
    total_peaks = df_stats['n_peaks'].sum()
    total_deconvolved = df_stats['n_deconvolved'].sum()
    total_components = df_stats['n_components'].sum()

    categories = ['Total\nPeaks', 'Deconvolved\nPeaks', 'Total\nComponents']
    values = [total_peaks, total_deconvolved, total_components]
    colors_bar = ['blue', 'red', 'green']

    ax2.bar(categories, values, color=colors_bar, alpha=0.7)

    for i, v in enumerate(values):
        ax2.text(i, v, str(v), ha='center', va='bottom', fontweight='bold', fontsize=12)

    ax2.set_ylabel('Count', fontsize=12)
    ax2.set_title('Overall Deconvolution Summary', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    output_file = Path(analysis_dir) / "deconvolution_summary.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nSummary saved: {output_file}")
    plt.close()


def main():
    """Main function."""

    print("="*80)
    print("DECONVOLUTION VISUALIZATION")
    print("="*80)

    # Set data directory
    data_dir = Path("result/DEF_LC 2025-05-19 17-57-25")
    analysis_dir = data_dir / "analysis_results"

    if not analysis_dir.exists():
        print(f"\nAnalysis directory not found: {analysis_dir}")
        return

    # Find Excel files
    excel_files = sorted(list(analysis_dir.glob("*_peaks.xlsx")))

    if not excel_files:
        print(f"\nNo Excel files found in {analysis_dir}")
        return

    print(f"\nFound {len(excel_files)} analysis files")
    print(f"Analysis directory: {analysis_dir}")

    # Create visualizations for samples with deconvolution
    print("\nCreating individual visualizations...")
    viz_count = 0

    for excel_file in excel_files:
        sample_name = excel_file.stem.replace('_peaks', '')
        csv_file = data_dir / f"{sample_name}.csv"

        if not csv_file.exists():
            print(f"  Warning: CSV not found for {sample_name}")
            continue

        # Check if has deconvolution
        _, df_deconv, has_deconv = load_analysis_results(excel_file)

        if has_deconv and df_deconv is not None and len(df_deconv) > 0:
            # Count deconvolved peaks
            grouped = df_deconv.groupby('Original_Peak_Number')
            n_deconvolved = sum(1 for _, g in grouped if len(g) > 1)

            if n_deconvolved > 0:
                print(f"\n{sample_name}: {n_deconvolved} peaks deconvolved")
                output_file = analysis_dir / f"{sample_name}_deconvolution.png"

                if visualize_deconvolution(csv_file, excel_file, output_file):
                    viz_count += 1

    print(f"\n{viz_count} visualizations created")

    # Create summary plot
    print("\nCreating summary plot...")
    create_summary_plot(analysis_dir)

    print("\n" + "="*80)
    print("VISUALIZATION COMPLETE")
    print("="*80)
    print(f"\nCheck the analysis_results folder:")
    print(f"  {analysis_dir}")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
