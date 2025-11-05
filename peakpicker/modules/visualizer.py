"""
Chromatogram visualization module
"""

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np
from typing import Optional, Tuple


class ChromatogramVisualizer:
    """Visualize chromatography data"""

    def __init__(self, figsize: Tuple[int, int] = (12, 6)):
        """
        Initialize visualizer

        Args:
            figsize: Figure size (width, height) in inches
        """
        self.figsize = figsize
        self.fig = None
        self.ax = None

    def plot_chromatogram(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        title: str = "Chromatogram",
        xlabel: str = "Retention Time (min)",
        ylabel: str = "Intensity",
        color: str = "blue",
        linewidth: float = 1.0,
        grid: bool = True,
    ) -> matplotlib.figure.Figure:
        """
        Plot chromatogram

        Args:
            time: Time/retention time array
            intensity: Intensity/signal array
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            color: Line color
            linewidth: Line width
            grid: Show grid

        Returns:
            Matplotlib figure object
        """
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=self.figsize)

        # Plot chromatogram
        self.ax.plot(time, intensity, color=color, linewidth=linewidth)

        # Set labels and title
        self.ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
        self.ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
        self.ax.set_title(title, fontsize=14, fontweight='bold')

        # Grid
        if grid:
            self.ax.grid(True, alpha=0.3, linestyle='--')

        # Format
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

        # Tight layout
        plt.tight_layout()

        return self.fig

    def plot_with_baseline(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        baseline: Optional[np.ndarray] = None,
        title: str = "Chromatogram with Baseline",
    ) -> matplotlib.figure.Figure:
        """
        Plot chromatogram with baseline

        Args:
            time: Time array
            intensity: Intensity array
            baseline: Baseline array (optional)
            title: Plot title

        Returns:
            Matplotlib figure object
        """
        self.fig, self.ax = plt.subplots(figsize=self.figsize)

        # Plot chromatogram
        self.ax.plot(time, intensity, color='blue', linewidth=1.0, label='Signal')

        # Plot baseline if provided
        if baseline is not None:
            self.ax.plot(time, baseline, color='red', linewidth=1.5,
                        linestyle='--', label='Baseline')
            self.ax.legend(loc='upper right')

        # Set labels
        self.ax.set_xlabel('Retention Time (min)', fontsize=12, fontweight='bold')
        self.ax.set_ylabel('Intensity', fontsize=12, fontweight='bold')
        self.ax.set_title(title, fontsize=14, fontweight='bold')

        # Grid
        self.ax.grid(True, alpha=0.3, linestyle='--')

        # Format
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

        plt.tight_layout()

        return self.fig

    def plot_interactive_region(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        time_range: Optional[Tuple[float, float]] = None,
        title: str = "Chromatogram - Zoomed View",
    ) -> matplotlib.figure.Figure:
        """
        Plot specific time range of chromatogram

        Args:
            time: Time array
            intensity: Intensity array
            time_range: (start_time, end_time) to display
            title: Plot title

        Returns:
            Matplotlib figure object
        """
        self.fig, self.ax = plt.subplots(figsize=self.figsize)

        # Apply time range filter if specified
        if time_range is not None:
            mask = (time >= time_range[0]) & (time <= time_range[1])
            time_plot = time[mask]
            intensity_plot = intensity[mask]
        else:
            time_plot = time
            intensity_plot = intensity

        # Plot
        self.ax.plot(time_plot, intensity_plot, color='blue', linewidth=1.5)

        # Labels
        self.ax.set_xlabel('Retention Time (min)', fontsize=12, fontweight='bold')
        self.ax.set_ylabel('Intensity', fontsize=12, fontweight='bold')
        self.ax.set_title(title, fontsize=14, fontweight='bold')

        # Grid
        self.ax.grid(True, alpha=0.3, linestyle='--')

        # Format
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

        plt.tight_layout()

        return self.fig

    def add_peak_markers(
        self,
        peak_times: np.ndarray,
        peak_intensities: np.ndarray,
        marker_style: str = 'ro',
        marker_size: int = 8,
    ):
        """
        Add peak markers to existing plot

        Args:
            peak_times: Array of peak retention times
            peak_intensities: Array of peak intensities
            marker_style: Matplotlib marker style
            marker_size: Marker size
        """
        if self.ax is None:
            raise ValueError("No active plot. Call plot_chromatogram first.")

        self.ax.plot(peak_times, peak_intensities, marker_style,
                    markersize=marker_size, label='Detected Peaks')
        self.ax.legend(loc='upper right')

    def save_figure(self, filename: str, dpi: int = 300):
        """
        Save current figure to file

        Args:
            filename: Output filename
            dpi: Resolution in dots per inch
        """
        if self.fig is None:
            raise ValueError("No figure to save")

        self.fig.savefig(filename, dpi=dpi, bbox_inches='tight')

    def clear(self):
        """Clear current figure"""
        if self.fig is not None:
            plt.close(self.fig)
            self.fig = None
            self.ax = None
