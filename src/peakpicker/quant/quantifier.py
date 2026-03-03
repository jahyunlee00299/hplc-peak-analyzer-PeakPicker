"""
Quantifier
==========

Applies a QuantMethod to AnalysisResults to produce concentration tables.

Usage
-----
::

    from peakpicker.quant import QuantMethod, Quantifier
    from peakpicker.application.workflow import WorkflowBuilder
    from pathlib import Path

    method = QuantMethod.from_yaml("methods/hpx87h_sugars.yaml")
    wf     = WorkflowBuilder().with_auto_reader() \
                              .with_arpls_baseline() \
                              .with_two_pass_peak_detector() \
                              .build()
    quant  = Quantifier(method, wf)

    # Single file
    row = quant.quantify_file(Path("sample.D"))

    # Batch
    df = quant.quantify_batch(list(Path("data/").glob("*.D")))
    df.to_excel("results.xlsx", index=False)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .method_config import CompoundDef, QuantMethod

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompoundResult:
    """Quantification result for one compound in one sample."""
    compound: str
    rt: float                       # detected RT
    area: float                     # raw peak area
    area_percent: float             # % of total chromatogram area
    concentration: Optional[float]  # None if no standard curve
    unit: str = "mM"
    note: str = ""


@dataclass
class SampleResult:
    """All compound results for one sample file."""
    filename: str
    sample_name: str
    compounds: List[CompoundResult] = field(default_factory=list)
    unassigned_peaks: int = 0       # peaks not matching any compound

    def get(self, compound_name: str) -> Optional[CompoundResult]:
        for c in self.compounds:
            if c.compound == compound_name:
                return c
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Quantifier
# ─────────────────────────────────────────────────────────────────────────────

class Quantifier:
    """
    Assigns detected peaks to compounds and applies standard curves.

    Parameters
    ----------
    method : QuantMethod
        Column/compound/standard curve definitions.
    workflow : AnalysisWorkflow
        Configured PeakPicker workflow (reader + baseline + detector).
    """

    def __init__(self, method: QuantMethod, workflow):
        self.method = method
        self.workflow = workflow

    # ── Public API ────────────────────────────────────────────────────────────

    def quantify_file(self, path: str | Path) -> SampleResult:
        """Analyze one file and return a SampleResult."""
        path = Path(path)
        result = self.workflow.analyze_file(path)
        return self._assign(path.name, result.chromatogram.sample_name, result.peaks)

    def quantify_batch(self, paths: List[str | Path]) -> "pd.DataFrame":
        """
        Analyze multiple files and return a wide-format DataFrame.

        Columns: filename, sample_name, <compound>_area, <compound>_area%,
                 <compound>_conc, ...
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required: pip install pandas")

        rows = []
        for p in sorted(paths):
            try:
                sr = self.quantify_file(p)
                row = self._to_row(sr)
                rows.append(row)
                logger.info("Quantified: %s", Path(p).name)
            except Exception as e:
                logger.warning("Failed to quantify %s: %s", p, e)
                rows.append({"filename": Path(p).name, "error": str(e)})

        df = pd.DataFrame(rows)
        return df

    # ── Internal ──────────────────────────────────────────────────────────────

    def _assign(self, filename: str, sample_name: str, peaks) -> SampleResult:
        sr = SampleResult(filename=filename, sample_name=sample_name)
        assigned_compound_names: set = set()

        for pk in peaks:
            cdef = self.method.find_compound(pk.rt)
            if cdef is None:
                sr.unassigned_peaks += 1
                continue

            # Select area based on compound's area_mode
            if cdef.area_mode == "left_half":
                used_area = pk.left_area
            elif cdef.area_mode == "right_half":
                used_area = pk.right_area
            else:
                used_area = pk.area

            # If multiple peaks match same compound window, keep the largest
            existing = sr.get(cdef.name)
            if existing is not None and existing.area >= used_area:
                continue
            if existing is not None:
                sr.compounds.remove(existing)

            sc = self.method.get_standard_curve(cdef.name)
            if sc is not None and not sc.is_fitted():
                sc.fit()
            conc = sc.predict(used_area) if sc is not None else None

            sr.compounds.append(CompoundResult(
                compound=cdef.name,
                rt=pk.rt,
                area=used_area,
                area_percent=pk.area_percent,
                concentration=conc,
                unit=cdef.unit,
                note=cdef.note,
            ))
            assigned_compound_names.add(cdef.name)

        # Fill missing compounds with None
        for cdef in self.method.compounds:
            if cdef.name not in assigned_compound_names:
                sr.compounds.append(CompoundResult(
                    compound=cdef.name,
                    rt=float("nan"),
                    area=0.0,
                    area_percent=0.0,
                    concentration=None,
                    unit=cdef.unit,
                    note="not detected",
                ))

        return sr

    def _to_row(self, sr: SampleResult) -> dict:
        row: dict = {"filename": sr.filename, "sample_name": sr.sample_name}
        for cr in sorted(sr.compounds, key=lambda c: c.rt if not np.isnan(c.rt) else 999):
            prefix = cr.compound
            row[f"{prefix}_rt"]       = round(cr.rt, 3) if not np.isnan(cr.rt) else None
            row[f"{prefix}_area"]     = round(cr.area, 1) if cr.area else None
            row[f"{prefix}_area%"]    = round(cr.area_percent, 2) if cr.area_percent else None
            if cr.concentration is not None:
                row[f"{prefix}_conc({cr.unit})"] = round(cr.concentration, 4)
        row["unassigned_peaks"] = sr.unassigned_peaks
        return row
