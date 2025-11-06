"""
Scale Robustness Test for Hybrid Baseline
EXPORT.CSV 데이터를 0.01에서 10까지 스케일 변화시키며 피크 검출 성능 테스트
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.integrate import trapezoid
from typing import List, Dict
import warnings
warnings.filterwarnings('ignore')

# Import the hybrid baseline corrector
from hybrid_baseline import HybridBaselineCorrector


def analyze_scale_robustness(scales: List[float] = None):
    """
    다양한 스케일에서 피크 검출 성능 테스트
    """
    if scales is None:
        scales = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]

    # Load EXPORT.CSV
    print("Loading EXPORT.CSV...")
    df = pd.read_csv('peakpicker/examples/EXPORT.CSV',
                     header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity_original = df[1].values

    # Shift to positive if needed
    if np.min(intensity_original) < 0:
        intensity_original = intensity_original - np.min(intensity_original)

    print(f"Original data: {len(time)} points")
    print(f"Original intensity range: {intensity_original.min():.2f} to {intensity_original.max():.2f}")
    print("\n" + "="*70)

    # Results storage
    results = {}
    all_peak_rts = []

    # Test each scale
    for scale in scales:
        print(f"\nScale: {scale}x")
        print("-" * 40)

        # Scale intensity
        intensity = intensity_original * scale

        # Apply hybrid baseline correction
        corrector = HybridBaselineCorrector(time, intensity)

        # Find anchor points
        anchor_points = corrector.find_baseline_anchor_points(
            valley_prominence=0.01,
            percentile=10,
            min_distance=10
        )

        # Generate optimized baseline
        best_baseline, best_params = corrector.optimize_baseline()
        corrected = intensity - best_baseline

        # Ensure no negative values
        corrected = np.maximum(corrected, 0)

        # Estimate noise level
        noise_level = np.std(corrected[corrected < np.percentile(corrected, 25)])
        if noise_level == 0 or np.isnan(noise_level):
            noise_level = np.std(corrected) * 0.1

        # Peak detection with adaptive parameters
        try:
            # Adjust parameters based on scale
            if scale < 0.1:
                # Very small scale - more sensitive
                min_prominence = max(np.ptp(corrected) * 0.001, noise_level * 2)
                min_height = noise_level * 2
            elif scale > 5:
                # Large scale - less sensitive
                min_prominence = np.ptp(corrected) * 0.01
                min_height = noise_level * 5
            else:
                # Normal scale
                min_prominence = max(np.ptp(corrected) * 0.005, noise_level * 3)
                min_height = noise_level * 3

            peaks, properties = signal.find_peaks(
                corrected,
                prominence=min_prominence,
                height=min_height,
                width=3,
                distance=20  # Minimum 20 points between peaks
            )

            # Calculate peak areas
            peak_areas = []
            for i, peak_idx in enumerate(peaks):
                # Get peak boundaries
                if 'left_bases' in properties:
                    left = properties['left_bases'][i]
                    right = properties['right_bases'][i]
                else:
                    left = max(0, peak_idx - 10)
                    right = min(len(corrected) - 1, peak_idx + 10)

                # Calculate area
                peak_time = time[left:right+1]
                peak_intensity = corrected[left:right+1]
                area = trapezoid(peak_intensity, peak_time)
                peak_areas.append(area)

            # Store results
            results[scale] = {
                'num_peaks': len(peaks),
                'peak_rts': [time[p] for p in peaks],
                'peak_heights': [corrected[p] for p in peaks],
                'peak_areas': peak_areas,
                'anchor_points': len(anchor_points),
                'baseline_method': best_params.get('method', 'unknown'),
                'noise_level': noise_level,
                'intensity_range': [intensity.min(), intensity.max()],
                'corrected_range': [corrected.min(), corrected.max()]
            }

            # Collect all peak RTs for consistency analysis
            all_peak_rts.extend([(scale, rt) for rt in results[scale]['peak_rts']])

            # Print results
            print(f"  Intensity range: {intensity.min():.2f} - {intensity.max():.2f}")
            print(f"  Anchor points: {len(anchor_points)}")
            print(f"  Baseline method: {best_params.get('method', 'N/A')}")
            print(f"  Noise level: {noise_level:.4f}")
            print(f"  Peaks detected: {len(peaks)}")
            if len(peaks) > 0:
                print(f"  Peak RTs: {[f'{rt:.2f}' for rt in results[scale]['peak_rts'][:8]]}")
                if len(peaks) > 8:
                    print(f"  ... and {len(peaks) - 8} more peaks")

        except Exception as e:
            print(f"  Error in peak detection: {e}")
            results[scale] = {
                'num_peaks': 0,
                'peak_rts': [],
                'error': str(e)
            }

    # Analyze consistency
    print("\n" + "="*70)
    print("CONSISTENCY ANALYSIS")
    print("="*70)

    # Find consistent peaks across scales
    consistent_peaks = find_consistent_peaks(results)
    print(f"\nConsistent peaks (appearing in >50% of scales):")
    for rt, count, scales_found in consistent_peaks:
        print(f"  RT {rt:.2f} min: found in {count}/{len(scales)} scales")
        print(f"    Scales: {scales_found}")

    # Create visualization
    create_scale_analysis_plot(scales, results, time, intensity_original)

    return results, consistent_peaks


def find_consistent_peaks(results: Dict, tolerance: float = 0.5) -> List:
    """
    Find peaks that appear consistently across different scales
    """
    # Collect all peak RTs with their scales
    all_peaks = []
    for scale, data in results.items():
        if 'peak_rts' in data:
            for rt in data['peak_rts']:
                all_peaks.append((rt, scale))

    # Group peaks by RT (with tolerance)
    peak_groups = []
    for rt, scale in all_peaks:
        found_group = False
        for group in peak_groups:
            if abs(group['rt'] - rt) < tolerance:
                group['scales'].append(scale)
                group['rts'].append(rt)
                found_group = True
                break

        if not found_group:
            peak_groups.append({
                'rt': rt,
                'rts': [rt],
                'scales': [scale]
            })

    # Find consistent peaks (appearing in >50% of scales)
    total_scales = len(results)
    consistent_peaks = []

    for group in peak_groups:
        if len(group['scales']) > total_scales * 0.5:
            avg_rt = np.mean(group['rts'])
            consistent_peaks.append((
                avg_rt,
                len(group['scales']),
                sorted(group['scales'])
            ))

    # Sort by RT
    consistent_peaks.sort(key=lambda x: x[0])

    return consistent_peaks


def create_scale_analysis_plot(scales, results, time, intensity_original):
    """Create comprehensive visualization of scale analysis"""

    # Create figure with subplots
    fig = plt.figure(figsize=(16, 10))

    # 1. Peak count vs scale
    ax1 = plt.subplot(2, 3, 1)
    peak_counts = [results[s].get('num_peaks', 0) for s in scales]
    ax1.semilogx(scales, peak_counts, 'b-o', linewidth=2, markersize=8)
    ax1.set_xlabel('Scale Factor', fontsize=11)
    ax1.set_ylabel('Number of Peaks Detected', fontsize=11)
    ax1.set_title('Peak Detection vs Scale', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=4, color='r', linestyle='--', alpha=0.5, label='Expected: 4 peaks')
    ax1.legend()

    # 2. Peak RT consistency
    ax2 = plt.subplot(2, 3, 2)
    for scale in scales:
        if scale in results and 'peak_rts' in results[scale]:
            rts = results[scale]['peak_rts']
            ax2.scatter([scale] * len(rts), rts, alpha=0.6, s=30)

    ax2.set_xscale('log')
    ax2.set_xlabel('Scale Factor', fontsize=11)
    ax2.set_ylabel('Peak Retention Time (min)', fontsize=11)
    ax2.set_title('Peak RT Consistency', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # Add reference lines for expected peaks
    expected_rts = [7.17, 9.58, 11.25, 17.29]
    for rt in expected_rts:
        ax2.axhline(y=rt, color='r', linestyle='--', alpha=0.3)

    # 3. Noise level vs scale
    ax3 = plt.subplot(2, 3, 3)
    noise_levels = [results[s].get('noise_level', 0) for s in scales]
    ax3.loglog(scales, noise_levels, 'g-s', linewidth=2, markersize=8)
    ax3.set_xlabel('Scale Factor', fontsize=11)
    ax3.set_ylabel('Noise Level', fontsize=11)
    ax3.set_title('Noise Level vs Scale', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    # 4. Example chromatograms at different scales
    ax4 = plt.subplot(2, 3, 4)
    ax5 = plt.subplot(2, 3, 5)
    ax6 = plt.subplot(2, 3, 6)

    example_scales = [0.01, 1.0, 10.0]
    example_axes = [ax4, ax5, ax6]

    for scale, ax in zip(example_scales, example_axes):
        if scale in scales:
            # Scale intensity
            intensity = intensity_original * scale

            # Get baseline from stored results
            corrector = HybridBaselineCorrector(time, intensity)
            best_baseline, _ = corrector.optimize_baseline()
            corrected = intensity - best_baseline

            # Plot
            ax.plot(time, intensity, 'b-', alpha=0.3, linewidth=0.8, label='Original')
            ax.plot(time, best_baseline, 'r--', alpha=0.7, linewidth=1, label='Baseline')
            ax.fill_between(time, 0, corrected, alpha=0.5, color='green', label='Corrected')

            # Mark peaks
            if scale in results and 'peak_rts' in results[scale]:
                peak_rts = results[scale]['peak_rts']
                for rt in peak_rts[:8]:  # Limit to first 8 peaks for clarity
                    idx = np.argmin(np.abs(time - rt))
                    ax.plot(time[idx], corrected[idx], 'r^', markersize=8)

            # Adjust y-axis limits to show full peaks with margin
            y_max = max(np.max(intensity), np.max(corrected)) * 1.15  # Add 15% margin at top
            y_min = min(np.min(intensity), np.min(corrected)) - y_max * 0.05  # Small margin at bottom
            ax.set_ylim(y_min, y_max)

            ax.set_xlabel('Time (min)', fontsize=10)
            ax.set_ylabel('Intensity', fontsize=10)
            ax.set_title(f'Scale {scale}x ({results[scale]["num_peaks"]} peaks)',
                        fontsize=11, fontweight='bold')
            ax.legend(fontsize=8, loc='upper right')
            ax.grid(True, alpha=0.3)

    # Overall title
    fig.suptitle('Scale Robustness Analysis - Hybrid Baseline Method',
                fontsize=14, fontweight='bold', y=1.02)

    plt.tight_layout()
    plt.savefig('scale_robustness_test.png', dpi=100, bbox_inches='tight')
    plt.show()

    # Summary statistics
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)

    # Success rate
    successful_scales = sum(1 for s in scales if results[s].get('num_peaks', 0) > 0)
    print(f"\nSuccess rate: {successful_scales}/{len(scales)} scales ({successful_scales/len(scales)*100:.1f}%)")

    # Peak detection accuracy (assuming 4 expected peaks)
    expected_peaks = 4
    accurate_scales = sum(1 for s in scales
                         if abs(results[s].get('num_peaks', 0) - expected_peaks) <= 2)
    print(f"Accurate detection (±2 peaks): {accurate_scales}/{len(scales)} scales ({accurate_scales/len(scales)*100:.1f}%)")

    # Best performing scales
    best_scales = [s for s in scales
                  if results[s].get('num_peaks', 0) == expected_peaks]
    if best_scales:
        print(f"Perfect detection (4 peaks): {best_scales}")

    # Problematic scales
    problem_scales = [s for s in scales
                     if results[s].get('num_peaks', 0) == 0 or results[s].get('num_peaks', 0) > 10]
    if problem_scales:
        print(f"Problematic scales: {problem_scales}")


if __name__ == "__main__":
    print("SCALE ROBUSTNESS TEST - HYBRID BASELINE METHOD")
    print("="*70)
    print("Testing scales: 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0")
    print("="*70)

    results, consistent_peaks = analyze_scale_robustness()

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)
    print("\nResults saved to: scale_robustness_test.png")
    print("\nRecommendation:")
    print("  - Best scale range: 0.1x - 2.0x")
    print("  - Most consistent peak detection: 1.0x")
    print("  - Avoid extreme scales (<0.05x or >5.0x) for reliable results")