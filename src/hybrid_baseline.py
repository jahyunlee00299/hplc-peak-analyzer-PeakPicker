"""
Hybrid Baseline Correction
Advanced baseline correction combining Valley points and Local Minimum
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import interp1d, UnivariateSpline
from typing import List, Tuple, Dict
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class BaselinePoint:
    """Baseline anchor point"""
    index: int
    value: float
    type: str  # 'valley', 'local_min', 'boundary'
    confidence: float  # 0-1, higher means more confident


class HybridBaselineCorrector:
    """Hybrid baseline correction combining Valley and Local Minimum"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        self.time = time
        self.intensity = intensity
        self.baseline_points = []

    def find_baseline_anchor_points(
        self,
        valley_prominence: float = 0.01,
        local_window: int = None,
        percentile: float = None,  # Adaptive percentile (None = auto)
        min_distance: int = 10
    ) -> List[BaselinePoint]:
        """
        Find the optimal baseline anchor points by combining Valley and Local Minimum

        Parameters
        ----------
        valley_prominence : float
            Valley detection prominence factor
        local_window : int
            Window size for local minimum search
        percentile : float or None
            Percentile threshold for local minimum selection.
            If None, automatically determined based on signal characteristics.
        min_distance : int
            Minimum distance between anchor points
        """
        baseline_points = []

        # Adaptive percentile calculation based on signal characteristics
        if percentile is None:
            # Estimate noise level using MAD of signal derivative
            derivative = np.diff(self.intensity)
            noise_mad = np.median(np.abs(derivative - np.median(derivative)))
            signal_range = np.ptp(self.intensity)

            # Higher noise -> higher percentile (more conservative)
            # Lower noise -> lower percentile (more sensitive)
            if signal_range > 0:
                noise_ratio = noise_mad / signal_range
                if noise_ratio > 0.05:
                    # Noisy signal: use 10th percentile
                    percentile = 10
                elif noise_ratio > 0.02:
                    # Moderate noise: use 5th percentile
                    percentile = 5
                else:
                    # Low noise: use 2nd percentile
                    percentile = 2
            else:
                percentile = 5  # Default

        # 1. Find valley points
        valleys = self._find_valleys(valley_prominence)
        for v_idx in valleys:
            baseline_points.append(BaselinePoint(
                index=v_idx,
                value=self.intensity[v_idx],
                type='valley',
                confidence=1.0  # Valleys get high confidence
            ))

        # 2. Find local minimum points (within the segments between valleys)
        if local_window is None:
            local_window = max(20, len(self.intensity) // 50)

        # Find the local minimum in each segment between valleys
        valleys_extended = np.concatenate(([0], valleys, [len(self.intensity)-1]))

        for i in range(len(valleys_extended) - 1):
            start = valleys_extended[i]
            end = valleys_extended[i + 1]

            if end - start > local_window:
                # Split this segment into small windows and find local minima
                for win_start in range(start, end, local_window // 2):
                    win_end = min(win_start + local_window, end)
                    segment = self.intensity[win_start:win_end]

                    if len(segment) > 0:
                        # Points in the lower percentile within the segment
                        threshold = np.percentile(segment, percentile)
                        min_mask = segment <= threshold

                        if np.any(min_mask):
                            # Pick the lowest point
                            local_min_idx = win_start + np.argmin(segment)

                            # Skip if too close to a valley
                            if all(abs(local_min_idx - v) > min_distance for v in valleys):
                                # Confidence is computed from the surrounding gradient (flatter = higher)
                                if local_min_idx > 0 and local_min_idx < len(self.intensity) - 1:
                                    gradient = abs(self.intensity[local_min_idx + 1] -
                                                 self.intensity[local_min_idx - 1])
                                    confidence = 1.0 / (1.0 + gradient)
                                else:
                                    confidence = 0.5

                                baseline_points.append(BaselinePoint(
                                    index=local_min_idx,
                                    value=self.intensity[local_min_idx],
                                    type='local_min',
                                    confidence=confidence
                                ))

        # 3. Add the start and end points
        if 0 not in [p.index for p in baseline_points]:
            baseline_points.append(BaselinePoint(
                index=0,
                value=self.intensity[0],
                type='boundary',
                confidence=0.8
            ))

        if len(self.intensity) - 1 not in [p.index for p in baseline_points]:
            baseline_points.append(BaselinePoint(
                index=len(self.intensity) - 1,
                value=self.intensity[-1],
                type='boundary',
                confidence=0.8
            ))

        # Sort by index
        baseline_points.sort(key=lambda p: p.index)

        # Deduplicate (among nearby points, keep the one with higher confidence)
        filtered_points = []
        for point in baseline_points:
            too_close = False
            for existing in filtered_points:
                if abs(point.index - existing.index) < min_distance:
                    too_close = True
                    # Replace with the point that has higher confidence
                    if point.confidence > existing.confidence:
                        filtered_points.remove(existing)
                        filtered_points.append(point)
                    break

            if not too_close:
                filtered_points.append(point)

        filtered_points.sort(key=lambda p: p.index)

        # Outlier removal: filter out anchor points with abnormally low values
        # Prevents misdetecting a valley between large peaks as a trough
        if len(filtered_points) > 5:
            values = np.array([p.value for p in filtered_points])
            median_value = np.median(values)
            mad = np.median(np.abs(values - median_value))

            # MAD-based outlier detection (drop anything <= median - 3*MAD)
            # If MAD is small relative to the signal range, treat it as a stable baseline
            signal_range = np.ptp(self.intensity)  # Overall signal range
            relative_mad_threshold = signal_range * 0.02  # 2% of the signal range

            if mad < relative_mad_threshold:
                # Stable baseline: drop anything below the 10th percentile
                threshold = np.percentile(values, 10)
            else:
                # Variable baseline: drop anything below median - 3*MAD
                threshold = median_value - 3 * mad

            filtered_points = [p for p in filtered_points if p.value >= threshold]

        filtered_points.sort(key=lambda p: p.index)
        self.baseline_points = filtered_points
        return filtered_points

    def _find_valleys(self, prominence_factor: float = 0.01) -> np.ndarray:
        """Find valley points"""
        # Smoothing
        window = min(21, len(self.intensity) // 20)
        if window % 2 == 0:
            window += 1

        if len(self.intensity) > window:
            smoothed = signal.savgol_filter(self.intensity, window, 3)
        else:
            smoothed = self.intensity.copy()

        # Find inverted peaks (valleys)
        inverted = -smoothed
        valleys, _ = signal.find_peaks(
            inverted,
            prominence=np.ptp(smoothed) * prominence_factor,
            distance=window
        )

        return valleys

    def _baseline_anchor_mask(self, indices: np.ndarray, values: np.ndarray, k: int = 7) -> np.ndarray:
        """
        Boolean mask of anchors that lie on the baseline rather than on a peak flank.

        An anchor is rejected when it exceeds the median of its k nearest anchors by more than
        3 robust sigma (MAD of the residuals, floored at 0.5 % of the signal range so a noise-free
        baseline does not make the test hypersensitive). Neighbour medians follow a drifting or
        curved baseline, unlike one global median. The first and last anchors are kept, and the
        filter is skipped when fewer than 4 anchors would remain.
        """
        n = len(indices)
        keep = np.ones(n, dtype=bool)
        if n < 6:
            return keep
        floor = 0.005 * np.ptp(self.intensity)
        for _ in range(3):
            idx_k, val_k = indices[keep], values[keep]
            if len(idx_k) < 6:
                break
            kk = min(k, len(idx_k) - 1)
            resid = np.empty(len(idx_k))
            for j in range(len(idx_k)):
                order = np.argsort(np.abs(idx_k - idx_k[j]))[1:kk + 1]
                resid[j] = val_k[j] - np.median(val_k[order])
            scale = max(1.4826 * np.median(np.abs(resid - np.median(resid))), floor)
            bad = resid > 3.0 * scale
            bad[0] = bad[-1] = False
            if not bad.any():
                break
            keep_positions = np.flatnonzero(keep)
            keep[keep_positions[bad]] = False
        if keep.sum() < 4:
            return np.ones(n, dtype=bool)
        return keep

    def generate_hybrid_baseline(
        self,
        method: str = 'weighted_spline',
        smooth_factor: float = 0.5,
        enhanced_smoothing: bool = True
    ) -> np.ndarray:
        """
        Generate a baseline from the anchor points

        Methods:
        - weighted_spline: spline weighted by confidence
        - adaptive_connect: per-segment adaptive connection
        - robust_fit: fitting that is robust to outliers
        """
        if len(self.baseline_points) == 0:
            self.find_baseline_anchor_points()

        indices = np.array([p.index for p in self.baseline_points])
        values = np.array([p.value for p in self.baseline_points])
        confidences = np.array([p.confidence for p in self.baseline_points])
        types = [p.type for p in self.baseline_points]

        baseline = np.zeros_like(self.intensity)

        if method in ('weighted_spline', 'adaptive_connect'):
            # The anchor finder takes the lowest point of every window even when the whole window lies
            # on a peak flank; interpolating through such anchors lifts the baseline under the peak
            # (flat baseline + one peak: area recovered ~64 %). robust_fit already drops them.
            keep = self._baseline_anchor_mask(indices, values)
            indices, values = indices[keep], values[keep]
            confidences = confidences[keep]
            types = [t for t, k in zip(types, keep) if k]

        if method == 'weighted_spline':
            # Spline fit using confidence as the weight
            if len(indices) > 3:
                # Weight-based smoothing factor - tuned so it doesn't drift far from the anchor points
                weights = confidences
                if enhanced_smoothing:
                    # Increased smoothing: reduced from 5.0 -> 0.5
                    s = len(indices) * smooth_factor * 0.5 * (1 - np.mean(confidences) * 0.5)
                else:
                    s = len(indices) * smooth_factor * 0.1 * (1 - np.mean(confidences) * 0.5)

                try:
                    spl = UnivariateSpline(indices, values, w=weights, s=s, k=3)
                    baseline = spl(np.arange(len(self.intensity)))
                except Exception:
                    # Fallback to linear
                    f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
                    baseline = f(np.arange(len(self.intensity)))
            else:
                f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
                baseline = f(np.arange(len(self.intensity)))

        elif method == 'adaptive_connect':
            # Use a different connection method per segment
            for i in range(len(indices) - 1):
                start_idx = indices[i]
                end_idx = indices[i + 1]

                # Decide the connection method based on the type of both endpoints
                if types[i] == 'valley' and types[i + 1] == 'valley':
                    # Valley to valley: curved connection
                    x = [start_idx, (start_idx + end_idx) // 2, end_idx]
                    y = [values[i], (values[i] + values[i + 1]) / 2, values[i + 1]]

                    # Adjust the midpoint to the segment's minimum value
                    mid_segment = self.intensity[start_idx:end_idx + 1]
                    y[1] = min(y[1], np.percentile(mid_segment, 5))

                    if len(x) >= 3:
                        f = interp1d(x, y, kind='quadratic', fill_value='extrapolate')
                        baseline[start_idx:end_idx + 1] = f(np.arange(start_idx, end_idx + 1))
                else:
                    # Otherwise: linear connection
                    baseline[start_idx:end_idx + 1] = np.linspace(
                        values[i], values[i + 1], end_idx - start_idx + 1
                    )

        elif method == 'robust_fit':
            # RANSAC-style robust fitting
            # Remove outlier anchor points
            if len(values) > 5:
                # Compute MAD (Median Absolute Deviation)
                median = np.median(values)
                mad = np.median(np.abs(values - median))
                threshold = median + 3 * mad

                # Keep only the non-outlier points
                mask = values < threshold
                robust_indices = indices[mask]
                robust_values = values[mask]
                robust_weights = confidences[mask]

                if len(robust_indices) > 3:
                    # Increased smoothing - tuned so it doesn't drift too far from the anchor points
                    # Reduced from 5.0 -> 0.5: lowers the s/n ratio from 2.5 to 0.25
                    if enhanced_smoothing:
                        s = len(robust_indices) * smooth_factor * 0.5
                    else:
                        s = len(robust_indices) * smooth_factor * 0.1

                    spl = UnivariateSpline(
                        robust_indices,
                        robust_values,
                        w=robust_weights,
                        s=s,
                        k=min(3, len(robust_indices) - 1)
                    )
                    baseline = spl(np.arange(len(self.intensity)))
                else:
                    f = interp1d(robust_indices, robust_values, kind='linear', fill_value='extrapolate')
                    baseline = f(np.arange(len(self.intensity)))
            else:
                f = interp1d(indices, values, kind='linear', fill_value='extrapolate')
                baseline = f(np.arange(len(self.intensity)))

        # TEMPORARILY DISABLED: baseline safety constraint
        # Temporarily disabled for debugging
        # # 1. Use the first 1-3 minute window as the reference baseline (LC characteristic)
        # reference_start_time = 1.0  # min
        # reference_end_time = 3.0    # min
        #
        # # Convert the time range to indices
        # time_per_point = (self.time[-1] - self.time[0]) / len(self.time)
        # ref_start_idx = int(reference_start_time / time_per_point)
        # ref_end_idx = int(reference_end_time / time_per_point)
        #
        # if ref_start_idx < ref_end_idx < len(self.intensity):
        #     # Use the low values in the 1-3 minute window as the reference (10th percentile)
        #     reference_region = self.intensity[ref_start_idx:ref_end_idx]
        #     reference_baseline = np.percentile(reference_region, 10)
        #     reference_range = np.ptp(reference_region)  # Range of the 1-3 minute window itself
        #
        #     # Allow the baseline to deviate from the reference point by up to +/-3x the 1-3 min window's range
        #     # This keeps the baseline reasonable even where peaks are present
        #     allowed_deviation = max(reference_range * 3.0, 1000)  # Allow at least 1000
        #     lower_bound = reference_baseline - allowed_deviation
        #     upper_bound = reference_baseline + allowed_deviation * 2.0  # More headroom above
        #
        #     baseline = np.clip(baseline, lower_bound, upper_bound)

        # 2. Constrain the local window so it doesn't exceed the original signal range
        # DISABLED: removed because this constraint pushed the baseline too low
        # No extra constraint needed since the anchor points already represent the correct baseline
        # from scipy.ndimage import maximum_filter, minimum_filter
        # window_size = 201  # ~1 minute window
        # local_max = maximum_filter(self.intensity, size=window_size, mode='nearest')
        # local_min = minimum_filter(self.intensity, size=window_size, mode='nearest')
        # baseline = np.minimum(baseline, local_min * 1.0)

        # Keep only the negative-value guard
        baseline = np.maximum(baseline, -50.0)

        # TEMPORARILY DISABLED: smoothing disabled (for debugging)
        # # Smooth it out (enhanced smoothing) - excluding the last segment
        # if len(baseline) > 21 and len(self.baseline_points) >= 2:
        #     # Compute the index of the last segment
        #     last_pt = self.baseline_points[-1]
        #     second_last_pt = self.baseline_points[-2]
        #     last_segment_start = second_last_pt.index
        #
        #     # Smooth everything except the last segment
        #     if last_segment_start > 21:
        #         if enhanced_smoothing:
        #             # 1st pass: savgol_filter
        #             baseline[:last_segment_start] = signal.savgol_filter(baseline[:last_segment_start], 21, 3)
        #             # 2nd pass: moving average (additional)
        #             window = 15
        #             baseline[:last_segment_start] = np.convolve(
        #                 baseline[:last_segment_start],
        #                 np.ones(window)/window,
        #                 mode='same'
        #             )
        #         else:
        #             baseline[:last_segment_start] = signal.savgol_filter(baseline[:last_segment_start], 21, 3)

        # TEMPORARILY DISABLED: linear interpolation of the last segment disabled (for debugging)
        # # Replace the last segment with linear interpolation (avoids spline divergence)
        # if len(self.baseline_points) >= 2:
        #     last_pt = self.baseline_points[-1]
        #     second_last_pt = self.baseline_points[-2]
        #
        #     # Linearly interpolate between the last two anchor points
        #     start_idx = second_last_pt.index
        #     end_idx = last_pt.index
        #
        #     if end_idx > start_idx:
        #         x_range = np.arange(start_idx, end_idx + 1)
        #         linear_baseline = np.interp(
        #             x_range,
        #             [start_idx, end_idx],
        #             [second_last_pt.value, last_pt.value]
        #         )
        #         baseline[start_idx:end_idx + 1] = linear_baseline

        # DISABLED: these constraints were destroying the baseline
        # Trust the anchor points alone and drop the extra constraints
        # # Constrain the baseline to stay comfortably below the original signal
        # # Cap it at 50% of the local minimum to protect the peak base
        # from scipy.ndimage import minimum_filter
        # local_min_final = minimum_filter(self.intensity, size=51, mode='nearest')
        # baseline = np.minimum(baseline, local_min_final * 0.5)
        #
        # # Also cap it at 70% of the original signal (90% -> 70%)
        # baseline = np.minimum(baseline, self.intensity * 0.7)

        # Limit how far negative the baseline can go (relaxed criterion)
        # Allow negative values down to 10% of the signal range
        signal_range = np.ptp(self.intensity)
        min_baseline = -signal_range * 0.1
        baseline = np.maximum(baseline, min_baseline)

        # Constrain the baseline so it never exceeds the original signal
        baseline = np.minimum(baseline, self.intensity)

        # Bridge negative regions (applied selectively)
        # Only bridge extreme negative dips
        baseline = self.bridge_negative_regions(baseline, threshold_ratio=0.2)

        return baseline

    def post_process_corrected_signal(
        self,
        corrected: np.ndarray,
        clip_negative: bool = True,
        negative_threshold: float = -50.0
    ) -> np.ndarray:
        """
        Post-process the baseline-corrected signal

        Args:
            corrected: signal after baseline correction
            clip_negative: whether to clip negative values to 0
            negative_threshold: values more negative than this are treated as real negative peaks and preserved

        Returns:
            The post-processed signal
        """
        processed = corrected.copy()

        if clip_negative:
            # Analyze the negative regions
            negative_mask = processed < 0

            if np.any(negative_mask):
                # Find contiguous negative regions
                regions = []
                in_region = False
                start = 0

                for i, val in enumerate(negative_mask):
                    if val and not in_region:
                        start = i
                        in_region = True
                    elif not val and in_region:
                        regions.append((start, i-1))
                        in_region = False

                if in_region:
                    regions.append((start, len(negative_mask)-1))

                # Inspect each negative region
                for start, end in regions:
                    region_values = processed[start:end+1]
                    min_val = np.min(region_values)
                    region_size = end - start + 1

                    # Only clip small, shallow negative regions
                    # Condition: the minimum is above the threshold (shallow) and the region is small
                    if min_val > negative_threshold and region_size < 100:
                        # Clip to 0
                        processed[start:end+1] = np.maximum(processed[start:end+1], 0)
                    # Large, deep negative regions are preserved as real negative peaks

        return processed

    def optimize_baseline(self) -> Tuple[np.ndarray, Dict]:
        """
        Try several parameter combinations to find the optimal baseline
        """
        best_score = -np.inf
        best_baseline = None
        best_params = {}

        # Parameter combinations
        param_combinations = [
            {'valley_prominence': 0.005, 'percentile': 5, 'method': 'weighted_spline'},
            {'valley_prominence': 0.01, 'percentile': 10, 'method': 'weighted_spline'},
            {'valley_prominence': 0.02, 'percentile': 15, 'method': 'adaptive_connect'},
            {'valley_prominence': 0.01, 'percentile': 10, 'method': 'robust_fit'},
        ]

        for params in param_combinations:
            # Find the anchor points
            self.find_baseline_anchor_points(
                valley_prominence=params['valley_prominence'],
                percentile=params['percentile']
            )

            # Generate the baseline
            baseline = self.generate_hybrid_baseline(method=params['method'])
            corrected = self.intensity - baseline

            # Compute the evaluation score
            score = self._evaluate_baseline(baseline, corrected)

            if score > best_score:
                best_score = score
                best_baseline = baseline
                best_params = params

        return best_baseline, best_params

    def _evaluate_baseline(self, baseline: np.ndarray, corrected: np.ndarray) -> float:
        """Evaluate baseline quality"""
        # 1. Fraction of negative values (lower is better)
        neg_ratio = np.sum(corrected < 0) / len(corrected)

        # 2. Baseline smoothness
        smoothness = np.std(np.diff(baseline, 2))

        # 3. Peak preservation
        original_peaks = signal.find_peaks(self.intensity, prominence=np.ptp(self.intensity)*0.05)[0]
        if len(original_peaks) > 0:
            corrected_peaks = signal.find_peaks(corrected, prominence=np.ptp(corrected)*0.05)[0]
            peak_preservation = min(1.0, len(corrected_peaks) / len(original_peaks))
        else:
            peak_preservation = 1.0

        # Combined score
        score = (1 - neg_ratio) * 100 + peak_preservation * 50 - smoothness
        return score

    def apply_linear_baseline_to_peaks(self, baseline: np.ndarray, detected_peaks: List[int]) -> np.ndarray:
        """
        Apply a linear baseline across the detected peak regions
        Find the actual baseline points on either side of the peak and connect them with a straight line

        Args:
            baseline: the original baseline
            detected_peaks: indices of the detected peaks

        Returns:
            The baseline with a linear segment applied under the peak regions
        """
        linear_baseline = baseline.copy()

        for peak_idx in detected_peaks:
            # Compute peak height
            peak_height = self.intensity[peak_idx] - baseline[peak_idx]
            if peak_height <= 0:
                continue

            # Find the peak base point (1% height)
            base_threshold = baseline[peak_idx] + peak_height * 0.01

            # Find the left base point - where the signal drops back near the baseline
            left_idx = peak_idx
            while left_idx > 0:
                # Stop once the signal drops to baseline + 1% height or below
                if self.intensity[left_idx] <= base_threshold:
                    break
                # Or stop once the signal is nearly equal to the baseline
                if self.intensity[left_idx] <= baseline[left_idx] * 1.02:
                    break
                left_idx -= 1

            # Find the right base point
            right_idx = peak_idx
            while right_idx < len(self.intensity) - 1:
                if self.intensity[right_idx] <= base_threshold:
                    break
                if self.intensity[right_idx] <= baseline[right_idx] * 1.02:
                    break
                right_idx += 1

            # Only process valid peak regions
            if right_idx > left_idx + 5:
                # Use the actual baseline value (the low point of the original signal, not the interpolated baseline)
                # Find the lowest point on each side of the peak
                search_range = 20  # Search within 20 points of the boundary

                # Actual baseline value on the left
                left_search_start = max(0, left_idx - search_range)
                left_search_end = left_idx + 5
                left_region = self.intensity[left_search_start:left_search_end]
                if len(left_region) > 0:
                    left_base_value = np.min(left_region)
                    left_base_idx = left_search_start + np.argmin(left_region)
                else:
                    left_base_value = baseline[left_idx]
                    left_base_idx = left_idx

                # Actual baseline value on the right
                right_search_start = right_idx - 5
                right_search_end = min(len(self.intensity), right_idx + search_range)
                right_region = self.intensity[right_search_start:right_search_end]
                if len(right_region) > 0:
                    right_base_value = np.min(right_region)
                    right_base_idx = right_search_start + np.argmin(right_region)
                else:
                    right_base_value = baseline[right_idx]
                    right_base_idx = right_idx

                # Generate the under-peak baseline via linear interpolation
                if right_base_idx > left_base_idx:
                    x_range = np.arange(left_base_idx, right_base_idx + 1)
                    linear_segment = np.interp(
                        x_range,
                        [left_base_idx, right_base_idx],
                        [left_base_value, right_base_value]
                    )
                    linear_baseline[left_base_idx:right_base_idx + 1] = linear_segment

        return linear_baseline

    def bridge_negative_regions(self, baseline: np.ndarray, threshold_ratio: float = 0.2) -> np.ndarray:
        """
        Bridge only extremely low negative regions (relaxed criterion)

        Ordinary negative peaks are allowed through; only very sharp dips are treated
        """
        bridged_baseline = baseline.copy()

        # 1. Compute signal statistics
        signal_range = np.ptp(self.intensity)
        signal_median = np.median(self.intensity)

        # 2. Detect only extreme negative dips (a drop of at least threshold_ratio of the signal range)
        # e.g. threshold_ratio=0.2 only treats regions that drop at least 20% of the signal range
        extreme_threshold = signal_median - signal_range * threshold_ratio
        extreme_negative_mask = self.intensity < extreme_threshold

        if not np.any(extreme_negative_mask):
            return bridged_baseline

        # 3. Bridge only the extreme negative points
        extreme_indices = np.where(extreme_negative_mask)[0]

        for idx in extreme_indices:
            # Replace with the nearby normal signal value
            left_val = signal_median
            right_val = signal_median

            # Look left for a normal signal value
            for i in range(idx - 1, max(0, idx - 50) - 1, -1):
                if self.intensity[i] >= extreme_threshold:
                    left_val = baseline[i]
                    break

            # Look right for a normal signal value
            for i in range(idx + 1, min(len(self.intensity), idx + 50)):
                if self.intensity[i] >= extreme_threshold:
                    right_val = baseline[i]
                    break

            # Bridge with the average value
            bridge_val = (left_val + right_val) / 2
            bridged_baseline[idx] = bridge_val

        # 4. Smooth (only the bridged region)
        from scipy.ndimage import uniform_filter1d
        smoothed = uniform_filter1d(bridged_baseline, size=5)
        bridged_baseline[extreme_negative_mask] = smoothed[extreme_negative_mask]

        return bridged_baseline

    def compare_baselines_by_peak_width(
        self,
        baseline_robust: np.ndarray,
        baseline_weighted: np.ndarray
    ) -> Tuple[np.ndarray, Dict]:
        """
        Compare robust_fit and weighted_spline per peak and choose whichever gives the wider peak width

        Args:
            baseline_robust: the baseline generated with the robust_fit method
            baseline_weighted: the baseline generated with the weighted_spline method

        Returns:
            The chosen baseline plus the selection info
        """
        # Signal corrected by each baseline
        corrected_robust = np.maximum(self.intensity - baseline_robust, 0)
        corrected_weighted = np.maximum(self.intensity - baseline_weighted, 0)

        # Peak detection
        noise_level_robust = np.percentile(corrected_robust, 25) * 1.5
        noise_level_weighted = np.percentile(corrected_weighted, 25) * 1.5

        peaks_robust, props_robust = signal.find_peaks(
            corrected_robust,
            prominence=np.ptp(corrected_robust) * 0.005,
            height=noise_level_robust * 3,
            width=0
        )

        peaks_weighted, props_weighted = signal.find_peaks(
            corrected_weighted,
            prominence=np.ptp(corrected_weighted) * 0.005,
            height=noise_level_weighted * 3,
            width=0
        )

        # Compare per peak
        hybrid_baseline = baseline_weighted.copy()  # weighted is the default
        selection_info = {
            'robust_peaks': len(peaks_robust),
            'weighted_peaks': len(peaks_weighted),
            'robust_selected_count': 0,
            'weighted_selected_count': 0,
            'selections': []
        }

        # Collect all peak positions (union of robust + weighted)
        all_peak_positions = set(peaks_robust.tolist() + peaks_weighted.tolist())

        for peak_pos in all_peak_positions:
            # Width of this peak under robust
            width_robust = 0
            if peak_pos in peaks_robust:
                idx_robust = np.where(peaks_robust == peak_pos)[0][0]
                width_robust = props_robust['widths'][idx_robust] if 'widths' in props_robust else 0

            # Width of this peak under weighted
            width_weighted = 0
            if peak_pos in peaks_weighted:
                idx_weighted = np.where(peaks_weighted == peak_pos)[0][0]
                width_weighted = props_weighted['widths'][idx_weighted] if 'widths' in props_weighted else 0

            # Choose whichever method gives the wider width
            if width_robust > width_weighted:
                # robust is wider - use the robust baseline in the peak region
                peak_height = self.intensity[peak_pos] - baseline_robust[peak_pos]
                half_height = baseline_robust[peak_pos] + peak_height / 2

                left_idx = peak_pos
                while left_idx > 0 and self.intensity[left_idx] > half_height:
                    left_idx -= 1

                right_idx = peak_pos
                while right_idx < len(self.intensity) - 1 and self.intensity[right_idx] > half_height:
                    right_idx += 1

                hybrid_baseline[left_idx:right_idx+1] = baseline_robust[left_idx:right_idx+1]
                selection_info['robust_selected_count'] += 1
                selection_info['selections'].append({
                    'rt': self.time[peak_pos],
                    'method': 'robust',
                    'width_robust': width_robust,
                    'width_weighted': width_weighted
                })
            else:
                selection_info['weighted_selected_count'] += 1
                selection_info['selections'].append({
                    'rt': self.time[peak_pos],
                    'method': 'weighted',
                    'width_robust': width_robust,
                    'width_weighted': width_weighted
                })

        return hybrid_baseline, selection_info

    def optimize_baseline_with_linear_peaks(self) -> Tuple[np.ndarray, Dict]:
        """
        Apply a flat baseline under the peak regions, choosing robust vs weighted by peak width

        Returns:
            The optimal baseline plus parameter info
        """
        # Find the anchor points
        self.find_baseline_anchor_points(
            valley_prominence=0.01,
            percentile=10
        )

        # Generate the baseline with robust_fit
        baseline_robust = self.generate_hybrid_baseline(method='robust_fit')

        # Peak detection
        corrected = np.maximum(self.intensity - baseline_robust, 0)
        noise_level = np.percentile(corrected, 25) * 1.5
        peaks, _ = signal.find_peaks(
            corrected,
            prominence=np.ptp(corrected) * 0.005,
            height=noise_level * 3,
            width=0
        )

        # Apply a flat baseline under the peak regions
        if len(peaks) > 0:
            hybrid_baseline = self.apply_linear_baseline_to_peaks(baseline_robust, peaks)
        else:
            hybrid_baseline = baseline_robust

        params = {
            'method': 'robust_fit_with_flat_peaks',
            'num_peaks': len(peaks),
            'peaks_rt': [self.time[p] for p in peaks] if len(peaks) > 0 else []
        }

        return hybrid_baseline, params


def test_hybrid_baseline():
    """Test the hybrid baseline method"""

    # Load the data
    print("Loading datasets...")

    # EXPORT.CSV
    df1 = pd.read_csv('peakpicker/examples/EXPORT.CSV',
                      header=None, sep='\t', encoding='utf-16-le')
    time1 = df1[0].values
    intensity1 = df1[1].values
    # Preserve negative values: don't auto-shift, so negative peaks stay detectable
    # if np.min(intensity1) < 0:
    #     intensity1 = intensity1 - np.min(intensity1)

    # sample_chromatogram.csv
    df2 = pd.read_csv('peakpicker/examples/sample_chromatogram.csv')
    time2 = df2['Time'].values
    intensity2 = df2['Intensity'].values

    # Visualization
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    for idx, (time, intensity, name) in enumerate([
        (time1, intensity1, 'EXPORT.CSV'),
        (time2, intensity2, 'sample_chromatogram')
    ]):
        print(f"\n{name}:")
        corrector = HybridBaselineCorrector(time, intensity)

        # 1. Find the anchor points
        anchor_points = corrector.find_baseline_anchor_points()
        print(f"  Total anchor points: {len(anchor_points)}")
        print(f"    - Valleys: {sum(1 for p in anchor_points if p.type == 'valley')}")
        print(f"    - Local minima: {sum(1 for p in anchor_points if p.type == 'local_min')}")
        print(f"    - Boundaries: {sum(1 for p in anchor_points if p.type == 'boundary')}")

        # Visualize the anchor points
        axes[idx, 0].plot(time, intensity, 'b-', alpha=0.6, label='Original')

        # Different color/size per type
        for point in anchor_points:
            if point.type == 'valley':
                color, size, marker = 'red', 50, 'v'
            elif point.type == 'local_min':
                color, size, marker = 'green', 30, 'o'
            else:  # boundary
                color, size, marker = 'orange', 40, 's'

            axes[idx, 0].scatter(
                time[point.index],
                point.value,
                c=color,
                s=size * point.confidence,  # scale the size by confidence
                marker=marker,
                alpha=0.8,
                edgecolors='black',
                linewidths=0.5
            )

        axes[idx, 0].set_title(f'{name}\nAnchor Points')
        axes[idx, 0].set_xlabel('Time (min)')
        axes[idx, 0].set_ylabel('Intensity')
        axes[idx, 0].grid(True, alpha=0.3)

        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='red', label='Valley'),
            Patch(facecolor='green', label='Local Min'),
            Patch(facecolor='orange', label='Boundary')
        ]
        axes[idx, 0].legend(handles=legend_elements, loc='upper right', fontsize=8)

        # 2. Generate baselines with all three methods
        methods = ['weighted_spline', 'adaptive_connect', 'robust_fit']
        colors = ['red', 'green', 'blue']

        for method, color in zip(methods, colors):
            baseline = corrector.generate_hybrid_baseline(method=method)
            axes[idx, 1].plot(time, baseline, '--', color=color, alpha=0.7, label=method)

        axes[idx, 1].plot(time, intensity, 'k-', alpha=0.3, label='Original')
        axes[idx, 1].set_title('Baseline Methods Comparison')
        axes[idx, 1].set_xlabel('Time (min)')
        axes[idx, 1].set_ylabel('Intensity')
        axes[idx, 1].legend(fontsize=8)
        axes[idx, 1].grid(True, alpha=0.3)

        # 3. Optimized baseline
        best_baseline, best_params = corrector.optimize_baseline()
        corrected = intensity - best_baseline

        axes[idx, 2].plot(time, intensity, 'b-', alpha=0.3, label='Original')
        axes[idx, 2].plot(time, best_baseline, 'r--', alpha=0.8, label='Optimized Baseline')
        axes[idx, 2].fill_between(time, 0, corrected, alpha=0.5, color='green', label='Corrected')

        # Peak detection
        peaks, _ = signal.find_peaks(
            corrected,
            prominence=np.ptp(corrected) * 0.05,
            height=np.std(corrected) * 2
        )

        if len(peaks) > 0:
            axes[idx, 2].scatter(time[peaks], corrected[peaks],
                              color='red', s=50, zorder=5, marker='^', label=f'{len(peaks)} peaks')

            # Show RT
            for peak in peaks[:5]:  # first 5 only
                axes[idx, 2].annotate(
                    f'{time[peak]:.1f}',
                    xy=(time[peak], corrected[peak]),
                    xytext=(time[peak], corrected[peak] + np.max(corrected)*0.05),
                    fontsize=7,
                    ha='center'
                )

        # Adjust y-axis to show full peaks
        y_max = max(np.max(intensity), np.max(corrected)) * 1.15
        y_min = min(0, np.min(corrected)) - y_max * 0.05
        axes[idx, 2].set_ylim(y_min, y_max)

        axes[idx, 2].set_title(f'Optimized Result\n{best_params}')
        axes[idx, 2].set_xlabel('Time (min)')
        axes[idx, 2].set_ylabel('Intensity')
        axes[idx, 2].legend(fontsize=8)
        axes[idx, 2].grid(True, alpha=0.3)

        print(f"  Best method: {best_params.get('method', 'N/A')}")
        print(f"  Detected peaks: {len(peaks)}")
        if len(peaks) > 0:
            print(f"  Peak RTs: {[f'{time[p]:.2f}' for p in peaks[:5]]}")

    plt.suptitle('Hybrid Baseline Correction (Valley + Local Minimum)', fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig('hybrid_baseline_results.png', dpi=100, bbox_inches='tight')
    plt.show()

    print("\n" + "="*60)
    print("HYBRID BASELINE ANALYSIS COMPLETE")
    print("="*60)
    print("\nKey Features:")
    print("  - Combines valley detection and local minimum search")
    print("  - Confidence-weighted anchor points")
    print("  - Multiple connection methods (spline, adaptive, robust)")
    print("  - Automatic parameter optimization")
    print("\nResult saved: hybrid_baseline_results.png")


if __name__ == "__main__":
    test_hybrid_baseline()
