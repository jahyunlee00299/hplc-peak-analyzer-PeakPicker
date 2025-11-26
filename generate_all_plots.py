"""
Generate visualization plots for all analyzed samples
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

# Set font
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from hybrid_baseline import HybridBaselineCorrector
from peak_models import gaussian


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


def load_analysis_results(excel_file):
    """Load analysis results from Excel file."""
    try:
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


def create_visualization(csv_file, excel_file, output_file):
    """Create visualization for a single sample."""

    # Load data
    time, intensity = load_chromatogram(csv_file)
    df_peaks, df_deconv, has_deconv = load_analysis_results(excel_file)

    if time is None or df_peaks is None:
        return False

    # Shift intensity to positive
    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    # Apply baseline correction
    corrector = HybridBaselineCorrector(time, intensity)
    baseline, params = corrector.optimize_baseline_with_linear_peaks()
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)

    sample_name = Path(csv_file).stem

    # Create figure
    if has_deconv and df_deconv is not None and len(df_deconv) > 0:
        fig, axes = plt.subplots(3, 1, figsize=(16, 12))
    else:
        fig, axes = plt.subplots(2, 1, figsize=(16, 8))
        axes = list(axes) + [None]

    # Plot 1: Original with baseline
    ax = axes[0]
    ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original', alpha=0.7)
    ax.plot(time, baseline, 'r--', linewidth=1.5, label='Baseline')
    ax.set_xlabel('Time (min)', fontsize=12)
    ax.set_ylabel('Intensity', fontsize=12)
    ax.set_title(f'{sample_name} - Baseline Correction', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # Plot 2: Corrected with detected peaks
    ax = axes[1]
    ax.plot(time, corrected, 'b-', linewidth=1.5, label='Baseline Corrected', alpha=0.7)

    # Mark detected peaks
    if len(df_peaks) > 0:
        peak_times = df_peaks['retention_time'].values
        peak_heights = df_peaks['height'].values
        ax.plot(peak_times, peak_heights, 'ro', markersize=8, label=f'{len(df_peaks)} Peaks Detected')

        # Add peak labels
        for i, (rt, h) in enumerate(zip(peak_times, peak_heights)):
            ax.text(rt, h * 1.05, f'#{i+1}\n{rt:.2f}',
                   ha='center', va='bottom', fontsize=8, color='red')

    ax.set_xlabel('Time (min)', fontsize=12)
    ax.set_ylabel('Intensity', fontsize=12)
    ax.set_title('Detected Peaks', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # Set y-axis to start from -500
    current_ylim = ax.get_ylim()
    ax.set_ylim(-500, current_ylim[1])

    # Plot 3: Deconvolution (if available)
    if axes[2] is not None and has_deconv and df_deconv is not None and len(df_deconv) > 0:
        ax = axes[2]
        ax.plot(time, corrected, 'b-', linewidth=2, label='Baseline Corrected', alpha=0.5)

        # Group by original peak
        for orig_peak in df_deconv['Original_Peak_Number'].unique():
            deconv_components = df_deconv[df_deconv['Original_Peak_Number'] == orig_peak]

            if len(deconv_components) > 1:  # Only show if actually deconvolved
                # Plot each component
                colors = plt.cm.Set3(np.linspace(0, 1, len(deconv_components)))
                for idx, (_, comp) in enumerate(deconv_components.iterrows()):
                    # Generate Gaussian for this component
                    center = comp['Component_RT']
                    amplitude = comp['Component_Height']
                    sigma = comp['Sigma']

                    # Generate curve
                    mask = (time >= comp['Start_RT']) & (time <= comp['End_RT'])
                    t_comp = time[mask]
                    y_comp = gaussian(t_comp, amplitude, center, sigma)

                    label = f"Peak {int(orig_peak)}.{int(comp['Component_Number'])} ({comp['Component_Area_Percent']:.1f}%)"
                    ax.plot(t_comp, y_comp, '--', linewidth=2, color=colors[idx], label=label, alpha=0.8)

        ax.set_xlabel('Time (min)', fontsize=12)
        ax.set_ylabel('Intensity', fontsize=12)
        ax.set_title(f'Peak Deconvolution ({len(df_deconv)} Components)', fontsize=14, fontweight='bold')
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    return True


def main():
    """Generate plots for all samples."""

    data_dir = Path("result/Revision 재실험")
    analysis_dir = data_dir / "analysis_results"
    plots_dir = data_dir / "plots"

    # Create plots directory
    plots_dir.mkdir(parents=True, exist_ok=True)

    # Get all CSV files
    csv_files = sorted(data_dir.glob("*.csv"))

    # Search for Excel files recursively in all subdirectories
    excel_files = sorted(data_dir.rglob("*_peaks.xlsx"))

    print("=" * 80)
    print("GENERATING VISUALIZATION PLOTS")
    print("=" * 80)
    print(f"\nData directory: {data_dir}")
    print(f"Analysis results: {analysis_dir}")
    print(f"Output directory: {plots_dir}")
    print(f"\nFound {len(csv_files)} CSV files")
    print(f"Found {len(excel_files)} Excel results")
    print()

    success_count = 0
    failed_files = []

    # Process each file
    print("Generating plots...")
    for i, excel_file in enumerate(excel_files, 1):
        sample_name = excel_file.stem.replace('_peaks', '')

        # Try to find CSV in main directory
        csv_file = data_dir / f"{sample_name}.csv"

        if i % 10 == 0 or i == 1 or i == len(excel_files):
            print(f"  Progress: {i}/{len(excel_files)} files processed...")

        if not csv_file.exists():
            print(f"  [SKIP] CSV not found: {sample_name}")
            failed_files.append(sample_name)
            continue

        output_file = plots_dir / f"{sample_name}_analysis.png"

        try:
            success = create_visualization(csv_file, excel_file, output_file)
            if success:
                success_count += 1
            else:
                failed_files.append(sample_name)
        except Exception as e:
            print(f"  [ERROR] {sample_name}: {e}")
            import traceback
            traceback.print_exc()
            failed_files.append(sample_name)

    print("\n" + "=" * 80)
    print("PLOT GENERATION COMPLETE")
    print("=" * 80)
    print(f"\nTotal files processed: {len(excel_files)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(failed_files)}")

    if failed_files:
        print(f"\nFailed files:")
        for fname in failed_files[:10]:  # Show first 10
            print(f"  - {fname}")
        if len(failed_files) > 10:
            print(f"  ... and {len(failed_files) - 10} more")

    print(f"\nPlots saved to: {plots_dir}")
    print()


if __name__ == '__main__':
    main()
