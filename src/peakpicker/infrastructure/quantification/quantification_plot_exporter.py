"""
Quantification Plot Exporter
==============================

Exports quantification visualizations: bar charts with significance brackets,
time course line plots, and enzyme comparison charts.

Single Responsibility: Only handles quantification plot generation and export.
Implements IQuantificationPlotExporter interface.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['axes.unicode_minus'] = False

from ...interfaces.quantification import IQuantificationPlotExporter
from ...domain.models import (
    QuantificationResult,
    QuantifiedPeak,
    StatisticalAnalysisResult,
    StatisticalTestResult,
    TukeyHSDComparison,
)
from ...config.quantification_config import VisualizationConfig, StatisticalConfig

logger = logging.getLogger(__name__)


class QuantificationPlotExporter(IQuantificationPlotExporter):
    """
    Exports quantification result visualizations.

    Produces three chart types:
    - Bar chart: mean concentration per dose with error bars, individual
      data points, and Tukey HSD significance brackets.
    - Time course: line plot of mean concentration across time points for
      every dose x enzyme combination.
    - Comparison chart: side-by-side RO vs RS bars for a given compound
      and time point.

    Parameters
    ----------
    config : VisualizationConfig
        Visual styling and layout parameters.
    stat_config : StatisticalConfig
        Dose order, enzyme conditions, and time points.
    """

    def __init__(
        self,
        config: VisualizationConfig,
        stat_config: StatisticalConfig,
    ) -> None:
        self._config = config
        self._stat_config = stat_config

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def export_bar_chart(
        self,
        quant_result: QuantificationResult,
        stat_result: Optional[StatisticalAnalysisResult],
        output_path: Path,
        compound_name: str,
        enzyme: str,
        time_h: str,
    ) -> Path:
        """
        Export a bar chart for one compound / enzyme / time point.

        Each bar represents a cofactor dose.  Error bars show +/- 1 SD.
        Individual replicates are overlaid as jittered points.
        Significant pairwise differences (Tukey HSD) are shown as brackets.

        Returns the *Path* of the saved image file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doses = self._stat_config.dose_order
        colors = [self._config.dose_colors.get(d, '#888888') for d in doses]

        # Gather per-dose statistics
        means: List[float] = []
        sds: List[float] = []
        ns: List[int] = []
        individual_pts: List[List[float]] = []

        for dose in doses:
            peaks = quant_result.get_by_conditions(
                compound_name=compound_name,
                enzyme=enzyme,
                time_h=time_h,
                cofactor_dose=dose,
            )
            concs = [qp.concentration_original for qp in peaks]
            if concs:
                means.append(float(np.mean(concs)))
                sds.append(float(np.std(concs, ddof=1)) if len(concs) > 1 else 0.0)
                ns.append(len(concs))
                individual_pts.append(concs)
            else:
                means.append(0.0)
                sds.append(0.0)
                ns.append(0)
                individual_pts.append([])

        # Build figure
        fig, ax = plt.subplots(figsize=self._config.figsize, dpi=self._config.dpi)
        x = np.arange(len(doses))

        bars = ax.bar(
            x, means,
            yerr=sds,
            capsize=self._config.error_bar_capsize,
            width=0.6,
            color=colors,
            edgecolor='black',
            linewidth=1,
            alpha=0.85,
            error_kw={'elinewidth': 1.5, 'capthick': 1.5},
        )

        # Individual data points
        if self._config.show_individual_points:
            for i, pts in enumerate(individual_pts):
                if not pts:
                    continue
                jitter = np.random.uniform(
                    -self._config.jitter_width,
                    self._config.jitter_width,
                    size=len(pts),
                )
                ax.scatter(
                    np.full(len(pts), i) + jitter,
                    pts,
                    color='black', s=30, zorder=5, alpha=0.6,
                    edgecolors='white', linewidths=0.5,
                )

        # Mean value labels
        if self._config.show_mean_labels:
            for i, (m, s) in enumerate(zip(means, sds)):
                if ns[i] > 0:
                    ax.text(
                        i, m + s + max(means) * 0.01,
                        f'{m:.2f}',
                        ha='center', va='bottom',
                        fontsize=9, fontweight='bold',
                    )

        # Significance brackets
        if self._config.show_significance_brackets and stat_result is not None:
            sig_pairs = stat_result.get_significant_pairs(compound_name, enzyme, time_h)
            self._draw_significance_brackets(ax, sig_pairs, doses, means, sds)

        # NC reference line (initial substrate concentration)
        if self._config.show_nc_reference_line:
            nc_mean = quant_result.get_nc_mean(compound_name)
            if nc_mean is not None:
                ax.axhline(
                    y=nc_mean,
                    linestyle=self._config.nc_line_style,
                    color=self._config.nc_line_color,
                    linewidth=self._config.nc_line_width,
                    label=self._config.nc_label,
                    zorder=1,
                )

        # Axes & labels
        ax.set_xticks(x)
        ax.set_xticklabels(doses, fontsize=self._config.tick_fontsize)
        ax.set_ylabel(
            'Concentration (g/L)',
            fontsize=self._config.label_fontsize,
            fontweight='bold',
        )
        ax.set_xlabel(
            'Cofactor Dose',
            fontsize=self._config.label_fontsize,
            fontweight='bold',
        )
        ax.set_title(
            f'{compound_name} - {enzyme} at {time_h}',
            fontsize=self._config.title_fontsize,
            fontweight='bold',
        )
        ax.tick_params(axis='y', labelsize=self._config.tick_fontsize)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        # Only show legend if there are labeled artists (e.g. NC reference line)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(fontsize=9, loc='upper right')

        plt.tight_layout()
        plt.savefig(output_path, dpi=self._config.dpi, bbox_inches='tight')
        plt.close(fig)

        logger.info("Bar chart saved: %s", output_path)
        return output_path

    def export_time_course(
        self,
        quant_result: QuantificationResult,
        output_path: Path,
        compound_name: str,
    ) -> Path:
        """
        Export a time-course line plot for one compound.

        One line per dose x enzyme combination.  X-axis is numeric hours
        (from ``time_numeric_map``).  Error bars show +/- 1 SD.

        Returns the *Path* of the saved image file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doses = self._stat_config.dose_order
        enzymes = self._stat_config.enzyme_conditions
        time_points = self._stat_config.time_points
        time_vals = [self._config.time_numeric_map.get(tp, 0.0) for tp in time_points]

        # Prepend NC as t=0 starting point
        nc_t0_vals = {}  # {compound_name: nc_mean_concentration}
        nc_mean = quant_result.get_nc_mean(compound_name)
        if nc_mean is not None:
            time_vals = [0.0] + time_vals

        enzyme_styles = {
            'RO': ('-', 'o'),
            'RS': ('--', 's'),
        }

        fig, ax = plt.subplots(figsize=self._config.figsize, dpi=self._config.dpi)

        for dose in doses:
            dose_color = self._config.dose_colors.get(dose, '#888888')
            for enz in enzymes:
                ls, marker = enzyme_styles.get(enz, ('-', 'o'))
                means: List[float] = []
                stds: List[float] = []

                # Prepend NC t=0 if available
                if nc_mean is not None:
                    means.append(nc_mean)
                    stds.append(0.0)  # Single NC sample, no SD

                for tp in time_points:
                    peaks = quant_result.get_by_conditions(
                        compound_name=compound_name,
                        enzyme=enz,
                        time_h=tp,
                        cofactor_dose=dose,
                    )
                    concs = [qp.concentration_original for qp in peaks]
                    if concs:
                        means.append(float(np.mean(concs)))
                        stds.append(
                            float(np.std(concs, ddof=1)) if len(concs) > 1 else 0.0
                        )
                    else:
                        means.append(0.0)
                        stds.append(0.0)

                ax.errorbar(
                    time_vals,
                    means,
                    yerr=stds,
                    marker=marker,
                    linestyle=ls,
                    linewidth=2,
                    markersize=7,
                    capsize=4,
                    label=f'{dose}_{enz}',
                    color=dose_color,
                )

        # Axes & labels
        if nc_mean is not None:
            tick_labels = ['0H'] + list(time_points)
        else:
            tick_labels = list(time_points)
        ax.set_xticks(time_vals)
        ax.set_xticklabels(tick_labels, fontsize=self._config.tick_fontsize)
        ax.set_xlabel(
            'Time (hours)',
            fontsize=self._config.label_fontsize,
            fontweight='bold',
        )
        ax.set_ylabel(
            'Concentration (g/L)',
            fontsize=self._config.label_fontsize,
            fontweight='bold',
        )
        ax.set_title(
            f'{compound_name} - Time Course',
            fontsize=self._config.title_fontsize,
            fontweight='bold',
        )
        ax.tick_params(axis='y', labelsize=self._config.tick_fontsize)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        # Legend outside the plot area
        ax.legend(
            bbox_to_anchor=(1.05, 1),
            loc='upper left',
            fontsize=9,
            framealpha=0.9,
        )

        plt.tight_layout()
        plt.savefig(output_path, dpi=self._config.dpi, bbox_inches='tight')
        plt.close(fig)

        logger.info("Time course saved: %s", output_path)
        return output_path

    def export_comparison_chart(
        self,
        quant_result: QuantificationResult,
        output_path: Path,
        compound_name: str,
        time_h: str,
    ) -> Path:
        """
        Export a side-by-side comparison chart (RO vs RS) for one compound /
        time point.

        Grouped bars: each dose has an RO bar and an RS bar.

        Returns the *Path* of the saved image file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doses = self._stat_config.dose_order
        enzymes = self._stat_config.enzyme_conditions
        x = np.arange(len(doses))
        width = 0.35

        fig, ax = plt.subplots(figsize=self._config.figsize, dpi=self._config.dpi)

        for offset, enz in zip([-width / 2, width / 2], enzymes):
            enz_color = self._config.enzyme_colors.get(enz, '#888888')
            means: List[float] = []
            sds: List[float] = []

            for dose in doses:
                peaks = quant_result.get_by_conditions(
                    compound_name=compound_name,
                    enzyme=enz,
                    time_h=time_h,
                    cofactor_dose=dose,
                )
                concs = [qp.concentration_original for qp in peaks]
                if concs:
                    means.append(float(np.mean(concs)))
                    sds.append(
                        float(np.std(concs, ddof=1)) if len(concs) > 1 else 0.0
                    )
                else:
                    means.append(0.0)
                    sds.append(0.0)

            ax.bar(
                x + offset,
                means,
                width,
                yerr=sds,
                capsize=4,
                label=enz,
                color=enz_color,
                edgecolor='black',
                alpha=0.85,
                error_kw={'elinewidth': 1.2, 'capthick': 1.2},
            )

            # Individual data points
            if self._config.show_individual_points:
                for i, dose in enumerate(doses):
                    peaks = quant_result.get_by_conditions(
                        compound_name=compound_name,
                        enzyme=enz,
                        time_h=time_h,
                        cofactor_dose=dose,
                    )
                    pts = [qp.concentration_original for qp in peaks]
                    if pts:
                        jitter = np.random.uniform(
                            -self._config.jitter_width * 0.5,
                            self._config.jitter_width * 0.5,
                            size=len(pts),
                        )
                        ax.scatter(
                            np.full(len(pts), x[i] + offset) + jitter,
                            pts,
                            color='black', s=25, zorder=5, alpha=0.6,
                            edgecolors='white', linewidths=0.5,
                        )

        # Axes & labels
        ax.set_xticks(x)
        ax.set_xticklabels(doses, fontsize=self._config.tick_fontsize)
        ax.set_xlabel(
            'Cofactor Dose',
            fontsize=self._config.label_fontsize,
            fontweight='bold',
        )
        ax.set_ylabel(
            'Concentration (g/L)',
            fontsize=self._config.label_fontsize,
            fontweight='bold',
        )
        ax.set_title(
            f'{compound_name} - RO vs RS at {time_h}',
            fontsize=self._config.title_fontsize,
            fontweight='bold',
        )
        ax.tick_params(axis='y', labelsize=self._config.tick_fontsize)
        ax.legend(fontsize=self._config.label_fontsize)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        plt.tight_layout()
        plt.savefig(output_path, dpi=self._config.dpi, bbox_inches='tight')
        plt.close(fig)

        logger.info("Comparison chart saved: %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _add_significance_bracket(
        ax: plt.Axes,
        x1: float,
        x2: float,
        y: float,
        sig_text: str,
        h: float = 0.02,
        color: str = 'black',
    ) -> None:
        """Draw a single significance bracket between two bar positions."""
        if sig_text == 'ns':
            return
        y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
        tip = y_range * h
        ax.plot(
            [x1, x1, x2, x2],
            [y, y + tip, y + tip, y],
            lw=1.2, color=color,
        )
        ax.text(
            (x1 + x2) / 2, y + tip, sig_text,
            ha='center', va='bottom',
            fontsize=9, fontweight='bold', color=color,
        )

    def _draw_significance_brackets(
        self,
        ax: plt.Axes,
        sig_pairs: List[TukeyHSDComparison],
        doses: List[str],
        means: List[float],
        sds: List[float],
    ) -> None:
        """
        Draw significance brackets above bars for all significant pairs.

        Brackets are stacked vertically so they do not overlap.
        """
        if not sig_pairs:
            return

        dose_index = {d: i for i, d in enumerate(doses)}

        # Filter to pairs whose groups are actually in the dose list
        valid_pairs: List[TukeyHSDComparison] = []
        for comp in sig_pairs:
            if comp.group1_name in dose_index and comp.group2_name in dose_index:
                valid_pairs.append(comp)

        if not valid_pairs:
            return

        # Limit the number of brackets to avoid clutter
        valid_pairs = valid_pairs[: self._config.max_significance_brackets]

        # Sort by span width (narrow first) for nicer stacking
        valid_pairs.sort(
            key=lambda c: abs(
                dose_index[c.group2_name] - dose_index[c.group1_name]
            )
        )

        # Starting y for brackets: just above the tallest bar + sd
        y_max = max(
            (m + s) for m, s in zip(means, sds) if (m + s) > 0
        ) if any(m + s > 0 for m, s in zip(means, sds)) else 1.0
        bracket_y = y_max * 1.08
        bracket_step = y_max * 0.08

        for idx, comp in enumerate(valid_pairs):
            x1 = float(dose_index[comp.group1_name])
            x2 = float(dose_index[comp.group2_name])
            y = bracket_y + idx * bracket_step
            self._add_significance_bracket(ax, x1, x2, y, comp.significance)
