"""
Test script for PeakPicker modules
"""

import sys
from pathlib import Path

# Add modules to path
sys.path.append(str(Path(__file__).parent))

from modules.data_loader import DataLoader
from modules.visualizer import ChromatogramVisualizer


def test_data_loader():
    """Test data loading module"""
    print("\n=== Testing Data Loader ===")

    # Test with sample CSV file
    sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"

    if not sample_file.exists():
        print(f"❌ Sample file not found: {sample_file}")
        return False

    try:
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        print(f"✅ Data loaded successfully!")
        print(f"   - Data points: {len(time)}")
        print(f"   - Time range: {time.min():.2f} - {time.max():.2f} min")
        print(f"   - Intensity range: {intensity.min():.2f} - {intensity.max():.2f}")

        # Get data info
        info = loader.get_data_info()
        print(f"\nData Info:")
        for key, value in info.items():
            print(f"   - {key}: {value}")

        return True

    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_visualizer():
    """Test visualizer module"""
    print("\n=== Testing Visualizer ===")

    try:
        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        # Create visualizer
        visualizer = ChromatogramVisualizer()

        # Test basic plot
        fig = visualizer.plot_chromatogram(
            time, intensity,
            title="Test Chromatogram",
            color="blue"
        )

        # Save plot
        output_file = Path(__file__).parent / "test_output.png"
        visualizer.save_figure(str(output_file))

        print(f"✅ Chromatogram plotted successfully!")
        print(f"   - Saved to: {output_file}")

        # Test with time range
        visualizer.clear()
        fig = visualizer.plot_interactive_region(
            time, intensity,
            time_range=(1.0, 3.0),
            title="Test Chromatogram - Zoomed"
        )

        output_file2 = Path(__file__).parent / "test_output_zoomed.png"
        visualizer.save_figure(str(output_file2))

        print(f"✅ Zoomed chromatogram plotted successfully!")
        print(f"   - Saved to: {output_file2}")

        return True

    except Exception as e:
        print(f"❌ Error in visualizer: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("PeakPicker Module Tests")
    print("=" * 60)

    results = []

    # Test data loader
    results.append(("Data Loader", test_data_loader()))

    # Test visualizer
    results.append(("Visualizer", test_visualizer()))

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
