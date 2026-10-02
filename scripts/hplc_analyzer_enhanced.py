"""
Enhanced HPLC Data Analysis Pipeline with Hybrid Baseline Correction
Integrates auto_export_keyboard and advanced baseline correction
"""

import argparse
import contextlib
import io
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import signal
from scipy.integrate import trapezoid

# Add repo root and src directory to path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))  # `src.` package imports
sys.path.insert(0, str(_REPO_ROOT / 'src'))  # flat module imports

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
        deconvolution_asymmetry_threshold: float = 1.2,
        half_peak_mode: str = 'none'
    ):
        # Constructor arguments, replayed by worker processes (--jobs > 1)
        self._init_kwargs = dict(
            data_directory=str(data_directory),
            output_directory=str(output_directory) if output_directory else None,
            use_hybrid_baseline=use_hybrid_baseline,
            enable_deconvolution=enable_deconvolution,
            deconvolution_asymmetry_threshold=deconvolution_asymmetry_threshold,
            half_peak_mode=half_peak_mode,
        )
        self.data_dir = Path(data_directory)
        self.output_dir = Path(output_directory) if output_directory else self.data_dir / "analysis_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_hybrid_baseline = use_hybrid_baseline
        self.enable_deconvolution = enable_deconvolution
        self.half_peak_mode = half_peak_mode

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
                print("  Applying baseline correction (with linear peaks)...")
                corrector = HybridBaselineCorrector(time, intensity)

                # Use optimize_baseline_with_linear_peaks method
                baseline, params = corrector.optimize_baseline_with_linear_peaks()
                corrected = intensity - baseline
                corrected = np.maximum(corrected, 0)  # No negative values

                baseline_method = params.get('method', 'robust_fit_with_flat_peaks')
                num_peaks_detected = params.get('num_peaks', 0)
                print(f"  Baseline method: {baseline_method} (detected {num_peaks_detected} peaks for flat baseline)")
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
        Two-pass adaptive peak detection for samples with large and small peaks

        Pass 1: Detect major peaks using signal-range-based threshold
        Pass 2: Detect minor peaks using noise-based threshold
        Then merge and deduplicate results

        Args:
            time: Time array
            intensity: Intensity array (baseline corrected)

        Returns:
            Tuple of (peak_indices, peak_data_list)
        """
        # Estimate noise level
        noise_level = self._estimate_noise(intensity)
        signal_range = np.ptp(intensity)

        # PASS 1: Detect major peaks (high threshold based on signal range)
        major_prominence = max(signal_range * 0.005, noise_level * 3)
        major_min_height = noise_level * 3
        major_peaks, major_props = signal.find_peaks(
            intensity,
            prominence=major_prominence,
            height=major_min_height,
            width=3,
            distance=20
        )

        # PASS 2: Detect minor peaks (low threshold based on noise level)
        # Use a much lower prominence threshold to catch small peaks
        # Significantly reduced to 2x noise level for very sensitive small peak detection
        minor_prominence = noise_level * 2  # ~2x noise level for small peaks
        minor_min_height = noise_level * 2  # Lower height threshold for small peaks
        minor_peaks, minor_props = signal.find_peaks(
            intensity,
            prominence=minor_prominence,
            height=minor_min_height,
            width=2,  # Relaxed from 3 to allow narrower peaks
            distance=5  # Reduced from 10 to catch closer small peaks
        )

        # Merge peaks and remove duplicates
        # Keep major peaks, add minor peaks that aren't too close to major peaks
        all_peaks = list(major_peaks)
        all_props_prominences = list(major_props['prominences'])
        all_props_widths = list(major_props.get('widths', [0] * len(major_peaks)))
        all_props_left_bases = list(major_props.get('left_bases', []))
        all_props_right_bases = list(major_props.get('right_bases', []))

        min_distance = 10  # Minimum distance to consider peaks as separate

        for i, minor_peak in enumerate(minor_peaks):
            # Check if this minor peak is too close to any major peak
            is_duplicate = False
            for major_peak in major_peaks:
                if abs(minor_peak - major_peak) < min_distance:
                    is_duplicate = True
                    break

            if not is_duplicate:
                all_peaks.append(minor_peak)
                all_props_prominences.append(minor_props['prominences'][i])
                all_props_widths.append(minor_props.get('widths', [0] * len(minor_peaks))[i])
                if 'left_bases' in minor_props:
                    all_props_left_bases.append(minor_props['left_bases'][i])
                if 'right_bases' in minor_props:
                    all_props_right_bases.append(minor_props['right_bases'][i])

        # Sort peaks by retention time
        sort_indices = np.argsort(all_peaks)
        peaks = np.array(all_peaks)[sort_indices]
        prominences = np.array(all_props_prominences)[sort_indices]
        widths = np.array(all_props_widths)[sort_indices] if all_props_widths else np.zeros(len(peaks))

        # Reconstruct properties dict
        properties = {
            'prominences': prominences,
            'widths': widths
        }
        if all_props_left_bases and all_props_right_bases:
            properties['left_bases'] = np.array(all_props_left_bases)[sort_indices]
            properties['right_bases'] = np.array(all_props_right_bases)[sort_indices]

        # Calculate peak properties
        peak_data = []
        for i, peak_idx in enumerate(peaks):
            # IMPROVED: Use relative height-based boundary detection
            # This prevents abnormally wide peaks caused by baseline issues
            peak_height = intensity[peak_idx]

            # Find boundaries where signal drops to 1% of peak height
            # This is more robust than scipy's prominence-based boundaries
            threshold = peak_height * 0.01  # 1% of peak height

            # Search left boundary
            left = peak_idx
            while left > 0 and intensity[left] > threshold:
                left -= 1

            # Search right boundary
            right = peak_idx
            while right < len(intensity) - 1 and intensity[right] > threshold:
                right += 1

            # Prevent peak boundaries from overlapping with adjacent peaks
            # Check if there's a next peak
            if i < len(peaks) - 1:
                next_peak_idx = peaks[i + 1]
                # Find the valley (minimum) between this peak and next peak
                valley_region = intensity[peak_idx:next_peak_idx]
                if len(valley_region) > 0:
                    valley_idx = peak_idx + np.argmin(valley_region)
                    # Right boundary should not exceed the valley
                    right = min(right, valley_idx)

            # Check if there's a previous peak
            if i > 0:
                prev_peak_idx = peaks[i - 1]
                # Find the valley between previous peak and this peak
                valley_region = intensity[prev_peak_idx:peak_idx]
                if len(valley_region) > 0:
                    valley_idx = prev_peak_idx + np.argmin(valley_region)
                    # Left boundary should not exceed the valley
                    left = max(left, valley_idx)

            # Apply maximum width constraint (e.g., 2 minutes for HPLC)
            # This prevents unreasonably wide peaks
            max_width_samples = int(2.0 / np.mean(np.diff(time)))  # 2 minutes
            if right - left > max_width_samples:
                # Shrink symmetrically around peak
                half_max_width = max_width_samples // 2
                left = max(0, peak_idx - half_max_width)
                right = min(len(intensity) - 1, peak_idx + half_max_width)

            # Ensure boundaries are valid
            left = max(0, left)
            right = min(len(intensity) - 1, right)

            # Calculate area using trapezoid integration with time in seconds
            # This matches Chemstation's physical integration approach
            peak_time = time[left:right+1]
            peak_intensity = intensity[left:right+1]

            # Trapezoid integration in seconds (matches Chemstation units)
            peak_time_sec = peak_time * 60  # Convert minutes to seconds

            # Half-peak quantification
            apex_rel = peak_idx - left  # apex index relative to peak region

            if self.half_peak_mode in ('left', 'right', 'auto') and apex_rel > 0 and apex_rel < len(peak_intensity) - 1:
                left_area = trapezoid(peak_intensity[:apex_rel+1], peak_time_sec[:apex_rel+1])
                right_area = trapezoid(peak_intensity[apex_rel:], peak_time_sec[apex_rel:])
                asymmetry_ratio = left_area / right_area if right_area > 0 else float('inf')

                if self.half_peak_mode == 'left':
                    half_area = left_area
                    area = half_area * 2
                    used_half = 'left'
                elif self.half_peak_mode == 'right':
                    half_area = right_area
                    area = half_area * 2
                    used_half = 'right'
                else:  # auto
                    if left_area <= right_area:
                        half_area = left_area
                        used_half = 'left'
                    else:
                        half_area = right_area
                        used_half = 'right'
                    area = half_area * 2

                asymmetry_warning = asymmetry_ratio > 1.5 or asymmetry_ratio < 0.67
            else:
                area = trapezoid(peak_intensity, peak_time_sec)
                left_area = trapezoid(peak_intensity[:max(1, apex_rel+1)], peak_time_sec[:max(1, apex_rel+1)]) if apex_rel > 0 else area / 2
                right_area = area - left_area
                asymmetry_ratio = left_area / right_area if right_area > 0 else 1.0
                asymmetry_warning = False
                used_half = 'none'
                half_area = area / 2

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
                'end_time': time[right],
                'half_peak_mode': used_half,
                'half_area': half_area,
                'full_area': left_area + right_area,
                'asymmetry_ratio': round(asymmetry_ratio, 3),
                'asymmetry_warning': asymmetry_warning,
            })

        return peaks, peak_data

    def _estimate_noise(self, intensity: np.ndarray) -> float:
        """
        Estimate noise level from baseline regions

        For samples with very large peaks, we need to estimate noise from
        quiet regions, not from the overall signal range.
        """
        # Use lower percentile to find quiet regions
        # Use a small positive threshold to avoid empty mask when all values are >= 0
        noise_region = np.percentile(intensity, 25)
        threshold = max(noise_region * 1.5, np.percentile(intensity, 30))
        quiet_mask = intensity < threshold

        if np.any(quiet_mask) and np.sum(quiet_mask) > 10:
            noise_std = np.std(intensity[quiet_mask])
        else:
            # Fallback: use very low percentile
            low_percentile = np.percentile(intensity, 10)
            if low_percentile > 0:
                noise_std = np.std(intensity[intensity < low_percentile])
            else:
                # If 10th percentile is 0, use 20th percentile
                noise_std = np.std(intensity[intensity < np.percentile(intensity, 20)])

            if noise_std == 0 or np.isnan(noise_std):
                noise_std = np.std(intensity) * 0.01

        # Don't use signal range for noise estimation when there are large peaks
        # Just use a minimum floor based on the quiet region
        min_noise = max(np.percentile(intensity, 5) * 0.01, 1.0)

        # Ensure we return a valid number
        result = max(noise_std, min_noise, 1.0)  # At least 1.0 to avoid division by zero

        # Final safety check for nan
        if np.isnan(result) or result <= 0:
            result = max(np.std(intensity) * 0.01, 1.0)

        return result

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

    def batch_analyze(self, file_pattern: str = "*.CSV", jobs: int = 1) -> List[Dict]:
        """
        Analyze all CSV files in the data directory

        Args:
            file_pattern: Pattern to match files
            jobs: Worker processes. 1 = the original serial path; >1 analyses
                files in parallel (one file per task). Results, output files and
                console output keep the sorted input-file order.

        Returns:
            List of results dictionaries
        """
        csv_files = sorted(self.data_dir.glob(file_pattern))

        if not csv_files:
            print(f"No files matching {file_pattern} found in {self.data_dir}")
            return []

        print(f"\nFound {len(csv_files)} files to analyze")
        print("="*60)

        jobs = min(max(1, int(jobs)), len(csv_files))
        if jobs == 1:
            results = []
            for csv_file in csv_files:
                result = self.analyze_csv_file(csv_file)
                results.append(result)
        else:
            print(f"Parallel analysis: {jobs} worker processes")
            results = self._analyze_parallel(csv_files, jobs)

        print("\n" + "="*60)
        print("BATCH ANALYSIS COMPLETE")
        print(f"Total files processed: {len(results)}")
        print(f"Results saved to: {self.output_dir}")

        return results

    def _analyze_parallel(self, csv_files: List[Path], jobs: int) -> List[Dict]:
        """File-level process pool; per-file console output is replayed in input order."""
        results: List[Dict] = []
        # Children inherit the environment: keep BLAS/OpenMP single-threaded so
        # N workers do not oversubscribe the cores.
        saved = {k: os.environ.get(k) for k in _BLAS_ENV}
        os.environ.update({k: '1' for k in _BLAS_ENV})
        try:
            with ProcessPoolExecutor(max_workers=jobs) as executor:
                futures = [executor.submit(_analyze_file_worker, self._init_kwargs, str(f))
                           for f in csv_files]
                for csv_file, future in zip(csv_files, futures):
                    try:
                        result, text = future.result()
                    except Exception as e:  # worker crash / unpicklable result
                        text = f"\nAnalyzing: {csv_file.name}\n  Error: {e}\n"
                        result = {'error': str(e), 'file': csv_file.name}
                    print(text, end='', flush=True)
                    results.append(result)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return results


_BLAS_ENV = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')


def _analyze_file_worker(init_kwargs: Dict, csv_path: str):
    """Top-level (picklable) worker: analyse one file, return (result, captured stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        analyzer = EnhancedHPLCAnalyzer(**init_kwargs)
        result = analyzer.analyze_csv_file(Path(csv_path))
    return result, buf.getvalue()


def default_jobs() -> int:
    """Default worker count: all cores but one, capped at 8."""
    return max(1, min((os.cpu_count() or 2) - 1, 8))


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
    parser.add_argument('--half-peak', choices=['none', 'left', 'right', 'auto'],
                        default='none', help='Half-peak quantification mode')

    parser.add_argument('--jobs', type=int, default=None, metavar='N',
                        help='Worker processes for file-level parallelism '
                             '(default: min(cpu_count-1, 8); 1 = serial). Results are identical.')

    args = parser.parse_args()
    jobs = default_jobs() if args.jobs is None else args.jobs

    # Create analyzer
    analyzer = EnhancedHPLCAnalyzer(
        data_directory=args.data_directory,
        output_directory=args.output,
        use_hybrid_baseline=not args.no_hybrid_baseline,
        enable_deconvolution=not args.no_deconvolution,
        deconvolution_asymmetry_threshold=args.asymmetry_threshold,
        half_peak_mode=args.half_peak
    )

    # Run batch analysis
    results = analyzer.batch_analyze(file_pattern=args.pattern, jobs=jobs)

    # Print summary
    successful = sum(1 for r in results if 'error' not in r)
    print(f"\nSuccessfully analyzed: {successful}/{len(results)} files")

    return 0 if successful == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())