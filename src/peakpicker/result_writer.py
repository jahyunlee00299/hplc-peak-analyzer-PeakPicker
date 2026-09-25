"""
result_writer.py — Excel export and chromatogram overlay plotting.

SRP: ExcelWriter handles Excel output only.
     OverlayPlotter handles PNG overlay output only.
"""
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .models import CompoundMethod, SampleMeta
from .chromatogram_io import SignalFileResolver, ChromatogramParser
from .peak_quantifier import PeakQuantifier


class ExcelWriter:
    """Saves quantification DataFrame to a multi-sheet Excel workbook."""

    def write(
        self,
        df: pd.DataFrame,
        output_dir: Path,
        experiment_id: str,
    ) -> Path:
        """
        Writes All_Results, Conc_Pivot, Area_Pivot, and QC_Warnings sheets.
        Returns the path of the written file.
        """
        xlsx_path = output_dir / f"{experiment_id}_quant.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="All_Results", index=False)

            pivot_conc = df.pivot_table(
                index="sample_id", columns="compound",
                values="conc_mM", aggfunc="first",
            )
            pivot_conc.to_excel(writer, sheet_name="Conc_Pivot")

            pivot_area = df.pivot_table(
                index="sample_id", columns="compound",
                values="area_nRIU_s", aggfunc="first",
            )
            pivot_area.to_excel(writer, sheet_name="Area_Pivot")

            qc_df = df[df["qc_flag"] != ""]
            if not qc_df.empty:
                qc_df.to_excel(writer, sheet_name="QC_Warnings", index=False)

        print(f"  Excel saved: {xlsx_path}")
        return xlsx_path


class OverlayPlotter:
    """Saves a chromatogram overlay PNG for all samples."""

    def __init__(
        self,
        compounds: List[CompoundMethod],
        resolver: SignalFileResolver,
        loader: ChromatogramParser,
        quantifier: PeakQuantifier,
    ):
        self._compounds = compounds
        self._resolver = resolver
        self._loader = loader
        self._quantifier = quantifier

    def plot(
        self,
        samples: List[SampleMeta],
        output_dir: Path,
        experiment_id: str,
    ) -> Path:
        """Render overlay PNG and return its path."""
        fig, ax = plt.subplots(figsize=(14, 6))

        cmap = plt.cm.tab20
        n = max(len(samples), 1)
        colors = [cmap(i / n) for i in range(n)]

        for i, sample in enumerate(samples):
            ch_path = self._resolver.resolve(sample.folder)
            if not ch_path.exists():
                continue
            try:
                time, raw_sig = self._loader.load(ch_path)
                sig = self._quantifier.smooth(raw_sig)
                sig = self._quantifier.apply_trim(time, sig)
                ls = "--" if sample.is_ne else "-"
                lw = 0.8 if sample.is_ne else 1.2
                ax.plot(
                    time, sig,
                    color=colors[i], linestyle=ls, linewidth=lw,
                    label=sample.sample_id[:35], alpha=0.8,
                )
            except Exception:
                pass

        ax.autoscale(enable=True, axis="y")
        ylims = ax.get_ylim()
        y_top = ylims[1] if ylims[1] != 0 else 1000

        for cmpd in self._compounds:
            lo, hi = cmpd.rt_window
            ax.axvspan(lo, hi, alpha=0.10, color=cmpd.color, zorder=0)
            ax.text(
                (lo + hi) / 2, y_top * 0.92,
                cmpd.name, ha="center", fontsize=7, color="#444", rotation=90,
            )

        ax.set_xlim(5, 20)
        ax.set_xlabel("Retention Time (min)")
        ax.set_ylabel("RID Signal (nRIU)")
        ax.set_title(f"{experiment_id} — Chromatogram Overlay")
        ax.legend(fontsize=5, ncol=2, loc="upper right")
        ax.grid(True, alpha=0.2)

        plt.tight_layout()
        png_path = output_dir / f"{experiment_id}_overlay.png"
        plt.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Overlay PNG: {png_path}")
        return png_path
