"""
Example: Excel Export Features
"""

import sys
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent.parent))

from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector
from modules.baseline_handler import BaselineHandler
from modules.excel_exporter import ExcelExporter


def example_basic_export():
    """Example 1: Basic peak export"""
    print("\n" + "="*60)
    print("Example 1: Basic Peak Export")
    print("="*60)

    # Load sample data
    sample_file = Path(__file__).parent / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    print(f"✓ Loaded data: {len(time)} points")

    # Detect peaks
    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    print(f"✓ Detected {len(peaks)} peaks")

    # Export to Excel
    exporter = ExcelExporter(output_dir="../test_results")
    output_file = exporter.export_peaks(
        peaks=peaks,
        filename="example_basic_export",
        sample_name="Sample 1"
    )

    print(f"✓ Exported to: {output_file}")
    print(f"  File size: {Path(output_file).stat().st_size} bytes")


def example_export_with_metadata():
    """Example 2: Export with metadata"""
    print("\n" + "="*60)
    print("Example 2: Export with Metadata")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    # Baseline correction
    handler = BaselineHandler(time, intensity)
    baseline = handler.calculate_als_baseline()
    corrected = handler.apply_baseline_correction()

    print(f"✓ Applied ALS baseline correction")

    # Detect peaks on corrected data
    detector = PeakDetector(time, corrected, auto_threshold=True)
    peaks = detector.detect_peaks()

    print(f"✓ Detected {len(peaks)} peaks")

    # Prepare metadata
    metadata = {
        "Instrument": "HPLC-RID",
        "Column": "C18, 4.6x250mm, 5μm",
        "Mobile Phase": "Water:Methanol (60:40)",
        "Flow Rate": "1.0 mL/min",
        "Column Temperature": "30°C",
        "Injection Volume": "10 μL",
        "Detection": "RID",
        "Baseline Method": "ALS (lam=1e6, p=0.01)",
        "Peak Detection": "Auto threshold",
        "Analyst": "Example User",
        "Comments": "Baseline-corrected chromatogram"
    }

    print(f"✓ Prepared metadata ({len(metadata)} fields)")

    # Export with metadata
    exporter = ExcelExporter(output_dir="../test_results")
    output_file = exporter.export_peaks(
        peaks=peaks,
        filename="example_with_metadata",
        sample_name="Sample 1 (Baseline Corrected)",
        metadata=metadata
    )

    print(f"✓ Exported with metadata to: {output_file}")


def example_batch_export():
    """Example 3: Batch export"""
    print("\n" + "="*60)
    print("Example 3: Batch Export")
    print("="*60)

    # Simulate multiple samples
    sample_file = Path(__file__).parent / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    batch_results = {}

    # Create 5 simulated samples with slight variations
    for i in range(1, 6):
        print(f"\nProcessing Sample {i}...")

        # Add some random variation
        noise = np.random.normal(0, 5, len(intensity))
        varied_intensity = intensity + noise

        # Detect peaks
        detector = PeakDetector(time, varied_intensity, auto_threshold=True)
        peaks = detector.detect_peaks()

        print(f"  ✓ Detected {len(peaks)} peaks")

        # Store results
        batch_results[f"Sample_{i}"] = peaks

    print(f"\n✓ Processed {len(batch_results)} samples")

    # Export batch
    exporter = ExcelExporter(output_dir="../test_results")
    output_file = exporter.export_batch_results(
        batch_results=batch_results,
        output_filename="example_batch_export"
    )

    print(f"✓ Batch exported to: {output_file}")
    print(f"  Contains {len(batch_results)} sample sheets")


def example_comparison_export():
    """Example 4: Sample comparison at target RTs"""
    print("\n" + "="*60)
    print("Example 4: Sample Comparison Export")
    print("="*60)

    # Load data
    sample_file = Path(__file__).parent / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))

    # Detect peaks for standard
    detector = PeakDetector(time, intensity, auto_threshold=True)
    standard_peaks = detector.detect_peaks()

    print(f"✓ Standard: {len(standard_peaks)} peaks")

    # Simulate 3 samples with variations
    sample_peaks = {}
    sample_peaks["Standard"] = standard_peaks

    for i in range(1, 4):
        # Add variation
        noise = np.random.normal(0, 10, len(intensity))
        varied_intensity = intensity + noise

        detector = PeakDetector(time, varied_intensity, auto_threshold=True)
        peaks = detector.detect_peaks()

        sample_peaks[f"Sample_{i}"] = peaks
        print(f"✓ Sample {i}: {len(peaks)} peaks")

    # Define target RTs (based on detected peaks)
    if len(standard_peaks) >= 3:
        target_rts = [
            standard_peaks[0].rt,
            standard_peaks[1].rt,
            standard_peaks[2].rt
        ]
    else:
        target_rts = [4.0, 5.0, 6.0]  # Default

    print(f"\n✓ Target RTs for comparison: {[f'{rt:.2f}' for rt in target_rts]}")

    # Export comparison
    exporter = ExcelExporter(output_dir="../test_results")
    output_file = exporter.export_comparison(
        sample_peaks=sample_peaks,
        target_rts=target_rts,
        output_filename="example_comparison",
        rt_tolerance=0.15
    )

    print(f"✓ Comparison exported to: {output_file}")
    print(f"  Comparing {len(sample_peaks)} samples at {len(target_rts)} target RTs")


def example_complete_workflow():
    """Example 5: Complete workflow with all features"""
    print("\n" + "="*60)
    print("Example 5: Complete Workflow")
    print("="*60)

    # 1. Load data
    sample_file = Path(__file__).parent / "sample_chromatogram.csv"
    loader = DataLoader()
    time, intensity = loader.load_file(str(sample_file))
    print(f"✓ Step 1: Loaded data ({len(time)} points)")

    # 2. Baseline correction
    handler = BaselineHandler(time, intensity)
    baseline = handler.calculate_als_baseline(lam=1e6, p=0.01)
    corrected = handler.apply_baseline_correction()
    print(f"✓ Step 2: Applied baseline correction")
    print(f"  Baseline range: {baseline.min():.2f} - {baseline.max():.2f}")
    print(f"  Corrected range: {corrected.min():.2f} - {corrected.max():.2f}")

    # 3. Peak detection
    detector = PeakDetector(time, corrected, auto_threshold=True)
    peaks = detector.detect_peaks()
    print(f"✓ Step 3: Detected {len(peaks)} peaks")

    # 4. Peak statistics
    total_area = sum(p.area for p in peaks)
    for peak in peaks:
        peak.percent_area = (peak.area / total_area) * 100

    print(f"  Total area: {total_area:.2f}")
    print(f"  Average RT: {np.mean([p.rt for p in peaks]):.3f} min")

    # 5. Prepare comprehensive metadata
    metadata = {
        "Analysis Type": "Complete Workflow Example",
        "Instrument": "HPLC-RID",
        "Column": "C18, 4.6x250mm, 5μm",
        "Mobile Phase": "Water:Methanol (60:40)",
        "Flow Rate": "1.0 mL/min",
        "Temperature": "30°C",
        "Detection": "Refractive Index Detector",
        "Data Processing": "Baseline corrected (ALS)",
        "Peak Detection": "Auto threshold",
        "Total Area": f"{total_area:.2f}",
        "Number of Peaks": len(peaks),
        "RT Range": f"{time.min():.2f} - {time.max():.2f} min"
    }

    print(f"✓ Step 4: Prepared comprehensive metadata")

    # 6. Export to Excel
    exporter = ExcelExporter(output_dir="../test_results")
    output_file = exporter.export_peaks(
        peaks=peaks,
        filename="example_complete_workflow",
        sample_name="Complete Workflow Sample",
        metadata=metadata
    )

    print(f"✓ Step 5: Exported to Excel")
    print(f"\n✓ Complete workflow finished!")
    print(f"  Output file: {output_file}")
    print(f"  File size: {Path(output_file).stat().st_size} bytes")
    print(f"  Contains: Metadata + {len(peaks)} peaks + Summary statistics")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("EXCEL EXPORT EXAMPLES")
    print("="*70)

    example_basic_export()
    example_export_with_metadata()
    example_batch_export()
    example_comparison_export()
    example_complete_workflow()

    print("\n" + "="*70)
    print("All examples completed!")
    print("Check the ../test_results/ directory for generated Excel files")
    print("="*70)


if __name__ == "__main__":
    main()
