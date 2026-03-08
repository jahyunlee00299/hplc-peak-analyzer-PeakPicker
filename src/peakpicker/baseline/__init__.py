"""
Baseline Correction Module
==========================

SOLID-compliant baseline correction for HPLC chromatography.

This module provides:
- Multiple anchor finding strategies
- Pluggable baseline generation strategies
- Quality evaluation
- Optimization across strategies
"""

from .baseline_corrector import BaselineCorrector, OptimizingBaselineCorrector

from .anchor_finders import (
    ValleyAnchorFinder,
    LocalMinAnchorFinder,
    BoundaryAnchorFinder,
    CompositeAnchorFinder,
)

from .strategies import (
    WeightedSplineStrategy,
    RobustFitStrategy,
    AdaptiveConnectStrategy,
    LinearStrategy,
)

from .generators import BaselineGenerator, PostProcessor

from .evaluators import BaselineQualityEvaluator

__all__ = [
    # Main correctors
    'BaselineCorrector',
    'OptimizingBaselineCorrector',
    # Anchor finders
    'ValleyAnchorFinder',
    'LocalMinAnchorFinder',
    'BoundaryAnchorFinder',
    'CompositeAnchorFinder',
    # Strategies
    'WeightedSplineStrategy',
    'RobustFitStrategy',
    'AdaptiveConnectStrategy',
    'LinearStrategy',
    # Generators
    'BaselineGenerator',
    'PostProcessor',
    # Evaluators
    'BaselineQualityEvaluator',
]
