"""
Export HPLC Analysis Results to Excel and CSV
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


class ResultExporter:
    """Export analysis results to various formats"""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize exporter

        Args:
            output_dir: Directory to save results (default: current directory)
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_peaks_to_excel(
        self,
        peaks: List[Peak],
        filename: str,
        sample_name: str = "Unknown",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Export peak data to Excel file

        Args:
            peaks: List of Peak objects
            filename: Output filename (without extension)
            sample_name: Name of the sample
            metadata: Additional metadata to include

        Returns:
            Path to created Excel file
        """
        output_path = self.output_dir / f"{filename}.xlsx"

        # Create DataFrame from peaks
        peak_data = []
        for i, peak in enumerate(peaks, 1):
            peak_data.append({
                'Peak #': i,
                'RT (min)': round(peak.rt, 3),
                'RT Start (min)': round(peak.rt_start, 3),
                'RT End (min)': round(peak.rt_end, 3),
                'Height': round(peak.height, 2),
                'Area': round(peak.area, 2),
                'Width (min)': round(peak.width, 3),
                '% Area': 0.0,  # Will calculate below
            })

        df = pd.DataFrame(peak_data)

        # Calculate % area
        if len(peaks) > 0:
            total_area = df['Area'].sum()
            df['% Area'] = (df['Area'] / total_area * 100).round(2)

        # Create Excel writer
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Write metadata sheet
            metadata_df = pd.DataFrame([
                ['Sample Name', sample_name],
                ['Analysis Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Number of Peaks', len(peaks)],
                ['Total Area', df['Area'].sum() if len(peaks) > 0 else 0],
            ])
            if metadata:
                for key, value in metadata.items():
                    metadata_df = pd.concat([
                        metadata_df,
                        pd.DataFrame([[key, value]])
                    ], ignore_index=True)

            metadata_df.to_excel(
                writer,
                sheet_name='Metadata',
                index=False,
                header=False
            )

            # Write peak data sheet
            df.to_excel(writer, sheet_name='Peak Data', index=False)

            # Write summary statistics
            if len(peaks) > 0:
                summary_df = pd.DataFrame([
                    ['Total Peaks', len(peaks)],
                    ['Total Area', round(df['Area'].sum(), 2)],
                    ['Average Peak Height', round(df['Height'].mean(), 2)],
                    ['Average Peak Width', round(df['Width (min)'].mean(), 3)],
                    ['Retention Time Range', f"{df['RT (min)'].min():.2f} - {df['RT (min)'].max():.2f}"],
                ])
                summary_df.to_excel(
                    writer,
                    sheet_name='Summary',
                    index=False,
                    header=False
                )

        print(f"[OK] Excel file saved: {output_path}")
        return str(output_path)

    def export_peaks_to_csv(
        self,
        peaks: List[Peak],
        filename: str,
        sample_name: str = "Unknown",
    ) -> str:
        """
        Export peak data to CSV file

        Args:
            peaks: List of Peak objects
            filename: Output filename (without extension)
            sample_name: Name of the sample

        Returns:
            Path to created CSV file
        """
        output_path = self.output_dir / f"{filename}.csv"

        # Create DataFrame
        peak_data = []
        for i, peak in enumerate(peaks, 1):
            peak_data.append({
                'Sample': sample_name,
                'Peak #': i,
                'RT (min)': round(peak.rt, 3),
                'RT Start (min)': round(peak.rt_start, 3),
                'RT End (min)': round(peak.rt_end, 3),
                'Height': round(peak.height, 2),
                'Area': round(peak.area, 2),
                'Width (min)': round(peak.width, 3),
            })

        df = pd.DataFrame(peak_data)

        # Calculate % area
        if len(peaks) > 0:
            total_area = df['Area'].sum()
            df['% Area'] = (df['Area'] / total_area * 100).round(2)

        df.to_csv(output_path, index=False)
        print(f"[OK] CSV file saved: {output_path}")
        return str(output_path)

    def export_chromatogram_plot(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        peaks: List[Peak],
        filename: str,
        sample_name: str = "Unknown",
        figsize: tuple = (14, 7),
        detector_type: str = "Signal",
    ) -> str:
        """
        Export chromatogram plot with annotated peaks

        Args:
            time: Time array
            intensity: Intensity array
            peaks: List of Peak objects
            filename: Output filename (without extension)
            sample_name: Name of the sample
            figsize: Figure size in inches
            detector_type: Type of detector (e.g., "RID", "UV", "Signal")

        Returns:
            Path to created PNG file
        """
        output_path = self.output_dir / f"{filename}.png"

        fig, ax = plt.subplots(figsize=figsize)

        # Plot chromatogram with better styling
        ax.plot(time, intensity, 'b-', linewidth=0.8, label=f'{detector_type} Signal', alpha=0.8)

        # Sort peaks by height for better annotation
        peaks_sorted = sorted(enumerate(peaks, 1), key=lambda x: x[1].height, reverse=True)

        # Mark peaks
        for original_idx, peak in enumerate(peaks, 1):
            # Get actual signal intensity at peak position
            peak_y = intensity[peak.index]

            # Plot peak maximum
            ax.plot(peak.rt, peak_y, 'ro', markersize=6, zorder=5)

            # Only annotate top peaks to avoid clutter
            if original_idx <= 10 or peak.height > np.percentile([p.height for p in peaks], 75):
                # Annotate peak with height info
                ax.annotate(
                    f'#{original_idx}\nRT: {peak.rt:.2f}\nH: {peak.height:,.0f}',
                    xy=(peak.rt, peak_y),
                    xytext=(0, 25),
                    textcoords='offset points',
                    ha='center',
                    fontsize=7,
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.75, edgecolor='orange'),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', lw=1)
                )

            # Shade peak area with gradient effect
            peak_mask = (time >= peak.rt_start) & (time <= peak.rt_end)
            peak_time = time[peak_mask]
            peak_intensity = intensity[peak_mask]

            if len(peak_time) > 0:
                # Baseline
                baseline_start = intensity[peak.index_start]
                baseline_end = intensity[peak.index_end]
                baseline = np.linspace(baseline_start, baseline_end, len(peak_time))

                ax.fill_between(
                    peak_time,
                    baseline,
                    peak_intensity,
                    alpha=0.25,
                    color='green',
                    label='Peak Area' if original_idx == 1 else ''
                )

        ax.set_xlabel('Retention Time (min)', fontsize=13, fontweight='bold')
        ax.set_ylabel(f'{detector_type} Response', fontsize=13, fontweight='bold')
        ax.set_title(
            f'HPLC Chromatogram: {sample_name}\n{len(peaks)} peaks detected | Detector: {detector_type}',
            fontsize=15, fontweight='bold', pad=20
        )
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

        # Add legend
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))  # Remove duplicates
        ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=10)

        # Format y-axis with thousands separator
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"[OK] Chromatogram plot saved: {output_path}")
        return str(output_path)

    def export_batch_summary(
        self,
        batch_results: List[Dict],
        filename: str = "batch_summary",
    ) -> str:
        """
        Export summary of multiple samples

        Args:
            batch_results: List of dictionaries containing analysis results
                          Each dict should have: 'sample_name', 'peaks', 'metadata'
            filename: Output filename

        Returns:
            Path to created Excel file
        """
        output_path = self.output_dir / f"{filename}.xlsx"

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Create summary table
            summary_data = []
            all_peaks_data = []

            for result in batch_results:
                sample_name = result['sample_name']
                peaks = result['peaks']
                metadata = result.get('metadata', {})

                # Add to summary
                total_area = sum(p.area for p in peaks) if peaks else 0
                summary_data.append({
                    'Sample': sample_name,
                    'Number of Peaks': len(peaks),
                    'Total Area': round(total_area, 2),
                    'Avg Peak Height': round(np.mean([p.height for p in peaks]), 2) if peaks else 0,
                    'RT Range': f"{min(p.rt for p in peaks):.2f}-{max(p.rt for p in peaks):.2f}" if peaks else "N/A",
                })

                # Add all peaks to detailed table
                for i, peak in enumerate(peaks, 1):
                    all_peaks_data.append({
                        'Sample': sample_name,
                        'Peak #': i,
                        'RT (min)': round(peak.rt, 3),
                        'Height': round(peak.height, 2),
                        'Area': round(peak.area, 2),
                        'Width (min)': round(peak.width, 3),
                    })

            # Write summary sheet
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Write detailed peaks sheet
            if all_peaks_data:
                peaks_df = pd.DataFrame(all_peaks_data)
                peaks_df.to_excel(writer, sheet_name='All Peaks', index=False)

        print(f"[OK] Batch summary saved: {output_path}")
        return str(output_path)


if __name__ == "__main__":
    # Test exporter with dummy data
    from peak_detector import Peak

    # Create dummy peaks
    dummy_peaks = [
        Peak(rt=2.5, rt_start=2.3, rt_end=2.7, height=100, area=250,
             width=0.15, index=250, index_start=230, index_end=270),
        Peak(rt=5.8, rt_start=5.5, rt_end=6.1, height=150, area=400,
             width=0.20, index=580, index_start=550, index_end=610),
    ]

    exporter = ResultExporter(output_dir="test_results")
    exporter.export_peaks_to_excel(
        dummy_peaks,
        "test_export",
        sample_name="Test Sample"
    )
    print("Test export completed!")
