"""
Automated HPLC Data Analysis Pipeline
Processes Chemstation .ch files and generates peak integration reports
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime

from chemstation_parser import ChemstationParser
from peak_detector import PeakDetector
from result_exporter import ResultExporter


def detect_detector_type(file_path: Path) -> str:
    """
    Detect detector type from filename

    Args:
        file_path: Path to the chromatogram file

    Returns:
        Detector type string (e.g., 'RID', 'UV-Vis', 'MS', etc.)
    """
    filename = file_path.name.upper()

    if 'RID' in filename:
        return 'RID'
    elif 'DAD' in filename or 'VWD' in filename:
        return 'UV-Vis'
    elif 'FLD' in filename or 'FLU' in filename:
        return 'Fluorescence'
    elif 'MSD' in filename or 'MS' in filename:
        return 'MS'
    elif 'ELSD' in filename:
        return 'ELSD'
    else:
        return 'Signal'


class HPLCAnalyzer:
    """Main analyzer class for HPLC data processing"""

    def __init__(
        self,
        data_directory: str,
        output_directory: Optional[str] = None,
        prominence: Optional[float] = None,
        min_height: Optional[float] = None,
        min_width: float = 0.01,
    ):
        """
        Initialize HPLC analyzer

        Args:
            data_directory: Path to directory containing .D folders
            output_directory: Path to save results (default: data_directory/results)
            prominence: Minimum peak prominence
            min_height: Minimum peak height
            min_width: Minimum peak width in minutes
        """
        self.data_dir = Path(data_directory)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_directory}")

        # Set output directory
        if output_directory:
            self.output_dir = Path(output_directory)
        else:
            self.output_dir = self.data_dir / "analysis_results"

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Peak detection parameters
        self.prominence = prominence
        self.min_height = min_height
        self.min_width = min_width

        # Results storage
        self.results = []

    def find_ch_files(self, recursive: bool = True) -> List[Path]:
        """
        Find all .ch files in the data directory

        Args:
            recursive: Whether to search recursively

        Returns:
            List of paths to .ch files
        """
        if recursive:
            ch_files = list(self.data_dir.rglob("*.ch"))
        else:
            ch_files = list(self.data_dir.glob("*.ch"))

        print(f"Found {len(ch_files)} .ch files")
        return ch_files

    def analyze_file(self, ch_file: Path) -> Optional[Dict]:
        """
        Analyze a single .ch file

        Args:
            ch_file: Path to .ch file

        Returns:
            Dictionary with analysis results or None if failed
        """
        try:
            print(f"\nProcessing: {ch_file.name}")

            # Parse chromatogram data
            parser = ChemstationParser(str(ch_file))
            time, intensity = parser.read()
            metadata = parser.get_metadata()

            print(f"  [OK] Read {len(time)} data points")
            print(f"  [OK] Time range: {time[0]:.2f} - {time[-1]:.2f} min")

            # Detect peaks
            detector = PeakDetector(
                time,
                intensity,
                prominence=self.prominence,
                min_height=self.min_height,
                min_width=self.min_width,
            )
            peaks = detector.detect_peaks()

            print(f"  [OK] Detected {len(peaks)} peaks")

            # Print peak summary
            for i, peak in enumerate(peaks, 1):
                print(f"    Peak {i}: RT={peak.rt:.3f} min, Area={peak.area:.1f}, Height={peak.height:.1f}")

            # Prepare result dictionary
            result = {
                'file_path': str(ch_file),
                'sample_name': ch_file.parent.name,  # Use .D folder name as sample name
                'time': time,
                'intensity': intensity,
                'peaks': peaks,
                'metadata': metadata,
                'summary': detector.get_summary(),
            }

            return result

        except Exception as e:
            print(f"  [ERROR] Error processing {ch_file.name}: {str(e)}")
            return None

    def analyze_batch(
        self,
        recursive: bool = True,
        export_format: str = 'excel',
        create_plots: bool = True,
    ) -> List[Dict]:
        """
        Analyze all .ch files in the data directory

        Args:
            recursive: Whether to search recursively
            export_format: Output format ('excel', 'csv', or 'both')
            create_plots: Whether to create chromatogram plots

        Returns:
            List of analysis results
        """
        print(f"\n{'='*60}")
        print(f"HPLC Batch Analysis")
        print(f"Data directory: {self.data_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'='*60}")

        # Find all .ch files
        ch_files = self.find_ch_files(recursive=recursive)

        if not ch_files:
            print("No .ch files found!")
            return []

        # Analyze each file
        self.results = []
        for ch_file in ch_files:
            result = self.analyze_file(ch_file)
            if result:
                self.results.append(result)

        print(f"\n{'='*60}")
        print(f"Analysis Complete: {len(self.results)}/{len(ch_files)} files processed successfully")
        print(f"{'='*60}\n")

        # Export results
        if self.results:
            self.export_results(export_format, create_plots)

        return self.results

    def export_results(
        self,
        export_format: str = 'excel',
        create_plots: bool = True,
    ):
        """
        Export analysis results

        Args:
            export_format: Output format ('excel', 'csv', or 'both')
            create_plots: Whether to create chromatogram plots
        """
        exporter = ResultExporter(str(self.output_dir))

        print("\nExporting results...")

        # Export individual sample results
        for result in self.results:
            sample_name = result['sample_name']
            peaks = result['peaks']
            time = result['time']
            intensity = result['intensity']
            metadata = result['metadata']
            file_path = Path(result['file_path'])

            # Detect detector type
            detector_type = detect_detector_type(file_path)

            # Sanitize filename
            safe_filename = "".join(
                c if c.isalnum() or c in (' ', '-', '_') else '_'
                for c in sample_name
            )

            # Export peak data
            if export_format in ['excel', 'both']:
                exporter.export_peaks_to_excel(
                    peaks,
                    f"{safe_filename}_peaks",
                    sample_name,
                    metadata,
                )

            if export_format in ['csv', 'both']:
                exporter.export_peaks_to_csv(
                    peaks,
                    f"{safe_filename}_peaks",
                    sample_name,
                )

            # Create plot
            if create_plots:
                exporter.export_chromatogram_plot(
                    time,
                    intensity,
                    peaks,
                    f"{safe_filename}_chromatogram",
                    sample_name,
                    detector_type=detector_type,
                )

        # Export batch summary
        if len(self.results) > 1:
            exporter.export_batch_summary(
                self.results,
                f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )

        print(f"\n[SUCCESS] All results exported to: {self.output_dir}")

    def analyze_with_target_peaks(
        self,
        target_rts: List[float],
        tolerance: float = 0.1,
    ) -> Dict:
        """
        Analyze samples looking for specific retention times

        Args:
            target_rts: List of target retention times
            tolerance: Tolerance for RT matching (minutes)

        Returns:
            Dictionary mapping target RTs to found peaks across samples
        """
        if not self.results:
            self.analyze_batch()

        target_peak_data = {rt: [] for rt in target_rts}

        for result in self.results:
            sample_name = result['sample_name']
            time = result['time']
            intensity = result['intensity']

            detector = PeakDetector(
                time,
                intensity,
                prominence=self.prominence,
                min_height=self.min_height,
                min_width=self.min_width,
            )
            detector.detect_peaks()

            for target_rt in target_rts:
                peak = detector.get_peak_at_rt(target_rt, tolerance)
                if peak:
                    target_peak_data[target_rt].append({
                        'sample': sample_name,
                        'peak': peak,
                    })

        # Export target peak analysis
        self._export_target_peak_analysis(target_peak_data, tolerance)

        return target_peak_data

    def _export_target_peak_analysis(
        self,
        target_peak_data: Dict,
        tolerance: float,
    ):
        """Export target peak analysis results"""
        import pandas as pd

        output_path = self.output_dir / f"target_peaks_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for target_rt, peak_list in target_peak_data.items():
                if not peak_list:
                    continue

                data = []
                for item in peak_list:
                    data.append({
                        'Sample': item['sample'],
                        'Target RT': target_rt,
                        'Found RT': round(item['peak'].rt, 3),
                        'RT Difference': round(item['peak'].rt - target_rt, 3),
                        'Height': round(item['peak'].height, 2),
                        'Area': round(item['peak'].area, 2),
                        'Width (min)': round(item['peak'].width, 3),
                    })

                df = pd.DataFrame(data)
                sheet_name = f"RT_{target_rt:.2f}".replace('.', '_')
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        print(f"[SUCCESS] Target peak analysis saved: {output_path}")


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Automated HPLC Chromatogram Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all .ch files in a directory
  python hplc_analyzer.py "C:/Chem32/1/DATA"

  # Analyze with custom peak detection parameters
  python hplc_analyzer.py "C:/Chem32/1/DATA" --prominence 100 --min-height 50

  # Analyze specific subdirectory
  python hplc_analyzer.py "C:/Chem32/1/DATA/1. DeoxyNucleoside HPLC raw data"

  # Export as CSV instead of Excel
  python hplc_analyzer.py "C:/Chem32/1/DATA" --format csv

  # Look for specific retention times
  python hplc_analyzer.py "C:/Chem32/1/DATA" --target-rts 2.5 5.8 10.2
        """
    )

    parser.add_argument(
        'data_directory',
        type=str,
        help='Path to directory containing Chemstation .D folders'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output directory for results (default: data_directory/analysis_results)'
    )
    parser.add_argument(
        '--prominence',
        type=float,
        default=None,
        help='Minimum peak prominence (auto if not specified)'
    )
    parser.add_argument(
        '--min-height',
        type=float,
        default=None,
        help='Minimum peak height (auto if not specified)'
    )
    parser.add_argument(
        '--min-width',
        type=float,
        default=0.01,
        help='Minimum peak width in minutes (default: 0.01)'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['excel', 'csv', 'both'],
        default='excel',
        help='Output format (default: excel)'
    )
    parser.add_argument(
        '--no-plots',
        action='store_true',
        help='Do not create chromatogram plots'
    )
    parser.add_argument(
        '--target-rts',
        type=float,
        nargs='+',
        default=None,
        help='Target retention times to search for (space-separated)'
    )
    parser.add_argument(
        '--rt-tolerance',
        type=float,
        default=0.1,
        help='Tolerance for target RT matching in minutes (default: 0.1)'
    )

    args = parser.parse_args()

    try:
        # Create analyzer
        analyzer = HPLCAnalyzer(
            data_directory=args.data_directory,
            output_directory=args.output,
            prominence=args.prominence,
            min_height=args.min_height,
            min_width=args.min_width,
        )

        # Run batch analysis
        analyzer.analyze_batch(
            recursive=True,
            export_format=args.format,
            create_plots=not args.no_plots,
        )

        # Analyze target peaks if specified
        if args.target_rts:
            print(f"\nSearching for target retention times: {args.target_rts}")
            analyzer.analyze_with_target_peaks(
                args.target_rts,
                tolerance=args.rt_tolerance,
            )

        print("\n[SUCCESS] Analysis pipeline completed successfully!")
        return 0

    except Exception as e:
        print(f"\n[ERROR] Error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
