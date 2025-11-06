"""
Test script for Excel Exporter
"""

import sys
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent))

from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector
from modules.excel_exporter import ExcelExporter


def test_export_peaks():
    """Test export peaks to Excel"""
    print("\n=== Testing Peak Export ===")

    try:
        # Load sample data and detect peaks
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        detector = PeakDetector(time, intensity, auto_threshold=True)
        peaks = detector.detect_peaks()

        print(f"✅ Detected {len(peaks)} peaks")

        # Export to Excel
        exporter = ExcelExporter(output_dir="test_results")
        output_file = exporter.export_peaks(
            peaks,
            filename="test_sample",
            sample_name="Sample 1",
            metadata={"Instrument": "HPLC-RID", "Method": "Test Method"}
        )

        print(f"✅ Exported to Excel: {output_file}")

        # Verify file exists
        if Path(output_file).exists():
            print(f"✅ File verified: {Path(output_file).stat().st_size} bytes")
            return True
        else:
            print(f"❌ File not found: {output_file}")
            return False

    except Exception as e:
        print(f"❌ Error exporting peaks: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_export():
    """Test batch export"""
    print("\n=== Testing Batch Export ===")

    try:
        # Create sample data for multiple samples
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        # Simulate 3 samples
        batch_results = {}
        for i in range(1, 4):
            detector = PeakDetector(time, intensity, auto_threshold=True)
            peaks = detector.detect_peaks()
            batch_results[f"Sample_{i}"] = peaks

        print(f"✅ Prepared {len(batch_results)} samples")

        # Export batch
        exporter = ExcelExporter(output_dir="test_results")
        output_file = exporter.export_batch_results(
            batch_results,
            output_filename="test_batch"
        )

        print(f"✅ Batch exported to: {output_file}")

        if Path(output_file).exists():
            print(f"✅ File verified")
            return True
        else:
            return False

    except Exception as e:
        print(f"❌ Error in batch export: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_comparison_export():
    """Test comparison export"""
    print("\n=== Testing Comparison Export ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        # Create sample peaks
        detector = PeakDetector(time, intensity, auto_threshold=True)
        peaks = detector.detect_peaks()

        sample_peaks = {
            "Sample_1": peaks,
            "Sample_2": peaks,
            "Sample_3": peaks,
        }

        # Target RTs
        target_rts = [4.0, 5.0, 6.0]

        print(f"✅ Prepared comparison data for {len(sample_peaks)} samples")
        print(f"   Target RTs: {target_rts}")

        # Export comparison
        exporter = ExcelExporter(output_dir="test_results")
        output_file = exporter.export_comparison(
            sample_peaks,
            target_rts,
            output_filename="test_comparison",
            rt_tolerance=0.2
        )

        print(f"✅ Comparison exported to: {output_file}")

        if Path(output_file).exists():
            return True
        else:
            return False

    except Exception as e:
        print(f"❌ Error in comparison export: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Excel Exporter Tests")
    print("=" * 60)

    results = []

    # Test exports
    results.append(("Peak Export", test_export_peaks()))
    results.append(("Batch Export", test_batch_export()))
    results.append(("Comparison Export", test_comparison_export()))

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
        print("Check test_results/ directory for generated Excel files")
    else:
        print("\n⚠️ Some tests failed!")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
