"""
Example: Peak Detection and Integration
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector, detect_and_integrate_peaks
from modules.visualizer import ChromatogramVisualizer


def example_basic_peak_detection():
    """Example 1: Basic peak detection"""
    print("\n" + "="*60)
    print("Example 1: Basic Peak Detection")
    print("="*60)

    # Load sample data
    sample_file = Path(__file__).parent.parent / "examples" / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    print(f"✓ Loaded data: {len(time)} points")

    # Auto-detect peaks
    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    print(f"✓ Detected {len(peaks)} peaks\n")

    # Display peak information
    for i, peak in enumerate(peaks, 1):
        print(f"Peak {i}:")
        print(f"  Retention Time: {peak.rt:.3f} min")
        print(f"  RT Range: {peak.rt_start:.3f} - {peak.rt_end:.3f} min")
        print(f"  Height: {peak.height:.2f}")
        print(f"  Area: {peak.area:.2f}")
        print(f"  Width: {peak.width:.3f} min")
        print(f"  % of Total Area: {peak.percent_area:.2f}%")
        print()

    return time, intensity, peaks


def example_manual_parameters():
    """Example 2: Manual parameter adjustment"""
    print("\n" + "="*60)
    print("Example 2: Manual Parameter Adjustment")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent.parent / "examples" / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    # Try different parameter sets
    parameter_sets = [
        {"prominence": 500, "min_height": 300, "min_width": 0.01},
        {"prominence": 200, "min_height": 100, "min_width": 0.05},
        {"prominence": 50, "min_height": 30, "min_width": 0.1},
    ]

    for i, params in enumerate(parameter_sets, 1):
        print(f"\nParameter Set {i}:")
        print(f"  Prominence: {params['prominence']}")
        print(f"  Min Height: {params['min_height']}")
        print(f"  Min Width: {params['min_width']}")

        detector = PeakDetector(
            time, intensity,
            prominence=params['prominence'],
            min_height=params['min_height'],
            min_width=params['min_width'],
            auto_threshold=False
        )
        peaks = detector.detect_peaks()

        print(f"  → Detected {len(peaks)} peaks")


def example_peak_search():
    """Example 3: Search for specific peaks"""
    print("\n" + "="*60)
    print("Example 3: Peak Search")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent.parent / "examples" / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    # Search for peak at specific RT
    target_rt = 4.0
    tolerance = 0.2

    print(f"\nSearching for peak at RT = {target_rt:.1f} min (±{tolerance} min)")

    peak = detector.get_peak_at_rt(target_rt, tolerance)

    if peak:
        print(f"✓ Found peak:")
        print(f"  RT: {peak.rt:.3f} min")
        print(f"  Area: {peak.area:.2f}")
    else:
        print("✗ No peak found in range")

    # Search for peaks in range
    rt_start, rt_end = 3.0, 5.0
    print(f"\nSearching for peaks between {rt_start} - {rt_end} min")

    peaks_in_range = detector.get_peaks_in_range(rt_start, rt_end)

    print(f"✓ Found {len(peaks_in_range)} peaks in range:")
    for peak in peaks_in_range:
        print(f"  - RT: {peak.rt:.3f} min, Area: {peak.area:.2f}")


def example_summary_statistics():
    """Example 4: Get summary statistics"""
    print("\n" + "="*60)
    print("Example 4: Summary Statistics")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent.parent / "examples" / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    # Detect peaks
    peaks, summary = detect_and_integrate_peaks(time, intensity)

    print("\nSummary Statistics:")
    print(f"  Number of peaks: {summary['num_peaks']}")
    print(f"  Total area: {summary['total_area']:.2f}")
    print(f"  Average peak width: {summary['avg_peak_width']:.3f} min")
    print(f"  Average peak height: {summary['avg_peak_height']:.2f}")
    print(f"\nRetention times: {[f'{rt:.3f}' for rt in summary['retention_times']]}")
    print(f"Peak areas: {[f'{area:.2f}' for area in summary['areas']]}")


def example_visualization():
    """Example 5: Visualize peaks"""
    print("\n" + "="*60)
    print("Example 5: Peak Visualization")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent.parent / "examples" / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    # Detect peaks
    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    print(f"✓ Detected {len(peaks)} peaks")

    # Create visualizer
    visualizer = ChromatogramVisualizer(figsize=(14, 6))

    # Plot with peaks
    fig = visualizer.plot_with_peaks(
        time, intensity, peaks,
        title="Chromatogram with Detected Peaks",
        show_baseline=True,
        annotate_peaks=True
    )

    # Save figure
    output_file = Path(__file__).parent / "peak_detection_example.png"
    visualizer.save_figure(str(output_file), dpi=300)

    print(f"✓ Saved plot to: {output_file}")

    # Also save a simple plot
    visualizer.clear()
    fig = visualizer.plot_chromatogram(
        time, intensity,
        title="Original Chromatogram",
        color="blue"
    )

    output_file2 = Path(__file__).parent / "chromatogram_simple.png"
    visualizer.save_figure(str(output_file2), dpi=300)

    print(f"✓ Saved simple plot to: {output_file2}")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("PEAK DETECTION EXAMPLES")
    print("="*70)

    # Run examples
    example_basic_peak_detection()
    example_manual_parameters()
    example_peak_search()
    example_summary_statistics()
    example_visualization()

    print("\n" + "="*70)
    print("All examples completed!")
    print("="*70)


if __name__ == "__main__":
    main()
