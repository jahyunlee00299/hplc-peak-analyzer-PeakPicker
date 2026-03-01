"""
Quantification Excel Exporter
===============================

Exports quantification and statistical analysis results to Excel format.

Single Responsibility: Only handles quantification-specific Excel export.
Implements IQuantificationExporter interface.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

import pandas as pd
import numpy as np

from ...interfaces.quantification import IQuantificationExporter
from ...domain.models import (
    QuantificationResult,
    QuantifiedPeak,
    StatisticalAnalysisResult,
    StatisticalTestResult,
    TukeyHSDComparison,
)
from ...config.quantification_config import StatisticalConfig

logger = logging.getLogger(__name__)


class QuantificationExcelExporter(IQuantificationExporter):
    """
    Exports quantification results and statistical analysis to an Excel
    workbook.

    The workbook contains two sheets:

    - **Summary**: one row per compound / dose / enzyme / time combination
      with mean, SD, N, and individual replicate concentrations.
    - **Tukey_HSD**: one row per pairwise comparison with mean difference,
      adjusted p-value, and significance annotation.

    Parameters
    ----------
    config : StatisticalConfig
        Provides the canonical dose order, enzyme conditions, and time
        points used for iterating over experimental groups.
    """

    def __init__(self, config: StatisticalConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def export(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_path: Path,
    ) -> Path:
        """
        Write the Excel workbook.

        Parameters
        ----------
        quant_result : QuantificationResult
            Quantified peaks for all samples.
        stat_result : StatisticalAnalysisResult or None
            Statistical test results.  If ``None`` the Tukey_HSD sheet
            will still be created but will be empty.
        output_path : Path
            Destination file path.  The suffix is forced to ``.xlsx``.

        Returns
        -------
        Path
            The path of the written file.
        """
        output_path = Path(output_path)
        if output_path.suffix.lower() != '.xlsx':
            output_path = output_path.with_suffix('.xlsx')
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary_df = self._build_summary(quant_result)
        tukey_df = self._build_tukey_hsd(stat_result)

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            tukey_df.to_excel(writer, sheet_name='Tukey_HSD', index=False)

        logger.info("Quantification Excel exported: %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        quant_result: QuantificationResult,
    ) -> pd.DataFrame:
        """
        Build the Summary sheet dataframe.

        Iterates over every compound x dose x enzyme x time combination
        defined by the configuration.  For each group the mean, SD, N,
        and each individual replicate concentration are reported.
        """
        rows: List[Dict] = []

        compound_names = quant_result.compound_names
        doses = self._config.dose_order
        enzymes = self._config.enzyme_conditions
        time_points = self._config.time_points

        # Determine the maximum number of replicates across all groups
        # so we can create a fixed set of "Rep_1", "Rep_2", ... columns.
        max_reps = 0
        for compound in compound_names:
            for dose in doses:
                for enz in enzymes:
                    for tp in time_points:
                        peaks = quant_result.get_by_conditions(
                            compound_name=compound,
                            enzyme=enz,
                            time_h=tp,
                            cofactor_dose=dose,
                        )
                        if len(peaks) > max_reps:
                            max_reps = len(peaks)

        # Ensure at least one replicate column even when there is no data
        max_reps = max(max_reps, 1)

        for compound in compound_names:
            for dose in doses:
                for enz in enzymes:
                    for tp in time_points:
                        peaks = quant_result.get_by_conditions(
                            compound_name=compound,
                            enzyme=enz,
                            time_h=tp,
                            cofactor_dose=dose,
                        )
                        concs = [qp.concentration_original for qp in peaks]

                        row: Dict = {
                            'Compound': compound,
                            'Dose': dose,
                            'Enzyme': enz,
                            'Time': tp,
                            'Mean': float(np.mean(concs)) if concs else np.nan,
                            'SD': (
                                float(np.std(concs, ddof=1))
                                if len(concs) > 1
                                else (0.0 if len(concs) == 1 else np.nan)
                            ),
                            'N': len(concs),
                        }

                        # Add individual replicate columns
                        for r_idx in range(max_reps):
                            col_name = f'Rep_{r_idx + 1}'
                            row[col_name] = concs[r_idx] if r_idx < len(concs) else np.nan

                        rows.append(row)

        return pd.DataFrame(rows)

    @staticmethod
    def _build_tukey_hsd(
        stat_result: Optional[StatisticalAnalysisResult],
    ) -> pd.DataFrame:
        """
        Build the Tukey_HSD sheet dataframe.

        One row per pairwise comparison across all test results.
        """
        if stat_result is None or not stat_result.test_results:
            return pd.DataFrame(
                columns=[
                    'Compound', 'Enzyme', 'Time',
                    'Group1', 'Group2',
                    'Mean_Diff', 'p_adjusted', 'Significance',
                ]
            )

        rows: List[Dict] = []

        for test in stat_result.test_results:
            for comp in test.pairwise_comparisons:
                rows.append({
                    'Compound': test.compound_name,
                    'Enzyme': test.enzyme,
                    'Time': test.time_h,
                    'Group1': comp.group1_name,
                    'Group2': comp.group2_name,
                    'Mean_Diff': round(comp.mean_difference, 6),
                    'p_adjusted': round(comp.p_adjusted, 6),
                    'Significance': comp.significance,
                })

        return pd.DataFrame(rows)
