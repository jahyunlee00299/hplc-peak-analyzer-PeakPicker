"""
Plot Exporter
=============

Exports chromatogram visualizations with automatic Y-axis break support.
Interface Segregation: Separate from data exporters.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

from ...interfaces import IPlotExporter
from ...domain import Peak

# Import broken axis components
try:
    from ..visualization.broken_axis_plotter import (
        PeakHeightAnalyzer, BreakStrategy, BreakPoint,
        BROKENAXES_AVAILABLE
    )
    if BROKENAXES_AVAILABLE:
        from brokenaxes import brokenaxes
except ImportError:
    BROKENAXES_AVAILABLE = False


class ChromatogramPlotExporter(IPlotExporter):
    """
    Exports chromatogram plots with peak annotations.

    Single Responsibility: Only handles plot export.
    """

    def __init__(
        self,
        output_dir: Path = None,
        default_figsize: tuple = (14, 7),
        default_dpi: int = 300,
        use_auto_break: bool = True,
        min_gap_ratio: float = 2.5
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
        use_auto_break : bool, default=True
            Automatically apply Y-axis break when peak height differences are large
        min_gap_ratio : float, default=2.5
            Minimum ratio between peak heights to apply break
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_figsize = default_figsize
        self.default_dpi = default_dpi
        self.use_auto_break = use_auto_break

        # Initialize peak height analyzer for automatic break detection
        if BROKENAXES_AVAILABLE:
            self.analyzer = PeakHeightAnalyzer(
                min_gap_ratio=min_gap_ratio,
                margin_factor=0.15
            )
        else:
            self.analyzer = None

    def _calculate_break_point(
        self,
        intensity: np.ndarray,
        peak_heights: np.ndarray = None
    ) -> Optional[BreakPoint]:
        """
        Calculate optimal break point for the signal.

        Parameters
        ----------
        intensity : np.ndarray
            Signal intensity array
        peak_heights : np.ndarray, optional
            Heights of detected peaks

        Returns
        -------
        BreakPoint or None
            Break point if break should be applied, None otherwise
        """
        if not self.use_auto_break or not BROKENAXES_AVAILABLE or self.analyzer is None:
            return None

        return self.analyzer.find_optimal_break_point(
            intensity,
            peak_heights=peak_heights,
            strategy=BreakStrategy.AUTO,
            include_negative=True
        )

    def export_chromatogram(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        peaks: List[Peak],
        output_path: Path,
        title: str = None,
        use_break: bool = None,
        **options
    ) -> Path:
        """
        Export chromatogram plot with peaks and optional Y-axis break.

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
        use_break : bool, optional
            Override auto break setting (None uses class default)
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

        # Determine if break should be used
        apply_break = use_break if use_break is not None else self.use_auto_break

        # Extract peak heights for break calculation
        peak_heights = np.array([p.height for p in peaks]) if peaks else None

        # Calculate break point
        break_point = None
        if apply_break and BROKENAXES_AVAILABLE and peak_heights is not None and len(peak_heights) > 1:
            break_point = self._calculate_break_point(intensity, peak_heights)

        fig = plt.figure(figsize=figsize)

        # Use brokenaxes if break point is calculated
        if break_point is not None:
            bax = brokenaxes(ylims=break_point.ylims, hspace=0.05, despine=False)

            # Plot chromatogram
            bax.plot(time, intensity, 'b-', linewidth=0.8, alpha=0.8, label=f'{detector_type} Signal')

            # Mark peaks
            for i, peak in enumerate(peaks, 1):
                peak_y = intensity[peak.index]

                # Peak marker
                bax.scatter([peak.rt], [peak_y], color='red', s=36, zorder=5)

                # Shade area (brokenaxes doesn't support fill_between well, use plot instead)
                if show_area:
                    mask = (time >= peak.rt_start) & (time <= peak.rt_end)
                    if np.any(mask):
                        bax.fill_between(
                            time[mask],
                            np.zeros(np.sum(mask)),
                            intensity[mask],
                            alpha=0.2,
                            color='green',
                            label='Peak Area' if i == 1 else ''
                        )

            # Labels
            bax.set_xlabel('Retention Time (min)', fontsize=12)
            bax.set_ylabel(f'{detector_type} Response', fontsize=12)

            if title:
                bax.set_title(f'{title}\n[Y-axis break applied]', fontsize=14, fontweight='bold')
            else:
                bax.set_title(f'Chromatogram - {len(peaks)} peaks detected\n[Y-axis break]', fontsize=14)

            bax.legend(loc='best')
        else:
            ax = fig.add_subplot(111)

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
        use_break: bool = None,
        peak_heights: np.ndarray = None,
        **options
    ) -> Path:
        """
        Export baseline comparison plot with optional Y-axis break.

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
        use_break : bool, optional
            Override auto break setting (None uses class default)
        peak_heights : np.ndarray, optional
            Peak heights for break calculation
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

        # Determine if break should be used
        apply_break = use_break if use_break is not None else self.use_auto_break

        # Calculate break point for original signal
        break_point = None
        if apply_break and BROKENAXES_AVAILABLE and peak_heights is not None and len(peak_heights) > 1:
            break_point = self._calculate_break_point(intensity, peak_heights)

        corrected = intensity - baseline

        # Calculate break point for corrected signal
        corrected_break = None
        if apply_break and BROKENAXES_AVAILABLE and peak_heights is not None and len(peak_heights) > 1:
            corrected_break = self._calculate_break_point(corrected, peak_heights)

        fig = plt.figure(figsize=figsize)
        gs = GridSpec(2, 1, figure=fig, hspace=0.3)

        # === Panel 1: Original with baseline ===
        if break_point is not None:
            bax1 = brokenaxes(ylims=break_point.ylims, subplot_spec=gs[0], hspace=0.05, despine=False)
            bax1.plot(time, intensity, 'b-', label='Original', alpha=0.8, linewidth=1)
            bax1.plot(time, baseline, 'r--', label='Baseline', alpha=0.8, linewidth=1.5)
            title_text = (title or 'Baseline Correction') + '\n[Y-axis break applied]'
            bax1.set_title(title_text, fontsize=12, fontweight='bold')
            bax1.legend(loc='best')
            bax1.set_ylabel('Intensity', fontsize=11)
        else:
            ax1 = fig.add_subplot(gs[0])
            ax1.plot(time, intensity, 'b-', label='Original', alpha=0.8)
            ax1.plot(time, baseline, 'r--', label='Baseline', alpha=0.8)
            ax1.set_title(title or 'Baseline Correction', fontsize=12, fontweight='bold')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.set_ylabel('Intensity', fontsize=11)

        # === Panel 2: Corrected signal ===
        if corrected_break is not None:
            bax2 = brokenaxes(ylims=corrected_break.ylims, subplot_spec=gs[1], hspace=0.05, despine=False)
            bax2.plot(time, corrected, 'g-', label='Corrected', alpha=0.8, linewidth=1)
            bax2.axhline(y=0, color='k', linestyle='-', alpha=0.3)
            bax2.set_xlabel('Time (min)', fontsize=11)
            bax2.set_ylabel('Corrected Intensity', fontsize=11)
            bax2.legend(loc='best')
        else:
            ax2 = fig.add_subplot(gs[1])
            ax2.plot(time, corrected, 'g-', label='Corrected', alpha=0.8)
            ax2.axhline(y=0, color='k', linestyle='-', alpha=0.3)
            ax2.set_xlabel('Time (min)', fontsize=11)
            ax2.set_ylabel('Corrected Intensity', fontsize=11)
            ax2.legend()
            ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close()

        return output_path
