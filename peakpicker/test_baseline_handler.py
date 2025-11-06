"""
Test script for Baseline Handler and Peak Splitter
"""

import sys
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent))

from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector
from modules.baseline_handler import BaselineHandler, PeakSplitter


def test_linear_baseline():
    """Test linear baseline calculation"""
    print("\n=== Testing Linear Baseline ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        # Create baseline handler
        handler = BaselineHandler(time, intensity)

        # Calculate linear baseline
        baseline = handler.calculate_linear_baseline()

        print(f"✅ Linear baseline calculated")
        print(f"   - Start intensity: {baseline[0]:.2f}")
        print(f"   - End intensity: {baseline[-1]:.2f}")

        # Apply correction
        corrected = handler.apply_baseline_correction()

        print(f"✅ Baseline correction applied")
        print(f"   - Original range: {intensity.min():.2f} - {intensity.max():.2f}")
        print(f"   - Corrected range: {corrected.min():.2f} - {corrected.max():.2f}")

        return True

    except Exception as e:
        print(f"❌ Error in linear baseline: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_polynomial_baseline():
    """Test polynomial baseline"""
    print("\n=== Testing Polynomial Baseline ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        handler = BaselineHandler(time, intensity)

        # Test different degrees
        for degree in [2, 3, 5]:
            baseline = handler.calculate_polynomial_baseline(degree=degree)
            print(f"✅ Polynomial baseline (degree={degree}) calculated")
            print(f"   - Baseline range: {baseline.min():.2f} - {baseline.max():.2f}")

        return True

    except Exception as e:
        print(f"❌ Error in polynomial baseline: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_als_baseline():
    """Test ALS baseline"""
    print("\n=== Testing ALS Baseline ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        handler = BaselineHandler(time, intensity)

        # Calculate ALS baseline
        baseline = handler.calculate_als_baseline(lam=1e6, p=0.01, niter=10)

        print(f"✅ ALS baseline calculated")
        print(f"   - Baseline range: {baseline.min():.2f} - {baseline.max():.2f}")

        # Apply correction
        corrected = handler.apply_baseline_correction()
        print(f"✅ ALS baseline correction applied")

        return True

    except Exception as e:
        print(f"❌ Error in ALS baseline: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manual_baseline():
    """Test manual baseline with anchor points"""
    print("\n=== Testing Manual Baseline ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        handler = BaselineHandler(time, intensity)

        # Define anchor points (time, intensity)
        anchor_points = [
            (0.0, 12.5),
            (2.0, 200.0),
            (4.0, 100.0),
            (6.0, 271.5)
        ]

        baseline = handler.manual_baseline(anchor_points)

        print(f"✅ Manual baseline created from {len(anchor_points)} anchor points")
        print(f"   - Anchor points: {anchor_points}")

        return True

    except Exception as e:
        print(f"❌ Error in manual baseline: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_peak_splitting():
    """Test peak splitting"""
    print("\n=== Testing Peak Splitting ===")

    try:
        # Create synthetic overlapping peaks
        time = np.linspace(0, 10, 500)
        peak1 = 100 * np.exp(-((time - 3) ** 2) / 0.3)
        peak2 = 80 * np.exp(-((time - 4) ** 2) / 0.3)
        intensity = peak1 + peak2 + 10  # Overlapping peaks with baseline

        print(f"✅ Created synthetic overlapping peaks")

        # Detect the overlapping peak
        detector = PeakDetector(time, intensity, auto_threshold=True)
        peaks = detector.detect_peaks()

        print(f"✅ Detected {len(peaks)} peak(s)")

        if len(peaks) > 0:
            # Split the first peak
            splitter = PeakSplitter(time, intensity)

            peak1_split, peak2_split = splitter.split_peak_at_minimum(peaks[0])

            print(f"✅ Peak split successful")
            print(f"   Peak 1: RT={peak1_split.rt:.3f}, Area={peak1_split.area:.2f}")
            print(f"   Peak 2: RT={peak2_split.rt:.3f}, Area={peak2_split.area:.2f}")

            return True
        else:
            print("⚠️ No peaks detected to split")
            return False

    except Exception as e:
        print(f"❌ Error in peak splitting: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_overlap_detection():
    """Test overlap detection"""
    print("\n=== Testing Overlap Detection ===")

    try:
        # Create synthetic data with overlapping peaks
        time = np.linspace(0, 10, 500)
        peak1 = 100 * np.exp(-((time - 3) ** 2) / 0.3)
        peak2 = 80 * np.exp(-((time - 3.5) ** 2) / 0.3)
        peak3 = 90 * np.exp(-((time - 7) ** 2) / 0.4)
        intensity = peak1 + peak2 + peak3 + 10

        # Detect peaks
        detector = PeakDetector(time, intensity, prominence=20, min_height=15, auto_threshold=False)
        peaks = detector.detect_peaks()

        print(f"✅ Detected {len(peaks)} peaks")

        # Check for overlaps
        splitter = PeakSplitter(time, intensity)
        overlapping = splitter.detect_overlapping_peaks(peaks, overlap_threshold=0.3)

        print(f"✅ Found {len(overlapping)} overlapping peak pair(s)")
        for peak1_idx, peak2_idx in overlapping:
            print(f"   - Peak {peak1_idx+1} overlaps with Peak {peak2_idx+1}")

        return True

    except Exception as e:
        print(f"❌ Error in overlap detection: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Baseline Handler and Peak Splitter Tests")
    print("=" * 60)

    results = []

    # Test baseline methods
    results.append(("Linear Baseline", test_linear_baseline()))
    results.append(("Polynomial Baseline", test_polynomial_baseline()))
    results.append(("ALS Baseline", test_als_baseline()))
    results.append(("Manual Baseline", test_manual_baseline()))

    # Test peak splitting
    results.append(("Peak Splitting", test_peak_splitting()))
    results.append(("Overlap Detection", test_overlap_detection()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed!")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
