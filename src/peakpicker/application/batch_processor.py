"""
Batch Processor
================

High-level batch processing for .D folder directories.
Composes scanning, analysis, and export.
"""

import logging
from pathlib import Path
from typing import List, Optional, Callable

import pandas as pd

from ..domain import AnalysisResult, BatchResult
from .workflow import AnalysisWorkflow

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Processes batches of .D folders or data files."""

    def __init__(
        self,
        workflow: AnalysisWorkflow,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Parameters
        ----------
        workflow : AnalysisWorkflow
            Configured analysis workflow
        progress_callback : callable, optional
            Called with (current_index, total, sample_name, status_message)
        """
        self.workflow = workflow
        self.progress_callback = progress_callback

    def process_d_folders(
        self,
        d_folders: List[Path],
        output_dir: Path,
    ) -> BatchResult:
        """
        Process a list of .D folder paths.

        Parameters
        ----------
        d_folders : List[Path]
            List of .D folder paths to process
        output_dir : Path
            Output directory for results

        Returns
        -------
        BatchResult
            Aggregated results
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results: List[AnalysisResult] = []
        errors = []
        total = len(d_folders)

        for i, d_folder in enumerate(d_folders):
            sample_name = d_folder.stem
            if self.progress_callback:
                self.progress_callback(i, total, sample_name, "Analyzing...")

            try:
                result = self.workflow.analyze_and_export(
                    d_folder, output_dir
                )
                results.append(result)
                logger.info(
                    f"[{i+1}/{total}] {sample_name}: "
                    f"{len(result.peaks)} peaks"
                )
            except Exception as e:
                logger.error(f"[{i+1}/{total}] {sample_name}: ERROR - {e}")
                errors.append({'folder': str(d_folder), 'error': str(e)})

        batch_result = BatchResult(results=results)

        # Export batch summary
        self._export_batch_summary(batch_result, output_dir, errors)

        if self.progress_callback:
            self.progress_callback(
                total, total, "Done",
                f"Processed {len(results)}/{total} samples"
            )

        return batch_result

    def _export_batch_summary(
        self,
        batch_result: BatchResult,
        output_dir: Path,
        errors: list,
    ):
        """Export batch summary Excel file."""
        summary_path = output_dir / "batch_summary.xlsx"

        with pd.ExcelWriter(summary_path, engine='openpyxl') as writer:
            # Sample summary sheet
            summary_rows = []
            all_peaks_rows = []

            for result in batch_result.results:
                name = result.chromatogram.sample_name
                peaks = result.peaks
                total_area = sum(p.area for p in peaks) if peaks else 0
                meta = result.chromatogram.metadata

                summary_rows.append({
                    'Sample': name,
                    'Detector': result.chromatogram.detector_type,
                    'Peaks': len(peaks),
                    'Total Area': round(total_area, 2),
                    'Time Range': (
                        f"{result.chromatogram.time[0]:.2f}-"
                        f"{result.chromatogram.time[-1]:.2f} min"
                    ),
                    'Method': meta.get('method', ''),
                    'Date': meta.get('date', ''),
                })

                for j, p in enumerate(peaks, 1):
                    pct = (p.area / total_area * 100) if total_area > 0 else 0
                    all_peaks_rows.append({
                        'Sample': name,
                        'Peak #': j,
                        'RT (min)': round(p.rt, 3),
                        'Height': round(p.height, 4),
                        'Area': round(p.area, 4),
                        'Width (min)': round(p.width, 3),
                        '% Area': round(pct, 2),
                    })

            if summary_rows:
                pd.DataFrame(summary_rows).to_excel(
                    writer, sheet_name='Summary', index=False
                )

            if all_peaks_rows:
                pd.DataFrame(all_peaks_rows).to_excel(
                    writer, sheet_name='All Peaks', index=False
                )

            if errors:
                pd.DataFrame(errors).to_excel(
                    writer, sheet_name='Errors', index=False
                )

        logger.info(f"Batch summary saved: {summary_path}")
