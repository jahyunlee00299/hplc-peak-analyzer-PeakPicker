"""
Improved Baseline Correction Algorithm
An improved hybrid baseline correction algorithm
"""

import numpy as np
from scipy import signal
from scipy.interpolate import UnivariateSpline, interp1d
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class BaselineAnchor:
    """Baseline anchor point"""
    index: int
    rt: float
    value: float
    type: str  # 'valley', 'local_min', 'boundary'
    confidence: float  # 0-1


class ImprovedBaselineCorrector:
    """Improved baseline correction algorithm"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        """
        Initialize corrector

        Args:
            time: Retention time array
            intensity: Signal intensity array
        """
        self.time = time
        self.intensity = intensity
        self.anchors: List[BaselineAnchor] = []

        # Automatically handle negative values
        if np.min(intensity) < 0:
            self.intensity = intensity - np.min(intensity)

    def find_anchors(
        self,
        valley_prominence_factor: float = 0.01,
        local_min_percentile: float = 5,
        min_anchor_distance: int = 15,
        smoothing_window: Optional[int] = None
    ) -> List[BaselineAnchor]:
        """
        Find baseline anchor points (improved algorithm)

        Args:
            valley_prominence_factor: Valley detection sensitivity
            local_min_percentile: lower percentile for local minimum
            min_anchor_distance: minimum distance between anchors (data points)
            smoothing_window: smoothing window size

        Returns:
            List of anchor points
        """
        anchors = []

        # 1. Smoothing
        if smoothing_window is None:
            smoothing_window = max(11, min(51, len(self.intensity) // 30))
        if smoothing_window % 2 == 0:
            smoothing_window += 1

        if len(self.intensity) > smoothing_window:
            smoothed = signal.savgol_filter(self.intensity, smoothing_window, 3)
        else:
            smoothed = self.intensity.copy()

        # 2. Valley detection (improved method)
        valleys = self._find_valleys_improved(
            smoothed,
            prominence_factor=valley_prominence_factor,
            window=smoothing_window
        )

        for v_idx in valleys:
            anchors.append(BaselineAnchor(
                index=v_idx,
                rt=self.time[v_idx],
                value=self.intensity[v_idx],
                type='valley',
                confidence=1.0
            ))

        # 3. Find Local Minimum within the segments between valleys (improved method)
        valley_indices = np.concatenate(([0], valleys, [len(self.intensity) - 1]))

        for i in range(len(valley_indices) - 1):
            start_idx = valley_indices[i]
            end_idx = valley_indices[i + 1]
            segment_length = end_idx - start_idx

            # Add a local minimum if the segment is long enough
            if segment_length > min_anchor_distance * 2:
                local_mins = self._find_local_minima_in_segment(
                    start_idx, end_idx,
                    percentile=local_min_percentile,
                    min_distance=min_anchor_distance
                )

                for lm_idx, confidence in local_mins:
                    # Check distance from valleys
                    if all(abs(lm_idx - v) > min_anchor_distance for v in valleys):
                        anchors.append(BaselineAnchor(
                            index=lm_idx,
                            rt=self.time[lm_idx],
                            value=self.intensity[lm_idx],
                            type='local_min',
                            confidence=confidence
                        ))

        # 4. Add boundary anchors
        if not any(a.index == 0 for a in anchors):
            anchors.append(BaselineAnchor(
                index=0,
                rt=self.time[0],
                value=self.intensity[0],
                type='boundary',
                confidence=0.8
            ))

        if not any(a.index == len(self.intensity) - 1 for a in anchors):
            anchors.append(BaselineAnchor(
                index=len(self.intensity) - 1,
                rt=self.time[-1],
                value=self.intensity[-1],
                type='boundary',
                confidence=0.8
            ))

        # 5. Sort and deduplicate (improved method)
        anchors = self._remove_close_anchors(anchors, min_anchor_distance)
        anchors.sort(key=lambda a: a.index)

        self.anchors = anchors
        return anchors

    def _find_valleys_improved(
        self,
        signal_data: np.ndarray,
        prominence_factor: float,
        window: int
    ) -> np.ndarray:
        """Improved Valley detection"""
        # Find peaks in the inverted signal
        inverted = -signal_data
        prominence = np.ptp(signal_data) * prominence_factor

        valleys, properties = signal.find_peaks(
            inverted,
            prominence=prominence,
            distance=window // 2,
            width=1
        )

        return valleys

    def _find_local_minima_in_segment(
        self,
        start_idx: int,
        end_idx: int,
        percentile: float,
        min_distance: int
    ) -> List[Tuple[int, float]]:
        """Find Local Minima within a segment (improved method)"""
        segment = self.intensity[start_idx:end_idx]

        if len(segment) < min_distance:
            return []

        # Lower-percentile threshold
        threshold = np.percentile(segment, percentile)

        # Find local minima among points at or below the threshold
        local_mins = []
        candidates = np.where(segment <= threshold)[0]

        if len(candidates) == 0:
            return []

        # Group candidates into clusters and pick the minimum from each cluster
        clusters = []
        current_cluster = [candidates[0]]

        for i in range(1, len(candidates)):
            if candidates[i] - candidates[i-1] <= min_distance // 2:
                current_cluster.append(candidates[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [candidates[i]]
        clusters.append(current_cluster)

        # Select the minimum value from each cluster
        for cluster in clusters:
            cluster_values = segment[cluster]
            min_idx_in_cluster = cluster[np.argmin(cluster_values)]
            global_idx = start_idx + min_idx_in_cluster

            # Compute confidence: higher when the surrounding slope is smaller
            confidence = self._calculate_confidence(global_idx)

            local_mins.append((global_idx, confidence))

        return local_mins

    def _calculate_confidence(self, idx: int, window: int = 5) -> float:
        """Compute the confidence of an anchor point"""
        if idx < window or idx >= len(self.intensity) - window:
            return 0.5

        # Standard deviation of the surrounding slope (lower = flatter = higher confidence)
        left_slope = abs(self.intensity[idx] - self.intensity[idx - window])
        right_slope = abs(self.intensity[idx + window] - self.intensity[idx])
        avg_slope = (left_slope + right_slope) / 2

        # Normalize (0-1 range)
        max_slope = np.ptp(self.intensity) * 0.1
        confidence = 1.0 / (1.0 + avg_slope / max_slope)

        return confidence

    def _remove_close_anchors(
        self,
        anchors: List[BaselineAnchor],
        min_distance: int
    ) -> List[BaselineAnchor]:
        """Remove anchors that are too close together (improved algorithm)"""
        if len(anchors) == 0:
            return []

        # Sort by index
        sorted_anchors = sorted(anchors, key=lambda a: a.index)

        # Priority: valley > boundary > local_min
        priority = {'valley': 3, 'boundary': 2, 'local_min': 1}

        filtered = [sorted_anchors[0]]

        for anchor in sorted_anchors[1:]:
            # Check the distance to the last added anchor
            if anchor.index - filtered[-1].index < min_distance:
                # Keep whichever has higher priority or confidence
                last = filtered[-1]

                if priority[anchor.type] > priority[last.type]:
                    filtered[-1] = anchor
                elif priority[anchor.type] == priority[last.type]:
                    if anchor.confidence > last.confidence:
                        filtered[-1] = anchor
            else:
                filtered.append(anchor)

        return filtered

    def generate_baseline(
        self,
        method: str = 'adaptive_spline',
        smooth_factor: float = 1.0,
        apply_rt_relaxation: bool = True
    ) -> np.ndarray:
        """
        Generate the baseline (improved method)

        Args:
            method: baseline generation method
                - 'adaptive_spline': confidence-weighted + RT-based adaptive spline
                - 'robust_spline': outlier removal + robust spline
                - 'linear': simple linear interpolation
            smooth_factor: smoothing strength (0-2)
            apply_rt_relaxation: whether to apply RT-based slope relaxation

        Returns:
            Baseline array
        """
        if len(self.anchors) == 0:
            self.find_anchors()

        if len(self.anchors) < 2:
            return np.zeros_like(self.intensity)

        indices = np.array([a.index for a in self.anchors])
        values = np.array([a.value for a in self.anchors])
        confidences = np.array([a.confidence for a in self.anchors])

        # Apply RT-based slope relaxation
        if apply_rt_relaxation:
            values = self._apply_rt_based_relaxation(indices, values)

        # Generate the baseline
        if method == 'adaptive_spline':
            baseline = self._adaptive_spline_baseline(
                indices, values, confidences, smooth_factor
            )
        elif method == 'robust_spline':
            baseline = self._robust_spline_baseline(
                indices, values, confidences, smooth_factor
            )
        elif method == 'linear':
            baseline = self._linear_baseline(indices, values)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Prevent the baseline from exceeding the signal
        baseline = np.minimum(baseline, self.intensity)

        # Smooth it out
        if len(baseline) > 21:
            baseline = signal.savgol_filter(baseline, 21, 2)
            baseline = np.minimum(baseline, self.intensity)

        # Remove negative values
        baseline = np.maximum(baseline, 0)

        return baseline

    def _apply_rt_based_relaxation(
        self,
        indices: np.ndarray,
        values: np.ndarray,
        rt_threshold: float = 0.5,  # RT difference threshold (min)
        max_slope_factor: float = 0.15  # maximum slope limit
    ) -> np.ndarray:
        """
        RT-based slope relaxation

        Relaxes a steep slope when the RT difference between adjacent anchors is large
        """
        if len(indices) < 2:
            return values

        relaxed_values = values.copy()

        for i in range(len(indices) - 1):
            rt_diff = self.time[indices[i+1]] - self.time[indices[i]]

            if rt_diff > rt_threshold:
                # Compute the slope
                value_diff = values[i+1] - values[i]
                index_diff = indices[i+1] - indices[i]

                if index_diff > 0:
                    slope = abs(value_diff / index_diff)
                    max_allowed_slope = np.ptp(self.intensity) * max_slope_factor / len(self.intensity)

                    # Relax the slope if it is too steep
                    if slope > max_allowed_slope:
                        # Adjust to the segment's minimum value
                        segment = self.intensity[indices[i]:indices[i+1]+1]
                        segment_min = np.percentile(segment, 2.5)

                        # Adjust to the lower value
                        if value_diff > 0:  # increasing segment
                            relaxed_values[i+1] = min(values[i+1], segment_min)
                        else:  # decreasing segment
                            relaxed_values[i] = min(values[i], segment_min)

        return relaxed_values

    def _adaptive_spline_baseline(
        self,
        indices: np.ndarray,
        values: np.ndarray,
        confidences: np.ndarray,
        smooth_factor: float
    ) -> np.ndarray:
        """Spline with confidence weighting applied"""
        if len(indices) < 4:
            return self._linear_baseline(indices, values)

        try:
            # Weight-based smoothing
            weights = confidences
            s = len(indices) * smooth_factor * (1 - np.mean(confidences) * 0.3)

            spl = UnivariateSpline(indices, values, w=weights, s=s, k=3)
            baseline = spl(np.arange(len(self.intensity)))
        except Exception:
            baseline = self._linear_baseline(indices, values)

        return baseline

    def _robust_spline_baseline(
        self,
        indices: np.ndarray,
        values: np.ndarray,
        confidences: np.ndarray,
        smooth_factor: float
    ) -> np.ndarray:
        """Robust spline after outlier removal"""
        if len(values) < 4:
            return self._linear_baseline(indices, values)

        # MAD-based outlier removal
        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad > 0:
            threshold = median + 3 * mad
            mask = values <= threshold
        else:
            mask = np.ones(len(values), dtype=bool)

        robust_indices = indices[mask]
        robust_values = values[mask]
        robust_weights = confidences[mask]

        if len(robust_indices) < 4:
            return self._linear_baseline(indices, values)

        try:
            spl = UnivariateSpline(
                robust_indices,
                robust_values,
                w=robust_weights,
                s=len(robust_indices) * smooth_factor,
                k=min(3, len(robust_indices) - 1)
            )
            baseline = spl(np.arange(len(self.intensity)))
        except Exception:
            baseline = self._linear_baseline(robust_indices, robust_values)

        return baseline

    def _linear_baseline(
        self,
        indices: np.ndarray,
        values: np.ndarray
    ) -> np.ndarray:
        """Simple linear interpolation"""
        f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
        return f(np.arange(len(self.intensity)))

    def apply_linear_to_peaks(
        self,
        baseline: np.ndarray,
        peak_indices: Optional[List[int]] = None,
        auto_detect: bool = True
    ) -> np.ndarray:
        """
        Apply a linear baseline under the peak regions

        Args:
            baseline: the original baseline
            peak_indices: list of peak indices (None = auto-detect)
            auto_detect: whether to automatically detect peaks

        Returns:
            The baseline with a linear segment applied under the peak regions
        """
        if peak_indices is None and auto_detect:
            # Automatic peak detection
            corrected = np.maximum(self.intensity - baseline, 0)
            noise_level = np.percentile(corrected, 25) * 1.5

            peaks, _ = signal.find_peaks(
                corrected,
                prominence=np.ptp(corrected) * 0.005,
                height=max(noise_level * 3, np.std(corrected) * 2)
            )
            peak_indices = peaks.tolist()

        if not peak_indices:
            return baseline

        linear_baseline = baseline.copy()

        for peak_idx in peak_indices:
            # Find the peak boundary (half-height method)
            peak_height = self.intensity[peak_idx] - baseline[peak_idx]

            if peak_height <= 0:
                continue

            half_height = baseline[peak_idx] + peak_height / 2

            # Left boundary
            left_idx = peak_idx
            while left_idx > 0 and self.intensity[left_idx] > half_height:
                left_idx -= 1

            # Right boundary
            right_idx = peak_idx
            while right_idx < len(self.intensity) - 1 and self.intensity[right_idx] > half_height:
                right_idx += 1

            # Apply the linear baseline
            if right_idx > left_idx:
                baseline_left = max(0, baseline[left_idx])
                baseline_right = max(0, baseline[right_idx])
                linear_baseline[left_idx:right_idx+1] = np.linspace(
                    baseline_left, baseline_right, right_idx - left_idx + 1
                )

        return linear_baseline

    def optimize_baseline(
        self,
        methods: Optional[List[str]] = None,
        use_linear_peaks: bool = True
    ) -> Tuple[np.ndarray, Dict]:
        """
        Automatically select the optimal baseline

        Args:
            methods: list of methods to try
            use_linear_peaks: whether to apply a linear baseline under the peaks

        Returns:
            (optimal baseline, parameter info)
        """
        if methods is None:
            methods = ['adaptive_spline', 'robust_spline']

        best_score = -np.inf
        best_baseline = None
        best_params = {}

        # Find anchor points
        self.find_anchors()

        # Try each method
        for method in methods:
            baseline = self.generate_baseline(method=method)

            # Apply a linear baseline under the peaks
            if use_linear_peaks:
                baseline = self.apply_linear_to_peaks(baseline)

            # Evaluate
            corrected = np.maximum(self.intensity - baseline, 0)
            score = self._evaluate_baseline(baseline, corrected)

            if score > best_score:
                best_score = score
                best_baseline = baseline
                best_params = {
                    'method': method,
                    'score': score,
                    'use_linear_peaks': use_linear_peaks,
                    'num_anchors': len(self.anchors)
                }

        return best_baseline, best_params

    def _evaluate_baseline(
        self,
        baseline: np.ndarray,
        corrected: np.ndarray
    ) -> float:
        """
        Evaluate baseline quality (improved method)

        Evaluation criteria:
        1. Fraction of negative values (lower is better)
        2. Baseline smoothness (should be moderately smooth)
        3. Peak preservation (more preserved is better)
        4. How close the baseline is to the signal (should not be too high)
        """
        # 1. Negative ratio (0-100 pts)
        neg_ratio = np.sum(corrected < 0) / len(corrected)
        neg_score = (1 - neg_ratio) * 100

        # 2. Smoothness (0-50 pts)
        if len(baseline) > 2:
            smoothness = np.std(np.diff(baseline, 2))
            max_smoothness = np.ptp(self.intensity) * 0.01
            smooth_score = max(0, 50 - smoothness / max_smoothness * 50)
        else:
            smooth_score = 25

        # 3. Peak preservation (0-50 pts)
        try:
            original_peaks = signal.find_peaks(
                self.intensity,
                prominence=np.ptp(self.intensity) * 0.02
            )[0]

            if len(original_peaks) > 0:
                corrected_peaks = signal.find_peaks(
                    corrected,
                    prominence=np.ptp(corrected) * 0.02
                )[0]
                preservation = min(1.0, len(corrected_peaks) / len(original_peaks))
            else:
                preservation = 1.0

            peak_score = preservation * 50
        except Exception:
            peak_score = 25

        # 4. Baseline height (0-25 pts) - penalized if too high
        baseline_ratio = np.median(baseline) / (np.median(self.intensity) + 1e-10)
        if baseline_ratio < 0.3:
            height_score = 25
        elif baseline_ratio < 0.5:
            height_score = 15
        else:
            height_score = 5

        # Combined score
        total_score = neg_score + smooth_score + peak_score + height_score

        return total_score


def process_exported_signal(
    csv_file: str,
    method: str = 'adaptive_spline',
    use_linear_peaks: bool = True,
    apply_rt_relaxation: bool = True
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict]:
    """
    Process an exported signal CSV file

    Args:
        csv_file: path to the CSV file
        method: baseline method
        use_linear_peaks: whether to apply a linear baseline under the peaks
        apply_rt_relaxation: whether to apply RT-based slope relaxation

    Returns:
        (time, intensity, baseline, info_dict)
    """
    import pandas as pd

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    # Baseline correction
    corrector = ImprovedBaselineCorrector(time, intensity)

    if method == 'auto':
        baseline, params = corrector.optimize_baseline(use_linear_peaks=use_linear_peaks)
    else:
        corrector.find_anchors()
        baseline = corrector.generate_baseline(
            method=method,
            apply_rt_relaxation=apply_rt_relaxation
        )
        if use_linear_peaks:
            baseline = corrector.apply_linear_to_peaks(baseline)

        params = {
            'method': method,
            'num_anchors': len(corrector.anchors),
            'use_linear_peaks': use_linear_peaks,
            'apply_rt_relaxation': apply_rt_relaxation
        }

    return time, intensity, baseline, params
