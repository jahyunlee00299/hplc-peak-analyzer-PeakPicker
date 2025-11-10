"""
Test Script for Peak Deconvolution Feature
==========================================

This script tests the peak deconvolution functionality with synthetic data.

Author: PeakPicker Project
Date: 2025-11-10
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from peak_models import gaussian, multi_gaussian
from peak_deconvolution import PeakDeconvolution
from deconvolution_visualizer import DeconvolutionVisualizer


def create_synthetic_chromatogram():
    """
    Create synthetic HPLC chromatogram with overlapping peaks.

    Returns
    -------
    rt : np.ndarray
        Retention time array
    signal : np.ndarray
        Signal intensity array
    ground_truth : dict
        Ground truth peak parameters
    """
    print("Creating synthetic chromatogram...")

    rt = np.linspace(0, 20, 2000)

    # Create multiple scenarios

    # Scenario 1: Two overlapping peaks (moderate overlap)
    peak1 = gaussian(rt, amplitude=100, center=5.0, sigma=0.3)
    peak2 = gaussian(rt, amplitude=80, center=5.8, sigma=0.35)

    # Scenario 2: Three overlapping peaks (complex)
    peak3 = gaussian(rt, amplitude=120, center=10.0, sigma=0.4)
    peak4 = gaussian(rt, amplitude=60, center=10.5, sigma=0.25)  # Shoulder
    peak5 = gaussian(rt, amplitude=40, center=11.2, sigma=0.3)   # Shoulder

    # Scenario 3: Asymmetric peak with shoulder
    peak6 = gaussian(rt, amplitude=90, center=15.0, sigma=0.35)
    peak7 = gaussian(rt, amplitude=50, center=15.6, sigma=0.2)   # Right shoulder

    # Combine all peaks
    signal = peak1 + peak2 + peak3 + peak4 + peak5 + peak6 + peak7

    # Add noise
    noise = np.random.normal(0, 2, len(rt))
    signal = signal + noise

    # Ensure no negative values
    signal = np.maximum(signal, 0)

    ground_truth = {
        'scenario_1': {
            'peaks': [
                {'center': 5.0, 'amplitude': 100, 'sigma': 0.3},
                {'center': 5.8, 'amplitude': 80, 'sigma': 0.35}
            ],
            'description': 'Two moderately overlapping peaks'
        },
        'scenario_2': {
            'peaks': [
                {'center': 10.0, 'amplitude': 120, 'sigma': 0.4},
                {'center': 10.5, 'amplitude': 60, 'sigma': 0.25},
                {'center': 11.2, 'amplitude': 40, 'sigma': 0.3}
            ],
            'description': 'Three overlapping peaks with shoulders'
        },
        'scenario_3': {
            'peaks': [
                {'center': 15.0, 'amplitude': 90, 'sigma': 0.35},
                {'center': 15.6, 'amplitude': 50, 'sigma': 0.2}
            ],
            'description': 'Asymmetric peak with right shoulder'
        }
    }

    print(f"  RT range: {rt[0]:.2f} - {rt[-1]:.2f} min")
    print(f"  Signal range: {signal.min():.2f} - {signal.max():.2f}")
    print(f"  Total synthetic peaks: 7")

    return rt, signal, ground_truth


def find_peak_boundaries(rt, signal, center_rt, width_factor=3.0):
    """
    Find peak boundaries around a center RT.

    Parameters
    ----------
    rt : np.ndarray
        Retention time array
    signal : np.ndarray
        Signal intensity array
    center_rt : float
        Center retention time
    width_factor : float
        How many sigma to extend on each side

    Returns
    -------
    start_idx : int
        Peak start index
    end_idx : int
        Peak end index
    """
    center_idx = np.argmin(np.abs(rt - center_rt))
    peak_height = signal[center_idx]

    # Find boundaries (where signal drops below 5% of peak height)
    threshold = peak_height * 0.05

    # Search left
    left_idx = center_idx
    while left_idx > 0 and signal[left_idx] > threshold:
        left_idx -= 1

    # Search right
    right_idx = center_idx
    while right_idx < len(signal) - 1 and signal[right_idx] > threshold:
        right_idx += 1

    return left_idx, right_idx


def test_deconvolution():
    """Test peak deconvolution with synthetic data."""

    print("\n" + "="*70)
    print("PEAK DECONVOLUTION TEST")
    print("="*70)

    # Create synthetic data
    rt, signal, ground_truth = create_synthetic_chromatogram()

    # Initialize deconvolution
    decon = PeakDeconvolution(
        min_asymmetry=1.15,
        min_shoulder_ratio=0.08,
        max_components=4
    )

    # Initialize visualizer
    visualizer = DeconvolutionVisualizer(dpi=150)

    # Test scenarios
    scenarios = [
        {'name': 'Scenario 1', 'center_rt': 5.4},
        {'name': 'Scenario 2', 'center_rt': 10.5},
        {'name': 'Scenario 3', 'center_rt': 15.3}
    ]

    results = []

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'-'*70}")
        print(f"Testing {scenario['name']}: {ground_truth[f'scenario_{i}']['description']}")
        print(f"{'-'*70}")

        center_rt = scenario['center_rt']

        # Find peak boundaries
        start_idx, end_idx = find_peak_boundaries(rt, signal, center_rt)

        print(f"  Peak region: RT {rt[start_idx]:.2f} - {rt[end_idx]:.2f} min")
        print(f"  Region data points: {end_idx - start_idx}")

        # Check if deconvolution is needed
        peak_idx = np.argmin(np.abs(rt - center_rt))
        needs_decon, reason = decon.needs_deconvolution(rt, signal, peak_idx)
        print(f"  Needs deconvolution: {needs_decon}")
        if needs_decon:
            print(f"  Reason: {reason}")

        # Perform deconvolution
        result = decon.analyze_peak(
            rt, signal, start_idx, end_idx,
            force_deconvolution=True
        )

        if result and result.success:
            print(f"\n  DECONVOLUTION SUCCESSFUL!")
            print(f"  Method: {result.method}")
            print(f"  Number of components: {result.n_components}")
            print(f"  Fit quality (R²): {result.fit_quality:.4f}")
            print(f"  RMSE: {result.rmse:.4f}")
            print(f"  Total area: {result.total_area:.1f}")

            print(f"\n  Components:")
            for j, comp in enumerate(result.components, 1):
                shoulder_tag = " [SHOULDER]" if comp.is_shoulder else ""
                print(f"    {j}. RT={comp.retention_time:.3f} min, "
                      f"Height={comp.amplitude:.1f}, "
                      f"Area={comp.area:.1f} ({comp.area_percent:.1f}%), "
                      f"Asymmetry={comp.asymmetry:.2f}{shoulder_tag}")

            # Compare with ground truth
            gt_peaks = ground_truth[f'scenario_{i}']['peaks']
            print(f"\n  Ground Truth Comparison:")
            print(f"    Expected peaks: {len(gt_peaks)}")
            print(f"    Found peaks: {result.n_components}")

            # Visualize
            save_path = Path(f"test_scenario_{i}_deconv.png")
            visualizer.plot_single_deconvolution(
                rt, signal, result, start_idx, end_idx,
                title=f"{scenario['name']}: {ground_truth[f'scenario_{i}']['description']}",
                save_path=save_path
            )

        else:
            print(f"\n  DECONVOLUTION FAILED")
            print(f"  Message: {result.message if result else 'No result'}")

        results.append(result)

    # Create summary plot
    print(f"\n{'-'*70}")
    print("Creating summary visualization...")
    print(f"{'-'*70}")

    summary_path = Path("test_deconvolution_summary.png")
    visualizer.plot_deconvolution_summary(results, summary_path)

    # Overall statistics
    successful = [r for r in results if r and r.success]
    print(f"\nOVERALL STATISTICS:")
    print(f"  Scenarios tested: {len(scenarios)}")
    print(f"  Successful deconvolutions: {len(successful)}/{len(results)}")

    if successful:
        avg_r2 = np.mean([r.fit_quality for r in successful])
        avg_rmse = np.mean([r.rmse for r in successful])
        total_components = sum(r.n_components for r in successful)

        print(f"  Average R²: {avg_r2:.4f}")
        print(f"  Average RMSE: {avg_rmse:.4f}")
        print(f"  Total components found: {total_components}")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)
    print("\nGenerated files:")
    print("  - test_scenario_1_deconv.png")
    print("  - test_scenario_2_deconv.png")
    print("  - test_scenario_3_deconv.png")
    print("  - test_deconvolution_summary.png")

    return results


if __name__ == "__main__":
    try:
        results = test_deconvolution()
        print("\nAll tests completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
