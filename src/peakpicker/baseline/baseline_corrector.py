"""
Baseline Corrector
==================

High-level baseline correction orchestrator.
Composes all baseline components following SOLID principles.
"""

from typing import List, Dict, Any
import numpy as np

from ..interfaces import (
    IBaselineCorrector,
    IAnchorFinder,
    IBaselineStrategy,
    IBaselineEvaluator,
)
from ..domain import BaselineResult, AnchorPoint, BaselineMethod
from ..config import BaselineCorrectorConfig

from .generators import BaselineGenerator, PostProcessor


class BaselineCorrector(IBaselineCorrector):
    """
    Complete baseline correction using dependency injection.

    Composes anchor finder, generator, and evaluator.
    Follows Open/Closed - can use any implementations of interfaces.
    """

    def __init__(
        self,
        anchor_finder: IAnchorFinder,
        strategy: IBaselineStrategy,
        evaluator: IBaselineEvaluator = None,
        config: BaselineCorrectorConfig = None
    ):
        """
        Initialize baseline corrector.

        Parameters
        ----------
        anchor_finder : IAnchorFinder
            Anchor point finder implementation
        strategy : IBaselineStrategy
            Baseline generation strategy
        evaluator : IBaselineEvaluator, optional
            Quality evaluator
        config : BaselineCorrectorConfig, optional
            Configuration parameters
        """
        self.anchor_finder = anchor_finder
        self.strategy = strategy
        self.evaluator = evaluator
        self.config = config or BaselineCorrectorConfig()

        # Create generator and post-processor
        self.generator = BaselineGenerator(strategy, self.config.generator_config)
        self.post_processor = PostProcessor(self.config.generator_config)

    def correct(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> BaselineResult:
        """
        Perform complete baseline correction.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        BaselineResult
            Complete baseline correction result
        """
        # 1. Find anchor points
        anchors = self.anchor_finder.find_anchors(time, signal)

        # 2. Generate baseline
        baseline = self.generator.generate(time, signal, anchors)

        # 3. Correct signal
        corrected = signal - baseline

        # 4. Post-process
        if self.config.clip_negative_signal:
            corrected = self.post_processor.process(corrected, signal, baseline)

        # 5. Evaluate quality
        if self.evaluator is not None:
            metrics = self.evaluator.evaluate(signal, baseline, corrected)
            quality_score = metrics.get('overall_score', 0) / 100.0
            negative_ratio = metrics.get('negative_ratio', 0)
            smoothness = metrics.get('smoothness', 0)
        else:
            quality_score = self._quick_quality_estimate(corrected)
            negative_ratio = np.sum(corrected < 0) / len(corrected)
            smoothness = np.std(np.diff(baseline, n=2)) if len(baseline) > 2 else 0

        return BaselineResult(
            baseline=baseline,
            anchors=anchors,
            method=self.strategy.method,
            quality_score=quality_score,
            negative_ratio=negative_ratio,
            smoothness=smoothness,
            params={
                'anchor_count': len(anchors),
                'corrected_signal': corrected,
            }
        )

    def _quick_quality_estimate(self, corrected: np.ndarray) -> float:
        """Quick quality estimate when evaluator not available."""
        neg_ratio = np.sum(corrected < 0) / len(corrected)
        return max(0, 1 - neg_ratio * 2)


class OptimizingBaselineCorrector(IBaselineCorrector):
    """
    Baseline corrector that tries multiple strategies and picks the best.

    Open/Closed: Strategies can be added without modifying this class.
    """

    def __init__(
        self,
        anchor_finder: IAnchorFinder,
        strategies: List[IBaselineStrategy],
        evaluator: IBaselineEvaluator,
        config: BaselineCorrectorConfig = None
    ):
        """
        Initialize optimizing corrector.

        Parameters
        ----------
        anchor_finder : IAnchorFinder
            Anchor point finder
        strategies : List[IBaselineStrategy]
            List of strategies to try
        evaluator : IBaselineEvaluator
            Quality evaluator for comparison
        config : BaselineCorrectorConfig, optional
            Configuration
        """
        self.anchor_finder = anchor_finder
        self.strategies = strategies
        self.evaluator = evaluator
        self.config = config or BaselineCorrectorConfig()

    def correct(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> BaselineResult:
        """
        Try multiple strategies and return best result.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        BaselineResult
            Best baseline correction result
        """
        # Find anchor points once
        anchors = self.anchor_finder.find_anchors(time, signal)

        best_result = None
        best_score = -np.inf

        for strategy in self.strategies:
            # Create corrector with this strategy
            corrector = BaselineCorrector(
                anchor_finder=self.anchor_finder,
                strategy=strategy,
                evaluator=self.evaluator,
                config=self.config
            )

            # Generate baseline (reuse anchors)
            generator = BaselineGenerator(strategy, self.config.generator_config)
            baseline = generator.generate(time, signal, anchors)

            # Correct and evaluate
            corrected = signal - baseline
            metrics = self.evaluator.evaluate(signal, baseline, corrected)
            score = metrics.get('overall_score', 0)

            if score > best_score:
                best_score = score
                best_result = BaselineResult(
                    baseline=baseline,
                    anchors=anchors,
                    method=strategy.method,
                    quality_score=score / 100.0,
                    negative_ratio=metrics.get('negative_ratio', 0),
                    smoothness=metrics.get('smoothness', 0),
                    params={
                        'anchor_count': len(anchors),
                        'corrected_signal': corrected,
                        'optimization_score': score,
                    }
                )

        return best_result
