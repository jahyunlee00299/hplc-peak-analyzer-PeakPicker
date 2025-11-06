"""
Advanced Baseline Correction and Peak Detection for HPLC Data
Optimized for signals with varying intensities (1x to 100x reduction)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal, sparse
from scipy.sparse.linalg import spsolve
from scipy.integrate import trapezoid
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class Peak:
    """Peak information"""
    rt: float  # Retention time at peak maximum
    rt_start: float  # Start of peak
    rt_end: float  # End of peak
    height: float  # Peak height (baseline-corrected)
    area: float  # Integrated peak area
    width: float  # Peak width at half height
    index: int  # Index in data array
    prominence: float  # Peak prominence
    snr: float  # Signal-to-noise ratio


class AdaptiveBaselineCorrector:
    """
    Advanced baseline correction methods for HPLC chromatograms
    """

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        self.time = time
        self.intensity = intensity
        self.baseline = None
        self.corrected_intensity = None

    def als_baseline(self, lam: float = 1e6, p: float = 0.001, niter: int = 20) -> np.ndarray:
        """
        Asymmetric Least Squares (ALS) baseline
        Optimized for HPLC with varying peak sizes

        Args:
            lam: Smoothness parameter (larger = smoother)
            p: Asymmetry parameter (smaller = better for positive peaks)
            niter: Number of iterations
        """
        L = len(self.intensity)
        D = sparse.diags([1, -2, 1], [0, -1, -2], shape=(L, L-2))
        D = lam * D.dot(D.transpose())
        w = np.ones(L)
        W = sparse.spdiags(w, 0, L, L)

        for i in range(niter):
            W.setdiag(w)
            Z = W + D
            z = spsolve(Z, w * self.intensity)
            w = p * (self.intensity > z) + (1 - p) * (self.intensity < z)

        self.baseline = z
        return z

    def arPLS_baseline(self, lam: float = 1e5, ratio: float = 0.001, niter: int = 100) -> np.ndarray:
        """
        Adaptive iteratively Reweighted Penalized Least Squares (arPLS)
        Better for complex baselines with drift

        Args:
            lam: Smoothness parameter
            ratio: Convergence ratio
            niter: Maximum iterations
        """
        L = len(self.intensity)
        D = sparse.diags([1, -2, 1], [0, -1, -2], shape=(L, L-2))
        H = lam * D.dot(D.transpose())
        w = np.ones(L)

        for i in range(niter):
            W = sparse.spdiags(w, 0, L, L)
            Z = W + H
            z = spsolve(Z, w * self.intensity)
            d = self.intensity - z
            dn = d[d < 0]

            if len(dn) == 0:
                break

            m = np.mean(dn)
            s = np.std(dn)
            w_new = 1 / (1 + np.exp(2 * (d - (2*s - m)) / s))

            if np.linalg.norm(w_new - w) / np.linalg.norm(w) < ratio:
                break

            w = w_new

        self.baseline = z
        return z

    def morphological_baseline(self, window_size: int = None, iterations: int = 2) -> np.ndarray:
        """
        Morphological baseline using erosion and dilation
        Good for preserving peak shapes

        Args:
            window_size: Size of structuring element (auto if None)
            iterations: Number of morphological operations
        """
        from scipy.ndimage import grey_opening, grey_closing

        if window_size is None:
            # Auto-determine based on typical peak width
            window_size = len(self.intensity) // 20

        baseline = self.intensity.copy()

        for _ in range(iterations):
            baseline = grey_opening(baseline, size=window_size)
            baseline = grey_closing(baseline, size=window_size)

        # Smooth the baseline
        baseline = signal.savgol_filter(baseline, window_size // 2 * 2 + 1, 3)

        self.baseline = baseline
        return baseline

    def rolling_ball_baseline(self, radius: int = None) -> np.ndarray:
        """
        Rolling ball algorithm for baseline estimation
        Intuitive and works well for varying peak sizes

        Args:
            radius: Ball radius (auto if None)
        """
        from scipy.ndimage import grey_opening

        if radius is None:
            radius = len(self.intensity) // 15

        # Apply morphological opening with ball-shaped structuring element
        baseline = grey_opening(self.intensity, size=radius)

        # Smooth the result
        if len(baseline) > 11:
            baseline = signal.savgol_filter(baseline, 11, 3)

        self.baseline = baseline
        return baseline

    def adaptive_iterative_baseline(self, window_size: int = 100, percentile: float = 10) -> np.ndarray:
        """
        Adaptive iterative baseline using local minima
        Excellent for varying peak intensities

        Args:
            window_size: Window for local minima detection
            percentile: Percentile for baseline points selection
        """
        baseline = self.intensity.copy()

        for iteration in range(5):
            # Find local minima in windows
            baseline_points = []
            indices = []

            for i in range(0, len(baseline), window_size // 2):
                end = min(i + window_size, len(baseline))
                window = baseline[i:end]
                if len(window) > 0:
                    # Get lowest percentile points in window
                    threshold = np.percentile(window, percentile)
                    mask = window <= threshold
                    if np.any(mask):
                        local_indices = np.where(mask)[0] + i
                        baseline_points.extend(baseline[local_indices])
                        indices.extend(local_indices)

            if len(indices) > 1:
                # Interpolate baseline through selected points
                from scipy.interpolate import UnivariateSpline
                indices = np.array(indices)
                baseline_points = np.array(baseline_points)

                # Sort by index
                sort_idx = np.argsort(indices)
                indices = indices[sort_idx]
                baseline_points = baseline_points[sort_idx]

                # Fit spline through baseline points
                spl = UnivariateSpline(indices, baseline_points, s=len(indices) * 0.1, k=3)
                new_baseline = spl(np.arange(len(self.intensity)))

                # Check convergence
                if np.max(np.abs(new_baseline - baseline)) < 0.01 * np.ptp(self.intensity):
                    break

                baseline = new_baseline

        self.baseline = baseline
        return baseline

    def get_corrected_intensity(self, method: str = 'adaptive', **kwargs) -> np.ndarray:
        """
        Get baseline-corrected intensity using specified method

        Args:
            method: Baseline method ('als', 'arpls', 'morphological', 'rolling_ball', 'adaptive')
            **kwargs: Method-specific parameters
        """
        methods = {
            'als': self.als_baseline,
            'arpls': self.arPLS_baseline,
            'morphological': self.morphological_baseline,
            'rolling_ball': self.rolling_ball_baseline,
            'adaptive': self.adaptive_iterative_baseline
        }

        if method not in methods:
            raise ValueError(f"Method {method} not recognized")

        baseline = methods[method](**kwargs)
        self.corrected_intensity = self.intensity - baseline

        # Ensure no negative values
        self.corrected_intensity = np.maximum(self.corrected_intensity, 0)

        return self.corrected_intensity


class AdaptivePeakDetector:
    """
    Adaptive peak detection for HPLC with varying signal intensities
    """

    def __init__(self, time: np.ndarray, intensity: np.ndarray, baseline_corrected: bool = False):
        self.time = time
        self.intensity = intensity
        self.baseline_corrected = baseline_corrected
        self.peaks = []

    def estimate_noise_level(self, percentile: float = 25) -> float:
        """Estimate noise level from quiet regions of chromatogram"""
        # Use lower percentile of signal as noise estimate
        noise_region = np.percentile(self.intensity, percentile)
        # Calculate standard deviation in quiet regions
        quiet_mask = self.intensity < noise_region * 1.5
        if np.any(quiet_mask):
            noise_std = np.std(self.intensity[quiet_mask])
        else:
            noise_std = np.std(self.intensity) * 0.1
        return noise_std

    def adaptive_peak_detection(
        self,
        min_snr: float = 3.0,
        min_prominence_factor: float = 0.01,
        min_width_seconds: float = 0.6,  # 0.01 minutes * 60
        max_width_seconds: float = 120,  # 2 minutes * 60
        min_distance_seconds: float = 1.2  # 0.02 minutes * 60
    ) -> List[Peak]:
        """
        Adaptive peak detection that adjusts to signal intensity

        Args:
            min_snr: Minimum signal-to-noise ratio
            min_prominence_factor: Min prominence as fraction of signal range
            min_width_seconds: Minimum peak width in seconds
            max_width_seconds: Maximum peak width in seconds
            min_distance_seconds: Minimum distance between peaks in seconds
        """
        # Estimate noise level
        noise_level = self.estimate_noise_level()

        # Convert time constraints to samples
        time_step = np.mean(np.diff(self.time))  # Time step in minutes
        time_step_seconds = time_step * 60  # Convert to seconds

        min_width_samples = max(3, int(min_width_seconds / time_step_seconds))
        max_width_samples = int(max_width_seconds / time_step_seconds)
        min_distance_samples = max(1, int(min_distance_seconds / time_step_seconds))

        # Dynamic prominence threshold
        signal_range = np.ptp(self.intensity)
        min_prominence = max(
            min_prominence_factor * signal_range,
            min_snr * noise_level
        )

        # Smooth signal for peak detection
        if len(self.intensity) > min_width_samples * 2:
            smoothed = signal.savgol_filter(
                self.intensity,
                min(len(self.intensity), min_width_samples * 2 + 1),
                3
            )
        else:
            smoothed = self.intensity.copy()

        # Find peaks
        peaks_idx, properties = signal.find_peaks(
            smoothed,
            height=min_snr * noise_level,
            prominence=min_prominence,
            width=min_width_samples,
            distance=min_distance_samples
        )

        # Process each peak
        self.peaks = []
        for i, peak_idx in enumerate(peaks_idx):
            # Get peak boundaries
            left_idx = properties['left_bases'][i] if 'left_bases' in properties else max(0, peak_idx - min_width_samples)
            right_idx = properties['right_bases'][i] if 'right_bases' in properties else min(len(self.intensity)-1, peak_idx + min_width_samples)

            # Refine boundaries by finding where signal drops to baseline level
            left_idx = self._refine_boundary(peak_idx, left_idx, direction='left', noise_level=noise_level)
            right_idx = self._refine_boundary(peak_idx, right_idx, direction='right', noise_level=noise_level)

            # Skip if peak is too wide (likely baseline artifact)
            if right_idx - left_idx > max_width_samples:
                continue

            # Calculate peak properties
            peak_height = self.intensity[peak_idx]
            if not self.baseline_corrected:
                # Estimate local baseline
                baseline_level = min(self.intensity[left_idx], self.intensity[right_idx])
                peak_height -= baseline_level

            # Calculate area
            peak_time = self.time[left_idx:right_idx+1]
            peak_intensity = self.intensity[left_idx:right_idx+1]
            if not self.baseline_corrected:
                baseline = np.linspace(
                    self.intensity[left_idx],
                    self.intensity[right_idx],
                    len(peak_intensity)
                )
                peak_intensity = peak_intensity - baseline

            area = trapezoid(np.maximum(peak_intensity, 0), peak_time)

            # Calculate width at half height
            width_samples = properties['widths'][i] if 'widths' in properties else right_idx - left_idx
            width_time = width_samples * time_step

            # Calculate SNR
            snr = peak_height / noise_level if noise_level > 0 else float('inf')

            # Calculate prominence
            prominence = properties['prominences'][i] if 'prominences' in properties else peak_height

            peak = Peak(
                rt=self.time[peak_idx],
                rt_start=self.time[left_idx],
                rt_end=self.time[right_idx],
                height=peak_height,
                area=area,
                width=width_time,
                index=peak_idx,
                prominence=prominence,
                snr=snr
            )

            # Only keep peaks with sufficient SNR and area
            if peak.snr >= min_snr and peak.area > 0:
                self.peaks.append(peak)

        return self.peaks

    def _refine_boundary(self, peak_idx: int, boundary_idx: int, direction: str, noise_level: float) -> int:
        """Refine peak boundary by finding where signal approaches baseline"""
        threshold = 2 * noise_level  # Signal level to consider as baseline

        if direction == 'left':
            # Search leftward from peak
            for i in range(peak_idx, max(0, boundary_idx - 50), -1):
                if self.intensity[i] < threshold:
                    return i
                # Also stop if we hit a local minimum that's significantly below peak
                if i > 0 and i < len(self.intensity) - 1:
                    if (self.intensity[i] < self.intensity[i-1] and
                        self.intensity[i] < self.intensity[i+1] and
                        self.intensity[i] < 0.1 * self.intensity[peak_idx]):
                        return i
        else:  # right
            # Search rightward from peak
            for i in range(peak_idx, min(len(self.intensity), boundary_idx + 50)):
                if self.intensity[i] < threshold:
                    return i
                # Also stop if we hit a local minimum
                if i > 0 and i < len(self.intensity) - 1:
                    if (self.intensity[i] < self.intensity[i-1] and
                        self.intensity[i] < self.intensity[i+1] and
                        self.intensity[i] < 0.1 * self.intensity[peak_idx]):
                        return i

        return boundary_idx


def analyze_chromatogram_with_scaling(
    time: np.ndarray,
    intensity: np.ndarray,
    scaling_factors: List[float] = [1, 0.1, 0.01],
    baseline_method: str = 'adaptive',
    plot_results: bool = True
) -> Dict:
    """
    Analyze chromatogram with different intensity scales

    Args:
        time: Time array (minutes)
        intensity: Intensity array
        scaling_factors: List of scaling factors to test
        baseline_method: Baseline correction method
        plot_results: Whether to plot results
    """
    results = {}

    if plot_results:
        fig, axes = plt.subplots(len(scaling_factors), 3, figsize=(15, 4*len(scaling_factors)))
        if len(scaling_factors) == 1:
            axes = axes.reshape(1, -1)

    for idx, scale in enumerate(scaling_factors):
        # Scale intensity
        scaled_intensity = intensity * scale

        # Apply baseline correction
        corrector = AdaptiveBaselineCorrector(time, scaled_intensity)
        corrected = corrector.get_corrected_intensity(method=baseline_method)

        # Detect peaks
        detector = AdaptivePeakDetector(time, corrected, baseline_corrected=True)
        peaks = detector.adaptive_peak_detection(
            min_snr=3.0,
            min_prominence_factor=0.005,
            min_width_seconds=0.6,
            max_width_seconds=180,
            min_distance_seconds=1.2
        )

        results[f'scale_{scale}'] = {
            'peaks': peaks,
            'baseline': corrector.baseline,
            'corrected': corrected,
            'num_peaks': len(peaks),
            'peak_rts': [p.rt for p in peaks],
            'peak_areas': [p.area for p in peaks],
            'peak_snrs': [p.snr for p in peaks]
        }

        if plot_results:
            # Plot raw with baseline
            axes[idx, 0].plot(time, scaled_intensity, 'b-', label='Raw', alpha=0.7)
            axes[idx, 0].plot(time, corrector.baseline, 'r--', label='Baseline', alpha=0.8)
            axes[idx, 0].set_title(f'Scale {scale}x - Raw & Baseline')
            axes[idx, 0].set_xlabel('Time (min)')
            axes[idx, 0].set_ylabel('Intensity')
            axes[idx, 0].legend()
            axes[idx, 0].grid(True, alpha=0.3)

            # Plot corrected
            axes[idx, 1].plot(time, corrected, 'g-', alpha=0.7)
            axes[idx, 1].set_title(f'Baseline Corrected ({len(peaks)} peaks)')
            axes[idx, 1].set_xlabel('Time (min)')
            axes[idx, 1].set_ylabel('Intensity')
            axes[idx, 1].grid(True, alpha=0.3)

            # Mark detected peaks
            for peak in peaks:
                peak_mask = (time >= peak.rt_start) & (time <= peak.rt_end)
                axes[idx, 1].fill_between(
                    time[peak_mask],
                    0,
                    corrected[peak_mask],
                    alpha=0.3,
                    label=f'RT:{peak.rt:.2f}'
                )

            # Plot peak properties
            if peaks:
                axes[idx, 2].bar(range(len(peaks)), [p.snr for p in peaks], alpha=0.6, label='SNR')
                axes[idx, 2].set_title('Peak Signal-to-Noise Ratios')
                axes[idx, 2].set_xlabel('Peak Index')
                axes[idx, 2].set_ylabel('SNR')
                axes[idx, 2].axhline(y=3, color='r', linestyle='--', label='Min SNR')
                axes[idx, 2].legend()
                axes[idx, 2].grid(True, alpha=0.3)

    if plot_results:
        plt.tight_layout()
        plt.show()

    return results


def optimize_parameters(
    time: np.ndarray,
    intensity: np.ndarray,
    known_peak_count: Optional[int] = None
) -> Dict:
    """
    Optimize detection parameters for the given chromatogram

    Args:
        time: Time array
        intensity: Intensity array
        known_peak_count: Expected number of peaks (if known)
    """
    baseline_methods = ['adaptive', 'als', 'arpls', 'morphological', 'rolling_ball']
    best_params = None
    best_score = -np.inf

    for method in baseline_methods:
        try:
            # Test baseline correction
            corrector = AdaptiveBaselineCorrector(time, intensity)
            corrected = corrector.get_corrected_intensity(method=method)

            # Test different SNR thresholds
            for min_snr in [2, 3, 5, 7]:
                for min_prom_factor in [0.001, 0.005, 0.01, 0.02]:
                    detector = AdaptivePeakDetector(time, corrected, baseline_corrected=True)
                    peaks = detector.adaptive_peak_detection(
                        min_snr=min_snr,
                        min_prominence_factor=min_prom_factor
                    )

                    # Score based on peak count and quality
                    score = 0
                    if peaks:
                        # Favor reasonable number of peaks
                        if known_peak_count:
                            score -= abs(len(peaks) - known_peak_count) * 10
                        else:
                            # Penalize too many or too few peaks
                            if 2 <= len(peaks) <= 50:
                                score += 10
                            else:
                                score -= abs(len(peaks) - 10)

                        # Favor high SNR peaks
                        avg_snr = np.mean([p.snr for p in peaks])
                        score += min(avg_snr, 20)

                        # Favor well-separated peaks
                        if len(peaks) > 1:
                            separations = [peaks[i+1].rt - peaks[i].rt for i in range(len(peaks)-1)]
                            score += min(np.mean(separations), 1) * 10

                    if score > best_score:
                        best_score = score
                        best_params = {
                            'baseline_method': method,
                            'min_snr': min_snr,
                            'min_prominence_factor': min_prom_factor,
                            'num_peaks': len(peaks),
                            'peaks': peaks
                        }
        except Exception as e:
            print(f"Error with method {method}: {e}")
            continue

    return best_params


# Example usage
if __name__ == "__main__":
    # Load the EXPORT.CSV data
    print("Loading HPLC data from EXPORT.CSV...")
    df = pd.read_csv('peakpicker/examples/EXPORT.CSV',
                     header=None, sep='\t', encoding='utf-16-le')

    time = df[0].values  # Time in minutes
    intensity = df[1].values

    # Shift to positive values if needed
    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    print(f"Data shape: {len(time)} points")
    print(f"Time range: {time[0]:.3f} to {time[-1]:.3f} minutes")
    print(f"Intensity range: {intensity.min():.2f} to {intensity.max():.2f}")

    # Analyze with different scaling factors
    print("\nAnalyzing with different intensity scales...")
    results = analyze_chromatogram_with_scaling(
        time, intensity,
        scaling_factors=[1, 0.1, 0.01],
        baseline_method='adaptive',
        plot_results=True
    )

    # Print summary
    print("\n" + "="*60)
    print("PEAK DETECTION SUMMARY")
    print("="*60)
    for scale_key, data in results.items():
        scale = float(scale_key.split('_')[1])
        print(f"\nScale Factor: {scale}x")
        print(f"Number of peaks detected: {data['num_peaks']}")
        if data['peaks']:
            print(f"Retention times: {[f'{rt:.2f}' for rt in data['peak_rts']]}")
            print(f"Average SNR: {np.mean(data['peak_snrs']):.1f}")
            print(f"Min/Max SNR: {min(data['peak_snrs']):.1f} / {max(data['peak_snrs']):.1f}")

    # Optimize parameters
    print("\n" + "="*60)
    print("OPTIMIZING PARAMETERS")
    print("="*60)
    best = optimize_parameters(time, intensity)
    if best:
        print(f"\nBest baseline method: {best['baseline_method']}")
        print(f"Optimal min SNR: {best['min_snr']}")
        print(f"Optimal prominence factor: {best['min_prominence_factor']}")
        print(f"Peaks detected: {best['num_peaks']}")