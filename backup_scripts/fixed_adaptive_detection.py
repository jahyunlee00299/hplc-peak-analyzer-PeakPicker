"""
Fixed version: Adaptive Peak Detection for all intensity scales
Resolves the issue with 1.0x scale detection
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.integrate import trapezoid
from typing import List, Optional
from dataclasses import dataclass

# Import the baseline corrector from the main script
from adaptive_baseline_peak_detection import AdaptiveBaselineCorrector


@dataclass
class Peak:
    """Peak information"""
    rt: float
    rt_start: float
    rt_end: float
    height: float
    area: float
    width: float
    index: int
    prominence: float
    snr: float


class FixedAdaptivePeakDetector:
    """Fixed version with improved noise estimation for all scales"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray, baseline_corrected: bool = False):
        self.time = time
        self.intensity = intensity
        self.baseline_corrected = baseline_corrected
        self.peaks = []

    def estimate_noise_level_robust(self) -> float:
        """
        Robust noise estimation using MAD (Median Absolute Deviation)
        Works better for signals with varying scales
        """
        # Use derivative to find flat regions
        if len(self.intensity) > 10:
            # Calculate first derivative
            derivative = np.abs(np.diff(self.intensity))

            # Find quiet regions (low derivative)
            threshold = np.percentile(derivative, 25)
            quiet_regions = derivative < threshold

            if np.any(quiet_regions):
                # Get intensity values in quiet regions
                quiet_indices = np.where(quiet_regions)[0]
                quiet_values = self.intensity[quiet_indices]

                # Calculate MAD (Median Absolute Deviation)
                median = np.median(quiet_values)
                mad = np.median(np.abs(quiet_values - median))

                # Convert MAD to standard deviation equivalent
                # (MAD * 1.4826 ≈ std for normal distribution)
                noise_std = mad * 1.4826

                # Ensure minimum noise level
                min_noise = np.ptp(self.intensity) * 0.001
                noise_std = max(noise_std, min_noise)
            else:
                # Fallback: use bottom 10% of signal
                noise_std = np.std(self.intensity[self.intensity < np.percentile(self.intensity, 10)])
        else:
            # Very short signal
            noise_std = np.std(self.intensity) * 0.1

        return noise_std

    def adaptive_peak_detection_fixed(
        self,
        min_snr: float = 3.0,
        min_prominence_factor: float = 0.005,
        min_width_seconds: float = 0.6,
        max_width_seconds: float = 120,
        min_distance_seconds: float = 1.2
    ) -> List[Peak]:
        """
        Fixed adaptive peak detection for all intensity scales
        """
        # Robust noise estimation
        noise_level = self.estimate_noise_level_robust()

        # Convert time constraints to samples
        time_step = np.mean(np.diff(self.time))
        time_step_seconds = time_step * 60

        min_width_samples = max(3, int(min_width_seconds / time_step_seconds))
        max_width_samples = int(max_width_seconds / time_step_seconds)
        min_distance_samples = max(1, int(min_distance_seconds / time_step_seconds))

        # Dynamic thresholds based on signal characteristics
        signal_range = np.ptp(self.intensity)

        # Adjust prominence based on signal scale
        if signal_range > 1000:
            # Large scale signal - use percentage-based prominence
            min_prominence = min_prominence_factor * signal_range
        else:
            # Small scale signal - use noise-based prominence
            min_prominence = max(min_prominence_factor * signal_range, min_snr * noise_level)

        # Height threshold
        min_height = min_snr * noise_level

        # Smooth signal for peak detection
        window_size = min(len(self.intensity), min_width_samples * 2 + 1)
        if window_size % 2 == 0:
            window_size += 1

        if len(self.intensity) >= window_size and window_size >= 3:
            smoothed = signal.savgol_filter(self.intensity, window_size, 2)
        else:
            smoothed = self.intensity.copy()

        # Find peaks with adjusted parameters
        try:
            peaks_idx, properties = signal.find_peaks(
                smoothed,
                height=min_height,
                prominence=min_prominence,
                width=min_width_samples,
                distance=min_distance_samples
            )
        except Exception as e:
            print(f"Peak detection error: {e}")
            return []

        # Process detected peaks
        self.peaks = []
        for i, peak_idx in enumerate(peaks_idx):
            # Get boundaries
            if 'left_bases' in properties:
                left_idx = properties['left_bases'][i]
                right_idx = properties['right_bases'][i]
            else:
                left_idx = max(0, peak_idx - min_width_samples)
                right_idx = min(len(self.intensity) - 1, peak_idx + min_width_samples)

            # Skip too wide peaks
            if right_idx - left_idx > max_width_samples:
                continue

            # Calculate peak properties
            peak_height = self.intensity[peak_idx]

            # Local baseline estimation
            if not self.baseline_corrected:
                baseline_level = min(self.intensity[left_idx], self.intensity[right_idx])
                peak_height_corrected = peak_height - baseline_level
            else:
                peak_height_corrected = peak_height

            # Calculate area
            peak_time = self.time[left_idx:right_idx + 1]
            peak_intensity = self.intensity[left_idx:right_idx + 1].copy()

            if not self.baseline_corrected:
                # Linear baseline correction
                baseline = np.linspace(
                    self.intensity[left_idx],
                    self.intensity[right_idx],
                    len(peak_intensity)
                )
                peak_intensity = peak_intensity - baseline

            area = trapezoid(np.maximum(peak_intensity, 0), peak_time)

            # Width and SNR
            width_samples = properties['widths'][i] if 'widths' in properties else right_idx - left_idx
            width_time = width_samples * time_step
            snr = peak_height_corrected / noise_level if noise_level > 0 else float('inf')

            # Prominence
            prominence = properties['prominences'][i] if 'prominences' in properties else peak_height_corrected

            peak = Peak(
                rt=self.time[peak_idx],
                rt_start=self.time[left_idx],
                rt_end=self.time[right_idx],
                height=peak_height_corrected,
                area=area,
                width=width_time,
                index=peak_idx,
                prominence=prominence,
                snr=snr
            )

            # Keep peaks with sufficient quality
            if peak.snr >= min_snr and peak.area > 0:
                self.peaks.append(peak)

        return self.peaks


def test_fixed_detection():
    """Test the fixed detection on EXPORT.CSV with all scales"""

    # Load data
    print("Loading HPLC data...")
    df = pd.read_csv('peakpicker/examples/EXPORT.CSV',
                     header=None, sep='\t', encoding='utf-16-le')

    time = df[0].values
    intensity = df[1].values

    # Shift to positive if needed
    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    print(f"Data: {len(time)} points, {time[0]:.3f} to {time[-1]:.3f} minutes")
    print(f"Intensity: {intensity.min():.2f} to {intensity.max():.2f}")

    # Test different scales
    scales = [1.0, 0.1, 0.01]
    fig, axes = plt.subplots(len(scales), 2, figsize=(12, 4*len(scales)))

    results = {}
    for idx, scale in enumerate(scales):
        print(f"\n{'='*40}")
        print(f"Testing scale {scale}x")
        print('='*40)

        # Scale intensity
        scaled_intensity = intensity * scale

        # Apply baseline correction
        corrector = AdaptiveBaselineCorrector(time, scaled_intensity)
        corrected = corrector.get_corrected_intensity(method='adaptive')

        # Detect peaks with fixed detector
        detector = FixedAdaptivePeakDetector(time, corrected, baseline_corrected=True)
        peaks = detector.adaptive_peak_detection_fixed(
            min_snr=3.0,
            min_prominence_factor=0.005,
            min_width_seconds=0.6,
            max_width_seconds=180,
            min_distance_seconds=1.2
        )

        # Store results
        results[f'scale_{scale}'] = {
            'peaks': peaks,
            'num_peaks': len(peaks),
            'noise_level': detector.estimate_noise_level_robust()
        }

        print(f"Noise level: {detector.estimate_noise_level_robust():.4f}")
        print(f"Peaks detected: {len(peaks)}")
        if peaks:
            print(f"Retention times: {[f'{p.rt:.2f}' for p in peaks]}")
            print(f"SNRs: {[f'{p.snr:.1f}' for p in peaks]}")

        # Plot
        axes[idx, 0].plot(time, scaled_intensity, 'b-', alpha=0.7, label='Raw')
        axes[idx, 0].plot(time, corrector.baseline, 'r--', alpha=0.8, label='Baseline')
        axes[idx, 0].set_title(f'Scale {scale}x - Raw & Baseline')
        axes[idx, 0].set_xlabel('Time (min)')
        axes[idx, 0].set_ylabel('Intensity')
        axes[idx, 0].legend()
        axes[idx, 0].grid(True, alpha=0.3)

        axes[idx, 1].plot(time, corrected, 'g-', alpha=0.7)
        axes[idx, 1].set_title(f'Corrected ({len(peaks)} peaks detected)')
        axes[idx, 1].set_xlabel('Time (min)')
        axes[idx, 1].set_ylabel('Intensity')
        axes[idx, 1].grid(True, alpha=0.3)

        # Mark peaks
        for peak in peaks:
            peak_mask = (time >= peak.rt_start) & (time <= peak.rt_end)
            axes[idx, 1].fill_between(
                time[peak_mask],
                0,
                corrected[peak_mask],
                alpha=0.3
            )
            # Add peak RT annotation
            axes[idx, 1].annotate(
                f'{peak.rt:.1f}',
                xy=(peak.rt, corrected[peak.index]),
                xytext=(peak.rt, corrected[peak.index] + 0.1 * np.max(corrected)),
                fontsize=8,
                ha='center'
            )

    plt.tight_layout()
    plt.savefig('fixed_detection_results.png', dpi=100)
    plt.show()

    # Summary
    print("\n" + "="*60)
    print("FIXED DETECTION SUMMARY")
    print("="*60)
    for scale_key, data in results.items():
        scale = float(scale_key.split('_')[1])
        print(f"\nScale {scale}x:")
        print(f"  - Peaks: {data['num_peaks']}")
        print(f"  - Noise: {data['noise_level']:.4f}")

    return results


if __name__ == "__main__":
    results = test_fixed_detection()