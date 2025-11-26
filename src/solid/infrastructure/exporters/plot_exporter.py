"""
Plot Exporter
=============

Exports chromatogram visualizations.
Interface Segregation: Separate from data exporters.
"""

from pathlib import Path
from typing import List, Optional

import numpy as np
import matplotlib.pyplot as plt

from ...interfaces import IPlotExporter
from ...domain import Peak


class ChromatogramPlotExporter(IPlotExporter):
    """
    Exports chromatogram plots with peak annotations.

    Single Responsibility: Only handles plot export.
    """

    def __init__(
        self,
        output_dir: Path = None,
        default_figsize: tuple = (14, 7),
        default_dpi: int = 300
    ):
        """
        Initialize exporter.

        Parameters
        ----------
        output_dir : Path, optional
            Default output directory
        default_figsize : tuple
            Default figure size
        default_dpi : int
            Default DPI for saved figures
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_figsize = default_figsize
        self.default_dpi = default_dpi

    def export_chromatogram(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        peaks: List[Peak],
        output_path: Path,
        title: str = None,
        **options
    ) -> Path:
        """
        Export chromatogram plot with peaks.

        Parameters
        ----------
        time : np.ndarray
            Time array
        intensity : np.ndarray
            Intensity array
        peaks : List[Peak]
            Detected peaks to annotate
        output_path : Path
            Output file path
        title : str, optional
            Plot title
        **options
            Plot options:
            - figsize: Figure size
            - dpi: Resolution
            - detector_type: Detector name for axis label
            - show_area: Whether to shade peak areas

        Returns
        -------
        Path
            Path to created file
        """
        output_path = Path(output_path)

        figsize = options.get('figsize', self.default_figsize)
        dpi = options.get('dpi', self.default_dpi)
        detector_type = options.get('detector_type', 'Signal')
        show_area = options.get('show_area', True)

        fig, ax = plt.subplots(figsize=figsize)

        # Plot chromatogram
        ax.plot(time, intensity, 'b-', linewidth=0.8, alpha=0.8, label=f'{detector_type} Signal')

        # Mark peaks
        for i, peak in enumerate(peaks, 1):
            peak_y = intensity[peak.index]

            # Peak marker
            ax.plot(peak.rt, peak_y, 'ro', markersize=6, zorder=5)

            # Annotate (limit to avoid clutter)
            if i <= 10 or peak.height > np.percentile([p.height for p in peaks], 75):
                ax.annotate(
                    f'#{i}\nRT: {peak.rt:.2f}',
                    xy=(peak.rt, peak_y),
                    xytext=(0, 20),
                    textcoords='offset points',
                    ha='center',
                    fontsize=7,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', lw=0.5)
                )

            # Shade area
            if show_area:
                mask = (time >= peak.rt_start) & (time <= peak.rt_end)
                if np.any(mask):
                    ax.fill_between(
                        time[mask],
                        0,
                        intensity[mask],
                        alpha=0.2,
                        color='green',
                        label='Peak Area' if i == 1 else ''
                    )

        # Labels
        ax.set_xlabel('Retention Time (min)', fontsize=12, fontweight='bold')
        ax.set_ylabel(f'{detector_type} Response', fontsize=12, fontweight='bold')

        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')
        else:
            ax.set_title(f'Chromatogram - {len(peaks)} peaks detected', fontsize=14)

        ax.grid(True, alpha=0.3, linestyle='--')

        # Legend (remove duplicates)
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper right')

        # Format y-axis
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))

        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close()

        return output_path

    def export_baseline_comparison(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        baseline: np.ndarray,
        output_path: Path,
        title: str = None,
        **options
    ) -> Path:
        """
        Export baseline comparison plot.

        Parameters
        ----------
        time : np.ndarray
            Time array
        intensity : np.ndarray
            Original intensity
        baseline : np.ndarray
            Baseline
        output_path : Path
            Output path
        title : str, optional
            Plot title
        **options
            Plot options

        Returns
        -------
        Path
            Path to created file
        """
        output_path = Path(output_path)
        figsize = options.get('figsize', self.default_figsize)
        dpi = options.get('dpi', self.default_dpi)

        fig, axes = plt.subplots(2, 1, figsize=figsize)

        # Original with baseline
        axes[0].plot(time, intensity, 'b-', label='Original', alpha=0.8)
        axes[0].plot(time, baseline, 'r--', label='Baseline', alpha=0.8)
        axes[0].set_title(title or 'Baseline Correction')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        axes[0].set_ylabel('Intensity')

        # Corrected
        corrected = intensity - baseline
        axes[1].plot(time, corrected, 'g-', label='Corrected', alpha=0.8)
        axes[1].axhline(y=0, color='k', linestyle='-', alpha=0.3)
        axes[1].set_xlabel('Time (min)')
        axes[1].set_ylabel('Corrected Intensity')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close()

        return output_path
