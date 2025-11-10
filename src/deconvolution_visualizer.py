"""
Peak Deconvolution Visualizer
==============================

Visualization tools for peak deconvolution results.

Author: PeakPicker Project
Date: 2025-11-10
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from peak_models import gaussian
from peak_deconvolution import DeconvolutionResult


class DeconvolutionVisualizer:
    """Visualizer for peak deconvolution results."""

    def __init__(self, dpi: int = 150, figure_size: Tuple[int, int] = (12, 8)):
        """
        Initialize visualizer.

        Parameters
        ----------
        dpi : int, default=150
            Resolution for saved figures
        figure_size : Tuple[int, int], default=(12, 8)
            Figure size in inches (width, height)
        """
        self.dpi = dpi
        self.figure_size = figure_size

    def plot_single_deconvolution(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        result: DeconvolutionResult,
        peak_start_idx: int,
        peak_end_idx: int,
        title: Optional[str] = None,
        save_path: Optional[Path] = None
    ) -> Figure:
        """
        Plot a single peak deconvolution result.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        result : DeconvolutionResult
            Deconvolution result
        peak_start_idx : int
            Peak start index
        peak_end_idx : int
            Peak end index
        title : str, optional
            Custom title for the plot
        save_path : Path, optional
            Path to save the figure

        Returns
        -------
        Figure
            Matplotlib figure object
        """
        # Extract peak region
        rt_peak = rt[peak_start_idx:peak_end_idx + 1]
        signal_peak = signal[peak_start_idx:peak_end_idx + 1]

        # Create figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.figure_size)

        # Plot 1: Original vs Fitted
        ax1.plot(rt_peak, signal_peak, 'b-', linewidth=2, label='Original Signal', alpha=0.7)

        if result.success:
            # Calculate fitted signal
            fitted_signal = np.zeros_like(rt_peak)
            for comp in result.components:
                fitted_signal += gaussian(rt_peak, comp.amplitude, comp.retention_time, comp.sigma)

            ax1.plot(rt_peak, fitted_signal, 'r-', linewidth=2, label='Fitted Signal')

            # Add residuals
            residuals = signal_peak - fitted_signal
            ax1.fill_between(rt_peak, fitted_signal, signal_peak, alpha=0.3, color='gray', label='Residuals')

        ax1.set_xlabel('Retention Time (min)', fontsize=11)
        ax1.set_ylabel('Intensity', fontsize=11)

        if title:
            ax1.set_title(title, fontsize=13, fontweight='bold')
        else:
            status = "Success" if result.success else "Failed"
            ax1.set_title(
                f'Peak Deconvolution: {result.method} (R²={result.fit_quality:.4f}) - {status}',
                fontsize=13, fontweight='bold'
            )

        ax1.legend(loc='best', fontsize=10)
        ax1.grid(True, alpha=0.3)

        # Plot 2: Individual components
        if result.success and result.n_components > 0:
            ax2.plot(rt_peak, signal_peak, 'gray', linewidth=1.5, label='Original', alpha=0.5)

            colors = ['red', 'green', 'blue', 'orange', 'purple', 'brown', 'pink']

            for i, comp in enumerate(result.components):
                component_signal = gaussian(rt_peak, comp.amplitude, comp.retention_time, comp.sigma)

                label = (f'Peak {i+1}: RT={comp.retention_time:.3f} min, '
                        f'Area={comp.area_percent:.1f}%')

                if comp.is_shoulder:
                    label += ' [SHOULDER]'

                ax2.plot(rt_peak, component_signal,
                        color=colors[i % len(colors)],
                        linewidth=2,
                        linestyle='--',
                        label=label)

                # Mark peak center
                ax2.plot(comp.retention_time, comp.amplitude, 'o',
                        color=colors[i % len(colors)], markersize=8)

            ax2.set_xlabel('Retention Time (min)', fontsize=11)
            ax2.set_ylabel('Intensity', fontsize=11)
            ax2.set_title('Individual Peak Components', fontsize=12, fontweight='bold')
            ax2.legend(loc='best', fontsize=9)
            ax2.grid(True, alpha=0.3)
        else:
            ax2.text(0.5, 0.5, f'Deconvolution {result.message}',
                    ha='center', va='center', transform=ax2.transAxes,
                    fontsize=12, color='red')
            ax2.set_xlabel('Retention Time (min)', fontsize=11)
            ax2.set_ylabel('Intensity', fontsize=11)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"  Visualization saved: {save_path.name}")

        return fig

    def plot_batch_deconvolution(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        peak_data: List[Dict],
        deconvolution_results: List[Optional[DeconvolutionResult]],
        sample_name: str,
        save_path: Optional[Path] = None
    ) -> Figure:
        """
        Plot overview of all deconvolved peaks in a chromatogram.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        peak_data : List[Dict]
            Peak data from detection
        deconvolution_results : List[DeconvolutionResult]
            Deconvolution results for each peak
        sample_name : str
            Sample name for title
        save_path : Path, optional
            Path to save the figure

        Returns
        -------
        Figure
            Matplotlib figure object
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 6))

        # Plot full chromatogram
        ax.plot(rt, signal, 'b-', linewidth=1.5, label='Chromatogram', alpha=0.6)

        # Count deconvolved peaks
        n_deconvolved = sum(1 for dr in deconvolution_results if dr and dr.success and dr.n_components > 1)

        # Overlay deconvolved components
        colors = plt.cm.tab10(np.linspace(0, 1, 10))
        color_idx = 0

        for i, (peak_info, result) in enumerate(zip(peak_data, deconvolution_results)):
            if result and result.success and result.n_components > 1:
                # Extract peak region
                start_idx = np.argmin(np.abs(rt - peak_info['start_time']))
                end_idx = np.argmin(np.abs(rt - peak_info['end_time']))
                rt_region = rt[start_idx:end_idx + 1]

                # Plot each component
                for comp in result.components:
                    comp_signal = gaussian(rt_region, comp.amplitude, comp.retention_time, comp.sigma)

                    label = None
                    if color_idx < 10:  # Only label first few to avoid clutter
                        label = f'Deconvolved {i+1}-{result.components.index(comp)+1}'

                    ax.plot(rt_region, comp_signal, '--',
                           color=colors[color_idx % 10],
                           linewidth=1.5,
                           alpha=0.8,
                           label=label)

                    color_idx += 1

        ax.set_xlabel('Retention Time (min)', fontsize=12)
        ax.set_ylabel('Intensity', fontsize=12)
        ax.set_title(f'{sample_name} - Deconvolution Overview ({n_deconvolved} peaks deconvolved)',
                    fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=9, ncol=2)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"  Overview visualization saved: {save_path.name}")

        return fig

    def plot_deconvolution_summary(
        self,
        deconvolution_results: List[Optional[DeconvolutionResult]],
        save_path: Optional[Path] = None
    ) -> Figure:
        """
        Plot summary statistics for deconvolution results.

        Parameters
        ----------
        deconvolution_results : List[DeconvolutionResult]
            List of deconvolution results
        save_path : Path, optional
            Path to save the figure

        Returns
        -------
        Figure
            Matplotlib figure object
        """
        # Filter successful results
        successful = [dr for dr in deconvolution_results if dr and dr.success]

        if not successful:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, 'No successful deconvolutions to display',
                   ha='center', va='center', fontsize=14)
            return fig

        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # 1. Number of components distribution
        n_components = [dr.n_components for dr in successful]
        axes[0, 0].hist(n_components, bins=range(1, max(n_components) + 2), edgecolor='black', alpha=0.7)
        axes[0, 0].set_xlabel('Number of Components', fontsize=11)
        axes[0, 0].set_ylabel('Count', fontsize=11)
        axes[0, 0].set_title('Distribution of Peak Components', fontsize=12, fontweight='bold')
        axes[0, 0].grid(True, alpha=0.3, axis='y')

        # 2. Fit quality distribution
        r2_values = [dr.fit_quality for dr in successful]
        axes[0, 1].hist(r2_values, bins=20, edgecolor='black', alpha=0.7, color='green')
        axes[0, 1].set_xlabel('R² Value', fontsize=11)
        axes[0, 1].set_ylabel('Count', fontsize=11)
        axes[0, 1].set_title('Fit Quality Distribution', fontsize=12, fontweight='bold')
        axes[0, 1].axvline(np.mean(r2_values), color='red', linestyle='--',
                          linewidth=2, label=f'Mean: {np.mean(r2_values):.3f}')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3, axis='y')

        # 3. RMSE distribution
        rmse_values = [dr.rmse for dr in successful]
        axes[1, 0].hist(rmse_values, bins=20, edgecolor='black', alpha=0.7, color='orange')
        axes[1, 0].set_xlabel('RMSE', fontsize=11)
        axes[1, 0].set_ylabel('Count', fontsize=11)
        axes[1, 0].set_title('RMSE Distribution', fontsize=12, fontweight='bold')
        axes[1, 0].axvline(np.mean(rmse_values), color='red', linestyle='--',
                          linewidth=2, label=f'Mean: {np.mean(rmse_values):.2f}')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3, axis='y')

        # 4. Shoulder peak statistics
        total_components = sum(dr.n_components for dr in successful)
        shoulder_count = sum(sum(1 for c in dr.components if c.is_shoulder) for dr in successful)

        categories = ['Regular Peaks', 'Shoulder Peaks']
        counts = [total_components - shoulder_count, shoulder_count]

        axes[1, 1].bar(categories, counts, edgecolor='black', alpha=0.7,
                      color=['blue', 'red'])
        axes[1, 1].set_ylabel('Count', fontsize=11)
        axes[1, 1].set_title('Peak Type Distribution', fontsize=12, fontweight='bold')
        axes[1, 1].grid(True, alpha=0.3, axis='y')

        # Add count labels on bars
        for i, (cat, count) in enumerate(zip(categories, counts)):
            axes[1, 1].text(i, count, str(count), ha='center', va='bottom', fontweight='bold')

        plt.suptitle('Deconvolution Summary Statistics', fontsize=14, fontweight='bold', y=1.00)
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"  Summary statistics saved: {save_path.name}")

        return fig

    def create_deconvolution_report(
        self,
        rt: np.ndarray,
        signal: np.ndarray,
        peak_data: List[Dict],
        deconvolution_results: List[Optional[DeconvolutionResult]],
        sample_name: str,
        output_dir: Path
    ):
        """
        Create a complete deconvolution report with multiple visualizations.

        Parameters
        ----------
        rt : np.ndarray
            Retention time array
        signal : np.ndarray
            Signal intensity array
        peak_data : List[Dict]
            Peak data from detection
        deconvolution_results : List[DeconvolutionResult]
            Deconvolution results
        sample_name : str
            Sample name
        output_dir : Path
            Directory to save visualizations
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  Creating deconvolution visualizations for {sample_name}...")

        # 1. Overview plot
        overview_path = output_dir / f"{sample_name}_deconvolution_overview.png"
        self.plot_batch_deconvolution(
            rt, signal, peak_data, deconvolution_results,
            sample_name, overview_path
        )

        # 2. Individual peak plots (only for deconvolved peaks)
        for i, (peak_info, result) in enumerate(zip(peak_data, deconvolution_results)):
            if result and result.success and result.n_components > 1:
                start_idx = np.argmin(np.abs(rt - peak_info['start_time']))
                end_idx = np.argmin(np.abs(rt - peak_info['end_time']))

                individual_path = output_dir / f"{sample_name}_peak_{peak_info['peak_number']}_deconv.png"
                title = f"{sample_name} - Peak {peak_info['peak_number']} at RT={peak_info['retention_time']:.3f} min"

                self.plot_single_deconvolution(
                    rt, signal, result, start_idx, end_idx,
                    title, individual_path
                )

        # 3. Summary statistics
        summary_path = output_dir / f"{sample_name}_deconvolution_summary.png"
        self.plot_deconvolution_summary(deconvolution_results, summary_path)

        print(f"  Deconvolution report complete: {output_dir}")


if __name__ == "__main__":
    # Test visualization with synthetic data
    from peak_deconvolution import PeakDeconvolution

    print("Testing deconvolution visualizer...")

    # Create test data: two overlapping peaks
    rt = np.linspace(0, 10, 1000)
    peak1 = gaussian(rt, amplitude=100, center=4.5, sigma=0.3)
    peak2 = gaussian(rt, amplitude=70, center=5.2, sigma=0.35)
    signal = peak1 + peak2 + np.random.normal(0, 2, len(rt))

    # Find peak boundaries
    peak_max_idx = np.argmax(signal)
    threshold = np.max(signal) * 0.01
    above_threshold = signal > threshold
    indices = np.where(above_threshold)[0]
    peak_start_idx = indices[0]
    peak_end_idx = indices[-1]

    # Perform deconvolution
    decon = PeakDeconvolution(min_asymmetry=1.15)
    result = decon.analyze_peak(rt, signal, peak_start_idx, peak_end_idx, force_deconvolution=True)

    # Visualize
    visualizer = DeconvolutionVisualizer()

    if result and result.success:
        fig = visualizer.plot_single_deconvolution(
            rt, signal, result, peak_start_idx, peak_end_idx,
            title="Test Peak Deconvolution",
            save_path=Path("test_deconvolution_viz.png")
        )
        print("\nTest visualization saved to 'test_deconvolution_viz.png'")

        # Test summary plot
        fig_summary = visualizer.plot_deconvolution_summary(
            [result],
            save_path=Path("test_deconvolution_summary.png")
        )
        print("Test summary saved to 'test_deconvolution_summary.png'")
    else:
        print("Deconvolution failed, skipping visualization")
