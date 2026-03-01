"""
Excel Exporter
==============

Exports analysis results to Excel format.
Interface Segregation: Separate from CSV and plot exporters.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd
import numpy as np

from ...interfaces import IExcelExporter, IBatchExporter
from ...domain import Peak, AnalysisResult, BatchResult


class ExcelExporter(IExcelExporter):
    """
    Exports analysis results to Excel files.

    Single Responsibility: Only handles Excel export.
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize exporter.

        Parameters
        ----------
        output_dir : Path, optional
            Default output directory
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        result: AnalysisResult,
        output_path: Path,
        **options
    ) -> Path:
        """
        Export analysis result to Excel.

        Parameters
        ----------
        result : AnalysisResult
            Analysis result to export
        output_path : Path
            Output file path
        **options
            Additional options

        Returns
        -------
        Path
            Path to created file
        """
        output_path = Path(output_path)
        if output_path.suffix.lower() != '.xlsx':
            output_path = output_path.with_suffix('.xlsx')

        # Create peak data
        peak_data = self._peaks_to_dataframe(result.peaks)

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Write peak data
            peak_data.to_excel(writer, sheet_name='Peak Data', index=False)

            # Write summary
            summary = self._create_summary(result)
            summary.to_excel(writer, sheet_name='Summary', index=False, header=False)

        return output_path

    def export_with_metadata(
        self,
        result: AnalysisResult,
        output_path: Path,
        metadata: Dict[str, Any] = None
    ) -> Path:
        """
        Export with additional metadata sheet.

        Parameters
        ----------
        result : AnalysisResult
            Analysis result
        output_path : Path
            Output path
        metadata : Dict[str, Any], optional
            Additional metadata

        Returns
        -------
        Path
            Path to created file
        """
        output_path = Path(output_path)
        if output_path.suffix.lower() != '.xlsx':
            output_path = output_path.with_suffix('.xlsx')

        peak_data = self._peaks_to_dataframe(result.peaks)

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Metadata sheet
            meta_rows = [
                ['Sample Name', result.chromatogram.sample_name],
                ['Analysis Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Number of Peaks', len(result.peaks)],
                ['Total Area', result.total_area],
                ['Detector', result.chromatogram.detector_type],
            ]

            if metadata:
                for key, value in metadata.items():
                    meta_rows.append([key, value])

            meta_df = pd.DataFrame(meta_rows)
            meta_df.to_excel(writer, sheet_name='Metadata', index=False, header=False)

            # Peak data
            peak_data.to_excel(writer, sheet_name='Peak Data', index=False)

            # Summary
            if len(result.peaks) > 0:
                summary = self._create_summary(result)
                summary.to_excel(writer, sheet_name='Summary', index=False, header=False)

        return output_path

    def _peaks_to_dataframe(self, peaks: List[Peak]) -> pd.DataFrame:
        """Convert peaks to DataFrame."""
        if not peaks:
            return pd.DataFrame()

        total_area = sum(p.area for p in peaks)

        data = []
        for i, peak in enumerate(peaks, 1):
            data.append({
                'Peak #': i,
                'RT (min)': round(peak.rt, 3),
                'RT Start (min)': round(peak.rt_start, 3),
                'RT End (min)': round(peak.rt_end, 3),
                'Height': round(peak.height, 2),
                'Area': round(peak.area, 2),
                'Width (min)': round(peak.width, 3),
                '% Area': round((peak.area / total_area * 100) if total_area > 0 else 0, 2)
            })

        return pd.DataFrame(data)

    def _create_summary(self, result: AnalysisResult) -> pd.DataFrame:
        """Create summary DataFrame."""
        peaks = result.peaks
        if not peaks:
            return pd.DataFrame([['No peaks detected', '']])

        df = self._peaks_to_dataframe(peaks)

        return pd.DataFrame([
            ['Total Peaks', len(peaks)],
            ['Total Area', round(df['Area'].sum(), 2)],
            ['Average Height', round(df['Height'].mean(), 2)],
            ['Average Width', round(df['Width (min)'].mean(), 3)],
            ['RT Range', f"{df['RT (min)'].min():.2f} - {df['RT (min)'].max():.2f}"],
        ])


class CSVExporter:
    """
    Exports peak data to CSV format.

    Single Responsibility: Only handles CSV export.
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize exporter.

        Parameters
        ----------
        output_dir : Path, optional
            Default output directory
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        result: AnalysisResult,
        output_path: Path,
        **options
    ) -> Path:
        """
        Export analysis result to CSV.

        Parameters
        ----------
        result : AnalysisResult
            Analysis result
        output_path : Path
            Output path
        **options
            Additional options

        Returns
        -------
        Path
            Path to created file
        """
        return self.export_peaks_only(
            result.peaks,
            output_path,
            result.chromatogram.sample_name
        )

    def export_peaks_only(
        self,
        peaks: List[Peak],
        output_path: Path,
        sample_name: str = None
    ) -> Path:
        """
        Export only peak data to CSV.

        Parameters
        ----------
        peaks : List[Peak]
            Peaks to export
        output_path : Path
            Output path
        sample_name : str, optional
            Sample name to include

        Returns
        -------
        Path
            Path to created file
        """
        output_path = Path(output_path)
        if output_path.suffix.lower() != '.csv':
            output_path = output_path.with_suffix('.csv')

        if not peaks:
            pd.DataFrame().to_csv(output_path, index=False)
            return output_path

        total_area = sum(p.area for p in peaks)

        data = []
        for i, peak in enumerate(peaks, 1):
            row = {
                'Peak #': i,
                'RT (min)': round(peak.rt, 3),
                'RT Start (min)': round(peak.rt_start, 3),
                'RT End (min)': round(peak.rt_end, 3),
                'Height': round(peak.height, 2),
                'Area': round(peak.area, 2),
                'Width (min)': round(peak.width, 3),
                '% Area': round((peak.area / total_area * 100) if total_area > 0 else 0, 2)
            }
            if sample_name:
                row = {'Sample': sample_name, **row}
            data.append(row)

        pd.DataFrame(data).to_csv(output_path, index=False)
        return output_path


class BatchExcelExporter(IBatchExporter):
    """
    Exports batch results to Excel.

    Single Responsibility: Only handles batch export.
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize exporter.

        Parameters
        ----------
        output_dir : Path, optional
            Default output directory
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_batch(
        self,
        batch_result: BatchResult,
        output_dir: Path,
        filename_prefix: str = "batch"
    ) -> List[Path]:
        """
        Export batch results.

        Parameters
        ----------
        batch_result : BatchResult
            Batch results
        output_dir : Path
            Output directory
        filename_prefix : str
            Prefix for output files

        Returns
        -------
        List[Path]
            Paths to created files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{filename_prefix}_summary.xlsx"

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            all_peaks_data = []

            for result in batch_result.results:
                name = result.chromatogram.sample_name
                peaks = result.peaks

                total_area = sum(p.area for p in peaks) if peaks else 0
                summary_data.append({
                    'Sample': name,
                    'Peaks': len(peaks),
                    'Total Area': round(total_area, 2),
                    'Avg Height': round(np.mean([p.height for p in peaks]), 2) if peaks else 0,
                })

                for i, peak in enumerate(peaks, 1):
                    all_peaks_data.append({
                        'Sample': name,
                        'Peak #': i,
                        'RT (min)': round(peak.rt, 3),
                        'Height': round(peak.height, 2),
                        'Area': round(peak.area, 2),
                    })

            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

            if all_peaks_data:
                pd.DataFrame(all_peaks_data).to_excel(writer, sheet_name='All Peaks', index=False)

        return [output_path]
