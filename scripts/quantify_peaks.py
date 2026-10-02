"""
Peak area quantification analysis
Quantifies every sample in a folder using the integrated peak detection system
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import re

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))  # `src.` package imports
sys.path.insert(0, str(_REPO_ROOT / 'src'))  # flat module imports
from hybrid_baseline import HybridBaselineCorrector
from peakpicker.infrastructure.quantification import chromatogram_plots

# Korean font settings (kept for CJK-capable rendering environments)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


class PeakQuantifier:
    """Peak area quantification analysis"""

    def __init__(self, half_peak_mode: str = 'none'):
        self.results = []
        self.half_peak_mode = half_peak_mode

    def quantify_sample(self, csv_file, baseline_method='robust_fit'):
        """Quantify a single sample"""
        # Load data
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity = df[1].values

        # Baseline correction
        corrector = HybridBaselineCorrector(time, intensity)
        corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
        baseline = corrector.generate_hybrid_baseline(
            method=baseline_method,
            enhanced_smoothing=True
        )

        # Correction and post-processing
        corrected_raw = intensity - baseline
        corrected = corrector.post_process_corrected_signal(
            corrected_raw,
            clip_negative=True,
            negative_threshold=-50.0
        )

        # Peak detection
        peaks_info = self._detect_peaks(time, corrected)

        return {
            'time': time,
            'intensity': intensity,
            'baseline': baseline,
            'corrected': corrected,
            'peaks': peaks_info
        }

    def _estimate_noise_level(self, corrected):
        """
        Robust noise level estimation using MAD (Median Absolute Deviation).

        Better than percentile-based estimation for signals with many peaks.
        """
        # Use derivative for noise estimation (less affected by peaks)
        derivative = np.diff(corrected)

        # MAD is more robust than standard deviation for non-Gaussian noise
        mad = np.median(np.abs(derivative - np.median(derivative)))

        # Convert MAD to standard deviation equivalent
        # For Gaussian: std ≈ 1.4826 * MAD
        noise_std = mad * 1.4826

        return noise_std

    def _estimate_snr(self, corrected, noise_level):
        """
        Estimate Signal-to-Noise Ratio for the chromatogram.

        Returns
        -------
        float
            Estimated SNR (signal peak / noise level)
        """
        signal_max = np.max(corrected)
        if noise_level > 0:
            return signal_max / noise_level
        return 100.0  # Default high SNR if noise is zero

    def _get_adaptive_parameters(self, corrected):
        """
        Calculate adaptive peak detection parameters based on SNR.

        Low SNR: More conservative (higher thresholds)
        High SNR: More sensitive (lower thresholds)
        """
        noise_level = self._estimate_noise_level(corrected)
        snr = self._estimate_snr(corrected, noise_level)
        signal_range = np.ptp(corrected)

        # Adaptive prominence based on SNR
        if snr > 100:
            # High SNR: Very sensitive detection
            prominence_factor = 0.0005
            height_factor = 0.3
            min_width = 1
        elif snr > 50:
            # Medium-high SNR: Sensitive detection
            prominence_factor = 0.001
            height_factor = 0.5
            min_width = 1
        elif snr > 20:
            # Medium SNR: Standard detection
            prominence_factor = 0.002
            height_factor = 1.0
            min_width = 2
        elif snr > 10:
            # Low SNR: Conservative detection
            prominence_factor = 0.005
            height_factor = 2.0
            min_width = 3
        else:
            # Very low SNR: Very conservative
            prominence_factor = 0.01
            height_factor = 3.0
            min_width = 5

        min_prominence = max(signal_range * prominence_factor, noise_level * height_factor)
        min_height = noise_level * height_factor

        return {
            'noise_level': noise_level,
            'snr': snr,
            'min_prominence': min_prominence,
            'min_height': min_height,
            'min_width': min_width
        }

    def _detect_peaks(self, time, corrected):
        """Peak detection and area calculation (SNR-based adaptive parameters)"""
        from scipy import signal
        from scipy.integrate import trapezoid

        # Get adaptive parameters based on SNR
        params = self._get_adaptive_parameters(corrected)
        noise_level = params['noise_level']
        min_prominence = params['min_prominence']
        min_height = params['min_height']
        min_width = params['min_width']

        # Detect positive peaks only
        peaks, props = signal.find_peaks(
            corrected,
            prominence=min_prominence,
            height=min_height,
            width=min_width,
            distance=15
        )

        peaks_info = []
        for i, peak_idx in enumerate(peaks):
            peak_height = corrected[peak_idx]

            # Peak-height-based boundary threshold (1% of the peak height)
            # This approach ensures consistent boundary detection for both small and large peaks
            boundary_threshold = max(peak_height * 0.01, noise_level * 0.5)

            # Find the point where the signal returns to baseline
            left_idx = peak_idx
            while left_idx > 0 and corrected[left_idx] > boundary_threshold:
                left_idx -= 1

            right_idx = peak_idx
            while right_idx < len(corrected) - 1 and corrected[right_idx] > boundary_threshold:
                right_idx += 1

            # Area calculation (converted to seconds)
            peak_region_time = time[left_idx:right_idx+1] * 60  # min -> sec
            peak_region_signal = np.maximum(corrected[left_idx:right_idx+1], 0)

            # Half-peak quantification
            apex_rel = peak_idx - left_idx  # apex index relative to peak region

            if self.half_peak_mode in ('left', 'right', 'auto') and apex_rel > 0 and apex_rel < len(peak_region_signal) - 1:
                left_area = trapezoid(peak_region_signal[:apex_rel+1], peak_region_time[:apex_rel+1])
                right_area = trapezoid(peak_region_signal[apex_rel:], peak_region_time[apex_rel:])
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
                area = trapezoid(peak_region_signal, peak_region_time)
                left_area = trapezoid(peak_region_signal[:max(1, apex_rel+1)], peak_region_time[:max(1, apex_rel+1)]) if apex_rel > 0 else area / 2
                right_area = area - left_area
                asymmetry_ratio = left_area / right_area if right_area > 0 else 1.0
                asymmetry_warning = False
                used_half = 'none'
                half_area = area / 2

            peaks_info.append({
                'index': peak_idx,
                'rt': time[peak_idx],
                'height': peak_height,
                'area': area,
                'prominence': props['prominences'][i],
                'width': time[right_idx] - time[left_idx],
                'left_idx': left_idx,
                'right_idx': right_idx,
                'half_peak_mode': used_half,
                'half_area': half_area,
                'full_area': left_area + right_area,
                'asymmetry_ratio': round(asymmetry_ratio, 3),
                'asymmetry_warning': asymmetry_warning,
            })

        # Sort by area
        peaks_info.sort(key=lambda p: p['area'], reverse=True)

        return peaks_info

    def analyze_folder(self, folder_path, create_individual_plots=True):
        """Analyze every sample in a folder"""
        folder = Path(folder_path)
        csv_files = sorted(folder.glob('*.csv'))

        print(f"\n{'='*80}")
        print(f"Folder: {folder.name}")
        print(f"{'='*80}")
        print(f"Found {len(csv_files)} samples\n")

        all_results = []
        sample_details = []  # store per-sample details

        for csv_file in csv_files:
            sample_name = csv_file.stem
            print(f"Analyzing: {sample_name}")

            try:
                result = self.quantify_sample(csv_file)

                # Extract info from the sample name
                sample_info = self._parse_sample_name(sample_name)

                # Peak info
                peaks = result['peaks']

                # Store results
                for i, peak in enumerate(peaks[:5], 1):  # top 5 peaks only
                    all_results.append({
                        'sample': sample_name,
                        'concentration': sample_info.get('concentration', 'unknown'),
                        'conc_numeric': sample_info.get('conc_numeric', 0),
                        'replicate': sample_info.get('replicate', 'unknown'),
                        'peak_rank': i,
                        'rt': peak['rt'],
                        'height': peak['height'],
                        'area': peak['area'],
                        'width': peak['width'],
                        'prominence': peak['prominence']
                    })

                print(f"  Peaks detected: {len(peaks)}")
                if len(peaks) > 0:
                    print(f"  Main peak RT: {peaks[0]['rt']:.2f} min, area: {peaks[0]['area']:.1f}")

                # Store sample details
                sample_details.append({
                    'name': sample_name,
                    'time': result['time'],
                    'intensity': result['intensity'],
                    'baseline': result['baseline'],
                    'corrected': result['corrected'],
                    'peaks': peaks
                })

            except Exception as e:
                print(f"  [Error] {e}")

        # Save individual chromatograms
        if create_individual_plots and len(sample_details) > 0:
            self.sample_details = sample_details

        return pd.DataFrame(all_results)

    def _parse_sample_name(self, sample_name):
        """Extract concentration and replicate info from the sample name"""
        info = {}

        # Extract only the concentration following the sample ID like STD01
        # e.g. STD01_0_625MM_1 -> 0.625mM
        #      STD01_10MM_1 -> 10mM

        # Look only for a concentration pattern after the SP/other ID
        conc_patterns = [
            # STD01_0_625MM form (SP/STD prefix)
            (r'SP\d+_(\d+_\d+)MM', lambda m: f"{m.group(1).replace('_', '.')}"),
            # STD01_10MM form
            (r'SP\d+_(\d+)MM', lambda m: f"{m.group(1)}"),
            # Generic pattern (no SP prefix)
            (r'_(\d+_\d+)MM', lambda m: f"{m.group(1).replace('_', '.')}"),
            (r'_(\d+)MM', lambda m: f"{m.group(1)}"),
        ]

        for pattern, formatter in conc_patterns:
            match = re.search(pattern, sample_name)
            if match:
                conc_value = formatter(match)
                info['concentration'] = conc_value
                info['conc_numeric'] = float(conc_value)
                break

        # Find the replicate number (trailing _number)
        rep_match = re.search(r'_(\d+)$', sample_name)
        if rep_match:
            info['replicate'] = int(rep_match.group(1))

        return info

    def create_summary_report(self, df, output_dir, reference_y0=None, reference_a=None):
        """Generate the summary report and compare against reference values"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check whether these are STD samples (sample name contains 'STD')
        is_std_samples = df['sample'].str.contains('STD', case=False, na=False).any()

        # Group by concentration (STD samples only)
        if is_std_samples and 'concentration' in df.columns and df['concentration'].nunique() > 1:
            # Filter to the main peak (rank 1) only
            main_peaks = df[df['peak_rank'] == 1].copy()

            # Sort by numeric concentration
            main_peaks['conc_value'] = main_peaks['conc_numeric']
            main_peaks = main_peaks[main_peaks['conc_value'] > 0]  # exclude unknown
            main_peaks = main_peaks.sort_values('conc_value')

            # Statistics by concentration
            summary = main_peaks.groupby('concentration').agg({
                'area': ['mean', 'std', 'count'],
                'rt': 'mean',
                'height': 'mean'
            }).round(2)

            print(f"\n{'='*80}")
            print("Main peak area summary by concentration")
            print(f"{'='*80}")
            print(summary)
        else:
            # Generic samples: visualize peak info
            print(f"\n{'='*80}")
            print("Generic sample analysis results")
            print(f"{'='*80}")
            self._plot_peak_information(df, output_dir)

        # Full results CSV
        full_file = output_dir / 'all_peaks_detailed.csv'
        df.to_csv(full_file, index=False, encoding='utf-8-sig')
        print(f"Full results saved: {full_file}")

        # Generate individual chromatograms
        chromatogram_files = self.create_individual_chromatograms(output_dir)

        # Generate overlay chromatograms
        overlay_files = self.create_overlay_chromatograms(output_dir)

        return df

    def _plot_peak_information(self, df, output_dir):
        """Visualize generic sample peak information"""
        return chromatogram_plots.plot_peak_information(df, output_dir)

    def create_individual_chromatograms(self, output_dir):
        """Visualize the chromatogram for each sample"""
        return chromatogram_plots.create_individual_chromatograms(getattr(self, 'sample_details', None), output_dir)

    def create_overlay_chromatograms(self, output_dir):
        """Overlay the chromatograms of similar samples"""
        return chromatogram_plots.create_overlay_chromatograms(getattr(self, 'sample_details', None), output_dir)


def main():
    """Main function"""
    import sys

    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = str(Path(__file__).parent.parent / "results" / "DEF_LC 2025-05-19 17-57-25")

    print("\n" + "="*80)
    print("Peak Area Quantification Analysis")
    print("="*80)

    quantifier = PeakQuantifier()

    # Analyze the folder
    df = quantifier.analyze_folder(folder_path)

    if len(df) > 0:
        # Generate the report (passing the reference values)
        output_dir = Path(folder_path) / 'quantification'
        reference_y0 = 2173.0209  # tag y0
        reference_a = 52004.0462   # tag a
        quantifier.create_summary_report(df, output_dir, reference_y0, reference_a)

        print(f"\n{'='*80}")
        print("Analysis complete!")
        print(f"{'='*80}")
        print(f"Results saved to: {output_dir}/")
    else:
        print("\nNo data was analyzed.")


if __name__ == '__main__':
    main()
