"""
Direct .D Folder Analysis
===========================

One-click pipeline: .D folder(s) -> parse -> baseline -> peaks -> report

Usage:
    # Analyze all .D folders in a sequence directory
    python analyze_direct.py "C:/path/to/sequence_folder/"

    # Analyze a single .D folder
    python analyze_direct.py "C:/path/to/SAMPLE.D"

    # Analyze with options
    python analyze_direct.py "C:/path/to/data/" -o results/ --detector RID1A --pattern "STD.*"
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.peakpicker.application.workflow import WorkflowBuilder
from src.peakpicker.application.batch_processor import BatchProcessor
from src.peakpicker.infrastructure.file_readers.d_folder_scanner import DFolderScanner


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )


def print_progress(current, total, sample_name, status):
    pct = (current / total * 100) if total > 0 else 0
    print(f"  [{current+1}/{total}] ({pct:.0f}%) {sample_name}: {status}")


def main():
    parser = argparse.ArgumentParser(
        description='Direct HPLC analysis from .D folders (no ChemStation needed)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'input_path',
        help='Path to .D folder or directory containing .D folders',
    )
    parser.add_argument(
        '-o', '--output',
        help='Output directory (default: input_path/analysis_results)',
        default=None,
    )
    parser.add_argument(
        '--detector',
        help='Preferred detector prefix (e.g., RID1A, VWD1A). Default: auto (RID first)',
        default=None,
    )
    parser.add_argument(
        '--pattern',
        help='Regex to filter .D folder names (e.g., "STD.*")',
        default=None,
    )
    parser.add_argument(
        '--exclude',
        help='Regex to exclude .D folder names',
        default=None,
    )
    parser.add_argument(
        '--no-plots',
        action='store_true',
        help='Skip plot generation (faster)',
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not search subdirectories for .D folders',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose logging',
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    input_path = Path(args.input_path)
    if not input_path.exists():
        print(f"ERROR: Path not found: {input_path}")
        return 1

    # Determine .D folders to process
    if input_path.is_dir() and input_path.suffix.lower() == '.d':
        d_folders = [input_path]
        default_output = input_path.parent / 'analysis_results'
    else:
        scanner = DFolderScanner(recursive=not args.no_recursive)
        d_folders = scanner.scan(
            input_path,
            pattern=args.pattern,
            exclude_pattern=args.exclude,
        )
        default_output = input_path / 'analysis_results'

    if not d_folders:
        print(f"No .D folders found in: {input_path}")
        return 1

    output_dir = Path(args.output) if args.output else default_output

    # Banner
    print("=" * 60)
    print("  PeakPicker - Direct .D Folder Analysis")
    print("=" * 60)
    print(f"  Input:    {input_path}")
    print(f"  Output:   {output_dir}")
    print(f"  Samples:  {len(d_folders)}")
    print(f"  Detector: {args.detector or 'auto (RID priority)'}")
    print("=" * 60)

    # Build workflow
    builder = WorkflowBuilder()
    builder.with_rainbow_reader(preferred_detector=args.detector)
    builder.with_default_baseline()
    builder.with_default_peak_detector()
    builder.with_excel_exporter(output_dir)

    if not args.no_plots:
        builder.with_plot_exporter(output_dir)

    workflow = builder.build()

    # Process batch
    processor = BatchProcessor(
        workflow=workflow,
        progress_callback=print_progress,
    )

    batch_result = processor.process_d_folders(
        d_folders=d_folders,
        output_dir=output_dir,
    )

    # Summary
    print()
    print("=" * 60)
    print("  ANALYSIS COMPLETE")
    print("=" * 60)
    n_ok = len(batch_result.results)
    n_total = len(d_folders)
    print(f"  Processed: {n_ok}/{n_total} samples")
    print(f"  Results:   {output_dir}")
    print(f"  Summary:   batch_summary.xlsx")
    print("=" * 60)

    return 0 if n_ok == n_total else 1


if __name__ == '__main__':
    sys.exit(main())
