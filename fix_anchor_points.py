"""
Fix anchor points to avoid climbing up peak sides
Only place anchor points at true valleys between peaks
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.ndimage import minimum_filter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector, BaselinePoint


def find_true_valleys_only(time, intensity):
    """
    Find only true valleys between peaks, not on peak shoulders
    """
    # First, identify peak regions to avoid
    # Smooth the signal first
    window = min(21, len(intensity) // 20)
    if window % 2 == 0:
        window += 1

    if len(intensity) > window:
        smoothed = signal.savgol_filter(intensity, window, 3)
    else:
        smoothed = intensity.copy()

    # Find peaks to know where to avoid
    peaks, peak_props = signal.find_peaks(
        smoothed,
        prominence=np.ptp(smoothed) * 0.01,
        distance=window
    )

    # Create peak mask - regions to avoid for anchor points
    peak_mask = np.zeros(len(intensity), dtype=bool)

    for peak_idx in peaks:
        # Find peak width at 20% height (wider than half-height)
        peak_height = smoothed[peak_idx] - np.min(smoothed)
        threshold = np.min(smoothed) + peak_height * 0.2  # 20% of peak height

        # Find left boundary
        left_idx = peak_idx
        while left_idx > 0 and smoothed[left_idx] > threshold:
            left_idx -= 1

        # Find right boundary
        right_idx = peak_idx
        while right_idx < len(smoothed) - 1 and smoothed[right_idx] > threshold:
            right_idx += 1

        # Mark this region as peak region (to avoid)
        peak_mask[max(0, left_idx-10):min(len(intensity), right_idx+10)] = True

    # Now find valleys, but only outside peak regions
    inverted = -smoothed
    valleys, valley_props = signal.find_peaks(
        inverted,
        prominence=np.ptp(smoothed) * 0.02,  # Higher prominence for true valleys
        distance=window * 2  # Larger distance between valleys
    )

    # Filter valleys - keep only those NOT in peak regions
    true_valleys = []
    for valley_idx in valleys:
        if not peak_mask[valley_idx]:
            true_valleys.append(valley_idx)

    return np.array(true_valleys), peak_mask


def create_improved_baseline():
    """Create baseline with improved anchor point selection"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print(f"Fixing anchor points for: {csv_file.name}")

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # Find true valleys only
    true_valleys, peak_mask = find_true_valleys_only(time, intensity)

    print(f"Found {len(true_valleys)} true valleys (excluding peak regions)")

    # Create baseline points from true valleys only
    baseline_points = []

    # Add start point if it's not in a peak region
    if not peak_mask[0]:
        baseline_points.append(BaselinePoint(
            index=0,
            value=intensity[0],
            type='boundary',
            confidence=0.8
        ))

    # Add valley points
    for valley_idx in true_valleys:
        baseline_points.append(BaselinePoint(
            index=valley_idx,
            value=intensity[valley_idx],
            type='valley',
            confidence=1.0
        ))

    # Add end point if it's not in a peak region
    if not peak_mask[-1]:
        baseline_points.append(BaselinePoint(
            index=len(intensity) - 1,
            value=intensity[-1],
            type='boundary',
            confidence=0.8
        ))

    # Sort by index
    baseline_points.sort(key=lambda p: p.index)

    # If we have very few anchor points, add some in non-peak regions
    if len(baseline_points) < 5:
        # Find regions between peaks
        non_peak_indices = np.where(~peak_mask)[0]

        # Sample some points from non-peak regions
        if len(non_peak_indices) > 20:
            # Take lowest 10% of non-peak points
            non_peak_values = intensity[non_peak_indices]
            threshold = np.percentile(non_peak_values, 10)
            low_points = non_peak_indices[non_peak_values <= threshold]

            # Sample evenly
            if len(low_points) > 5:
                sampled = low_points[::len(low_points)//5][:5]
                for idx in sampled:
                    if not any(abs(idx - p.index) < 20 for p in baseline_points):
                        baseline_points.append(BaselinePoint(
                            index=idx,
                            value=intensity[idx],
                            type='local_min',
                            confidence=0.7
                        ))

        baseline_points.sort(key=lambda p: p.index)

    # Create baseline using these improved anchor points
    from scipy.interpolate import UnivariateSpline, interp1d

    indices = np.array([p.index for p in baseline_points])
    values = np.array([p.value for p in baseline_points])

    # Use smooth spline with high smoothing
    baseline = np.zeros_like(intensity)

    if len(indices) > 3:
        # Very smooth spline
        s = len(indices) * 10.0  # High smoothing factor
        try:
            spl = UnivariateSpline(indices, values, s=s, k=3)
            baseline = spl(np.arange(len(intensity)))
        except:
            # Fallback to linear
            f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
            baseline = f(np.arange(len(intensity)))
    else:
        f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
        baseline = f(np.arange(len(intensity)))

    # Apply additional constraints to keep baseline low
    # Use local minimum with large window
    window_size = 301  # ~1.5 minute window
    local_min = minimum_filter(intensity, size=window_size, mode='nearest')
    baseline = np.minimum(baseline, local_min * 0.8)

    # Smooth the baseline
    if len(baseline) > 51:
        baseline = signal.savgol_filter(baseline, 51, 3)

    # Final constraint: never above 50% of signal
    baseline = np.minimum(baseline, intensity * 0.5)

    # Calculate corrected signal
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)

    # Detect peaks
    peaks, _ = signal.find_peaks(
        corrected,
        prominence=np.ptp(corrected) * 0.005,
        height=np.percentile(corrected[corrected > 0], 25) * 3
    )

    # Create visualization
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # Plot 1: Original with peak regions highlighted
    ax1 = axes[0, 0]
    ax1.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.8, label='Signal')

    # Highlight peak regions
    peak_regions = np.zeros_like(intensity)
    peak_regions[peak_mask] = intensity[peak_mask]
    ax1.fill_between(time, 0, peak_regions, alpha=0.2, color='red', label='Peak Regions (avoided)')

    # Show valleys
    if len(true_valleys) > 0:
        ax1.scatter(time[true_valleys], intensity[true_valleys],
                   c='green', s=50, marker='v', zorder=5, label='True Valleys')

    ax1.set_title('Peak Region Detection', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Retention Time (min)')
    ax1.set_ylabel('Intensity')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Anchor points placement
    ax2 = axes[0, 1]
    ax2.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.8, label='Signal')

    # Show all anchor points with different colors by type
    for point in baseline_points:
        if point.type == 'valley':
            color, marker, size = 'green', 'v', 60
        elif point.type == 'boundary':
            color, marker, size = 'orange', 's', 40
        else:  # local_min
            color, marker, size = 'blue', 'o', 30

        ax2.scatter(time[point.index], point.value,
                   c=color, s=size, marker=marker,
                   edgecolors='black', linewidths=0.5,
                   alpha=0.8, zorder=5)

    ax2.set_title(f'Improved Anchor Points ({len(baseline_points)} points)', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Retention Time (min)')
    ax2.set_ylabel('Intensity')

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        plt.Line2D([0], [0], color='b', linewidth=1.5, label='Signal'),
        plt.scatter([], [], c='green', marker='v', s=60, label='Valley'),
        plt.scatter([], [], c='orange', marker='s', s=40, label='Boundary'),
        plt.scatter([], [], c='blue', marker='o', s=30, label='Local Min')
    ]
    ax2.legend(handles=legend_elements, loc='upper right')
    ax2.grid(True, alpha=0.3)

    # Plot 3: Baseline correction
    ax3 = axes[1, 0]
    ax3.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.8, label='Original Signal')
    ax3.plot(time, baseline, 'r-', linewidth=1.2, label='Improved Baseline')
    ax3.fill_between(time, baseline, intensity, where=(intensity >= baseline),
                     alpha=0.25, color='yellow', label='Area to Remove')

    # Show anchor points on baseline
    ax3.scatter(time[indices], values, c='red', s=30, zorder=5,
               edgecolors='black', linewidths=0.5)

    ax3.set_title('Improved Baseline Correction', fontsize=12, fontweight='bold')
    ax3.set_xlabel('Retention Time (min)')
    ax3.set_ylabel('Intensity')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    # Plot 4: Corrected signal
    ax4 = axes[1, 1]
    ax4.plot(time, corrected, 'g-', linewidth=1.5, alpha=0.9, label='Corrected Signal')
    ax4.fill_between(time, 0, corrected, alpha=0.2, color='lightgreen')

    if len(peaks) > 0:
        ax4.scatter(time[peaks], corrected[peaks],
                   color='red', s=60, marker='^',
                   edgecolors='darkred', linewidths=1,
                   zorder=5, label=f'{len(peaks)} Peaks')

    ax4.set_title('Corrected Signal with Peak Detection', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Retention Time (min)')
    ax4.set_ylabel('Corrected Intensity')
    ax4.legend(loc='upper right')
    ax4.grid(True, alpha=0.3)

    plt.suptitle('Fixed Anchor Points - Avoiding Peak Regions', fontsize=14, fontweight='bold')
    plt.tight_layout()

    # Save figure
    output_file = Path("fixed_anchor_points.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: {output_file}")

    # Print statistics
    print("\n" + "="*60)
    print("IMPROVED ANCHOR POINT PLACEMENT")
    print("="*60)
    print(f"Total anchor points: {len(baseline_points)}")
    print(f"  - True valleys: {sum(1 for p in baseline_points if p.type == 'valley')}")
    print(f"  - Boundaries: {sum(1 for p in baseline_points if p.type == 'boundary')}")
    print(f"  - Local minima: {sum(1 for p in baseline_points if p.type == 'local_min')}")
    print(f"\nPeaks detected: {len(peaks)}")
    print(f"Baseline/Signal ratio: {(np.trapz(baseline, time)/np.trapz(intensity, time))*100:.1f}%")

    # Check if anchor points are avoiding peaks
    print("\nAnchor point analysis:")
    for i, point in enumerate(baseline_points):
        rt = time[point.index]
        val = point.value
        in_peak = "IN PEAK REGION!" if peak_mask[point.index] else "OK (outside peaks)"
        print(f"  Point {i+1}: RT={rt:.2f}, Value={val:.0f}, Type={point.type}, Status={in_peak}")

    plt.show()


if __name__ == "__main__":
    create_improved_baseline()