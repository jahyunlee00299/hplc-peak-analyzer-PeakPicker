"""
Test script for Peak Detector
"""

import sys
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent))

from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector, detect_and_integrate_peaks


def test_peak_detection():
    """Test peak detection"""
    print("\n=== Testing Peak Detection ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        print(f"✅ Data loaded: {len(time)} points")

        # Create detector with auto thresholds
        detector = PeakDetector(time, intensity, auto_threshold=True)

        # Detect peaks
        peaks = detector.detect_peaks()

        print(f"✅ Detected {len(peaks)} peaks")

        if peaks:
            for i, peak in enumerate(peaks, 1):
                print(f"   Peak {i}: RT={peak.rt:.3f} min, Area={peak.area:.2f}, "
                      f"Height={peak.height:.2f}, Width={peak.width:.3f} min")

        # Get summary
        summary = detector.get_summary()
        print(f"\n✅ Summary:")
        print(f"   - Total peaks: {summary['num_peaks']}")
        print(f"   - Total area: {summary['total_area']:.2f}")
        print(f"   - Avg width: {summary['avg_peak_width']:.3f} min")
        print(f"   - Avg height: {summary['avg_peak_height']:.2f}")

        return len(peaks) > 0

    except Exception as e:
        print(f"❌ Error in peak detection: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_convenience_function():
    """Test convenience function"""
    print("\n=== Testing Convenience Function ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        # Use convenience function
        peaks, summary = detect_and_integrate_peaks(time, intensity, auto_threshold=True)

        print(f"✅ Detected {len(peaks)} peaks via convenience function")
        print(f"✅ Summary: {summary['num_peaks']} peaks, total area: {summary['total_area']:.2f}")

        return True

    except Exception as e:
        print(f"❌ Error in convenience function: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Peak Detector Tests")
    print("=" * 60)

    results = []

    # Test peak detection
    results.append(("Peak Detection", test_peak_detection()))

    # Test convenience function
    results.append(("Convenience Function", test_convenience_function()))

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
