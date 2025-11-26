"""
Baseline Quality Evaluator
==========================

Evaluates quality of baseline correction.
Single Responsibility: Only evaluates baseline quality.
"""

from typing import Dict
import numpy as np

from ...interfaces import IBaselineEvaluator, ISignalProcessor


class BaselineQualityEvaluator(IBaselineEvaluator):
    """
    Evaluates baseline correction quality using multiple metrics.
    """

    def __init__(self, signal_processor: ISignalProcessor = None):
        """
        Initialize evaluator.

        Parameters
        ----------
        signal_processor : ISignalProcessor, optional
            Signal processor for peak detection
        """
        self.signal_processor = signal_processor

    def evaluate(
        self,
        signal: np.ndarray,
        baseline: np.ndarray,
        corrected: np.ndarray
    ) -> Dict[str, float]:
        """
        Evaluate baseline correction quality.

        Parameters
        ----------
        signal : np.ndarray
            Original signal
        baseline : np.ndarray
            Applied baseline
        corrected : np.ndarray
            Corrected signal (signal - baseline)

        Returns
        -------
        Dict[str, float]
            Quality metrics
        """
        metrics = {}

        # 1. Negative ratio - fraction of negative values (lower is better)
        negative_count = np.sum(corrected < 0)
        metrics['negative_ratio'] = negative_count / len(corrected)

        # 2. Smoothness - baseline smoothness (lower is better)
        if len(baseline) > 2:
            second_diff = np.diff(baseline, n=2)
            metrics['smoothness'] = np.std(second_diff)
        else:
            metrics['smoothness'] = 0.0

        # 3. Peak preservation - how well peaks are preserved
        metrics['peak_preservation'] = self._calculate_peak_preservation(
            signal, corrected
        )

        # 4. Baseline fit quality
        metrics['fit_quality'] = self._calculate_fit_quality(signal, baseline)

        # 5. Overall score (weighted combination)
        metrics['overall_score'] = self._calculate_overall_score(metrics)

        return metrics

    def _calculate_peak_preservation(
        self,
        original: np.ndarray,
        corrected: np.ndarray
    ) -> float:
        """Calculate how well peaks are preserved after correction."""
        if self.signal_processor is None:
            return 1.0

        # Find peaks in original
        orig_prominence = np.ptp(original) * 0.05
        orig_peaks, _ = self.signal_processor.find_peaks(
            original, prominence=orig_prominence
        )

        if len(orig_peaks) == 0:
            return 1.0

        # Find peaks in corrected
        corr_prominence = np.ptp(corrected) * 0.05
        corr_peaks, _ = self.signal_processor.find_peaks(
            corrected, prominence=corr_prominence
        )

        # Ratio of preserved peaks
        preservation = min(1.0, len(corr_peaks) / len(orig_peaks))
        return preservation

    def _calculate_fit_quality(
        self,
        signal: np.ndarray,
        baseline: np.ndarray
    ) -> float:
        """Calculate how well baseline fits the signal background."""
        # Baseline should be below signal most of the time
        below_signal = baseline <= signal
        fit_ratio = np.sum(below_signal) / len(signal)

        # Also check that baseline doesn't deviate too much
        deviations = np.abs(signal - baseline)
        signal_range = np.ptp(signal)

        if signal_range > 0:
            normalized_deviation = np.mean(deviations) / signal_range
            deviation_score = max(0, 1 - normalized_deviation)
        else:
            deviation_score = 1.0

        return (fit_ratio + deviation_score) / 2

    def _calculate_overall_score(self, metrics: Dict[str, float]) -> float:
        """Calculate weighted overall score."""
        # Weights for each metric
        weights = {
            'negative_ratio': -100,  # Negative because lower is better
            'smoothness': -0.001,    # Negative because lower is better
            'peak_preservation': 50,  # Positive because higher is better
            'fit_quality': 50         # Positive because higher is better
        }

        score = 0
        for key, weight in weights.items():
            if key in metrics:
                score += weight * metrics[key]

        # Normalize to 0-100 range approximately
        return max(0, min(100, score + 100))
