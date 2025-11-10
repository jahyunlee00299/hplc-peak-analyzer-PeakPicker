"""
Enhanced HPLC Data Analysis Pipeline with Hybrid Baseline Correction
Integrates auto_export_keyboard and advanced baseline correction
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import signal
from scipy.integrate import trapezoid

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from hybrid_baseline import HybridBaselineCorrector
from peak_deconvolution import PeakDeconvolution, DeconvolutionResult


class EnhancedHPLCAnalyzer:
    """Enhanced HPLC analyzer with hybrid baseline correction"""

    def __init__(
        self,
        data_directory: str,
        output_directory: Optional[str] = None,
        use_hybrid_baseline: bool = True,
        enable_deconvolution: bool = True,
        deconvolution_asymmetry_threshold: float = 1.2
    ):
        self.data_dir = Path(data_directory)
        self.output_dir = Path(output_directory) if output_directory else self.data_dir / "analysis_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_hybrid_baseline = use_hybrid_baseline
        self.enable_deconvolution = enable_deconvolution

        # Initialize peak deconvolution analyzer
        if self.enable_deconvolution:
            self.deconvolution = PeakDeconvolution(
                min_asymmetry=deconvolution_asymmetry_threshold,
                min_shoulder_ratio=0.1,
                max_components=4
            )
        else:
            self.deconvolution = None

    def analyze_csv_file(self, csv_file: Path) -> Dict:
        """
        Analyze a single CSV file exported from Chemstation

        Args:
            csv_file: Path to CSV file

        Returns:
            Dictionary with analysis results
        """
        print(f"\nAnalyzing: {csv_file.name}")

        try:
            # Load CSV data
            df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
            time = df[0].values
            intensity = df[1].values

            # Shift to positive if needed
            if np.min(intensity) < 0:
                intensity = intensity - np.min(intensity)

            print(f"  Data points: {len(time)}")
            print(f"  Time range: {time[0]:.2f} - {time[-1]:.2f} min")
            print(f"  Intensity range: {intensity.min():.2f} - {intensity.max():.2f}")

            # Apply hybrid baseline correction
            if self.use_hybrid_baseline:
                print("  Applying hybrid baseline correction...")
                corrector = HybridBaselineCorrector(time, intensity)
                baseline, best_params = corrector.optimize_baseline()
                corrected = intensity - baseline
                corrected = np.maximum(corrected, 0)  # No negative values

                print(f"  Best baseline method: {best_params.get('method', 'N/A')}")
            else:
                corrected = intensity
                baseline = np.zeros_like(intensity)

            # Peak detection
            print("  Detecting peaks...")
            peaks, peak_data = self._detect_peaks_adaptive(time, corrected)

            print(f"  Peaks detected: {len(peaks)}")

            # Peak deconvolution
            deconvolution_results = []
            if self.enable_deconvolution and self.deconvolution:
                print("  Analyzing peaks for deconvolution...")
                deconvolution_results = self._apply_deconvolution(time, corrected, peak_data)
                n_deconvolved = sum(1 for dr in deconvolution_results if dr and dr.success and dr.n_components > 1)
                if n_deconvolved > 0:
                    print(f"  Deconvolved {n_deconvolved} peaks into multiple components")

            # Create results
            results = {
                'file': csv_file.name,
                'time': time,
                'intensity': intensity,
                'baseline': baseline,
                'corrected': corrected,
                'peaks': peaks,
                'peak_data': peak_data,
                'deconvolution_results': deconvolution_results,
                'analysis_date': datetime.now().isoformat()
            }

            # Export results
            self._export_results(csv_file, results)

            return results

        except Exception as e:
            print(f"  Error: {e}")
            return {'error': str(e), 'file': csv_file.name}

    def _detect_peaks_adaptive(self, time: np.ndarray, intensity: np.ndarray) -> tuple:
        """
        Adaptive peak detection

        Args:
            time: Time array
            intensity: Intensity array (baseline corrected)

        Returns:
            Tuple of (peak_indices, peak_data_list)
        """
        # Estimate noise level
        noise_level = self._estimate_noise(intensity)

        # Dynamic thresholds
        signal_range = np.ptp(intensity)
        min_prominence = max(signal_range * 0.005, noise_level * 3)
        min_height = noise_level * 3

        # Find peaks
        peaks, properties = signal.find_peaks(
            intensity,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        # Calculate peak properties
        peak_data = []
        for i, peak_idx in enumerate(peaks):
            # Get boundaries
            if 'left_bases' in properties:
                left = properties['left_bases'][i]
                right = properties['right_bases'][i]
            else:
                left = max(0, peak_idx - 10)
                right = min(len(intensity) - 1, peak_idx + 10)

            # Calculate area
            peak_time = time[left:right+1]
            peak_intensity = intensity[left:right+1]
            area = trapezoid(peak_intensity, peak_time)

            # Calculate SNR
            snr = intensity[peak_idx] / noise_level if noise_level > 0 else float('inf')

            peak_data.append({
                'peak_number': i + 1,
                'retention_time': time[peak_idx],
                'height': intensity[peak_idx],
                'area': area,
                'width': properties['widths'][i] * np.mean(np.diff(time)) if 'widths' in properties else 0,
                'prominence': properties['prominences'][i] if 'prominences' in properties else 0,
                'snr': snr,
                'start_time': time[left],
                'end_time': time[right]
            })

        return peaks, peak_data

    def _estimate_noise(self, intensity: np.ndarray) -> float:
        """Estimate noise level"""
        # Use lower percentile
        noise_region = np.percentile(intensity, 25)
        quiet_mask = intensity < noise_region * 1.5
        if np.any(quiet_mask):
            noise_std = np.std(intensity[quiet_mask])
        else:
            noise_std = np.std(intensity) * 0.1

        return max(noise_std, np.ptp(intensity) * 0.001)

    def _apply_deconvolution(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        peak_data: List[Dict]
    ) -> List[Optional[DeconvolutionResult]]:
        """
        Apply peak deconvolution to detected peaks.

        Args:
            time: Time array
            intensity: Intensity array (baseline corrected)
            peak_data: List of peak dictionaries from peak detection

        Returns:
            List of DeconvolutionResult objects (None if peak not deconvolved)
        """
        deconvolution_results = []

        for peak_info in peak_data:
            # Find indices for peak boundaries
            start_rt = peak_info['start_time']
            end_rt = peak_info['end_time']

            start_idx = np.argmin(np.abs(time - start_rt))
            end_idx = np.argmin(np.abs(time - end_rt))

            # Analyze peak for deconvolution
            result = self.deconvolution.analyze_peak(
                time,
                intensity,
                start_idx,
                end_idx,
                force_deconvolution=False  # Only deconvolve if needed
            )

            deconvolution_results.append(result)

        return deconvolution_results

    def _export_results(self, csv_file: Path, results: Dict):
        """Export analysis results to Excel"""
        output_file = self.output_dir / f"{csv_file.stem}_peaks.xlsx"

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Count deconvolved peaks
            n_deconvolved = 0
            total_components = 0
            if 'deconvolution_results' in results:
                for dr in results['deconvolution_results']:
                    if dr and dr.success and dr.n_components > 1:
                        n_deconvolved += 1
                        total_components += dr.n_components

            # Summary sheet
            summary_data = {
                'Sample Name': [csv_file.stem],
                'Analysis Date': [results['analysis_date']],
                'Number of Peaks': [len(results['peaks'])],
                'Deconvolved Peaks': [n_deconvolved],
                'Total Components': [total_components if n_deconvolved > 0 else len(results['peaks'])],
                'Total Area': [sum(p['area'] for p in results['peak_data'])],
                'Time Range': [f"{results['time'][0]:.2f} - {results['time'][-1]:.2f} min"]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

            # Peak details sheet
            if results['peak_data']:
                peak_df = pd.DataFrame(results['peak_data'])
                # Calculate percent area
                total_area = peak_df['area'].sum()
                peak_df['percent_area'] = (peak_df['area'] / total_area * 100) if total_area > 0 else 0
                peak_df.to_excel(writer, sheet_name='Peaks', index=False)

            # Deconvolved peaks sheet
            if 'deconvolution_results' in results and any(dr and dr.success for dr in results['deconvolution_results']):
                deconv_data = []

                for i, dr in enumerate(results['deconvolution_results']):
                    if dr and dr.success:
                        original_peak = results['peak_data'][i]

                        for j, component in enumerate(dr.components):
                            deconv_data.append({
                                'Original_Peak_Number': original_peak['peak_number'],
                                'Original_RT': original_peak['retention_time'],
                                'Component_Number': j + 1,
                                'Component_RT': component.retention_time,
                                'Component_Height': component.amplitude,
                                'Component_Area': component.area,
                                'Component_Area_Percent': component.area_percent,
                                'Sigma': component.sigma,
                                'Is_Shoulder': component.is_shoulder,
                                'Asymmetry': component.asymmetry,
                                'Start_RT': component.start_rt,
                                'End_RT': component.end_rt,
                                'Fit_Quality_R2': dr.fit_quality,
                                'RMSE': dr.rmse,
                                'Method': dr.method
                            })

                if deconv_data:
                    deconv_df = pd.DataFrame(deconv_data)
                    deconv_df.to_excel(writer, sheet_name='Deconvolved_Peaks', index=False)

        print(f"  Results saved: {output_file.name}")

    def batch_analyze(self, file_pattern: str = "*.CSV") -> List[Dict]:
        """
        Analyze all CSV files in the data directory

        Args:
            file_pattern: Pattern to match files

        Returns:
            List of results dictionaries
        """
        csv_files = sorted(self.data_dir.glob(file_pattern))

        if not csv_files:
            print(f"No files matching {file_pattern} found in {self.data_dir}")
            return []

        print(f"\nFound {len(csv_files)} files to analyze")
        print("="*60)

        results = []
        for csv_file in csv_files:
            result = self.analyze_csv_file(csv_file)
            results.append(result)

        print("\n" + "="*60)
        print("BATCH ANALYSIS COMPLETE")
        print(f"Total files processed: {len(results)}")
        print(f"Results saved to: {self.output_dir}")

        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Enhanced HPLC Data Analysis with Hybrid Baseline Correction'
    )
    parser.add_argument(
        'data_directory',
        help='Directory containing CSV files exported from Chemstation'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output directory for results (default: data_directory/analysis_results)',
        default=None
    )
    parser.add_argument(
        '--no-hybrid-baseline',
        action='store_true',
        help='Disable hybrid baseline correction'
    )
    parser.add_argument(
        '--no-deconvolution',
        action='store_true',
        help='Disable peak deconvolution for overlapping peaks'
    )
    parser.add_argument(
        '--asymmetry-threshold',
        type=float,
        default=1.2,
        help='Asymmetry threshold for triggering deconvolution (default: 1.2)'
    )
    parser.add_argument(
        '--pattern',
        default='*.CSV',
        help='File pattern to match (default: *.CSV)'
    )

    args = parser.parse_args()

    # Create analyzer
    analyzer = EnhancedHPLCAnalyzer(
        data_directory=args.data_directory,
        output_directory=args.output,
        use_hybrid_baseline=not args.no_hybrid_baseline,
        enable_deconvolution=not args.no_deconvolution,
        deconvolution_asymmetry_threshold=args.asymmetry_threshold
    )

    # Run batch analysis
    results = analyzer.batch_analyze(file_pattern=args.pattern)

    # Print summary
    successful = sum(1 for r in results if 'error' not in r)
    print(f"\nSuccessfully analyzed: {successful}/{len(results)} files")

    return 0 if successful == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())