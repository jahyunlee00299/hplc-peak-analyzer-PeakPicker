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
    PeakBoundaryAnchorFinder,
)

from .strategies import (
    WeightedSplineStrategy,
    RobustFitStrategy,
    AdaptiveConnectStrategy,
    LinearStrategy,
    ArplsStrategy,
    AirplsStrategy,
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
    'PeakBoundaryAnchorFinder',
    # Strategies
    'WeightedSplineStrategy',
    'RobustFitStrategy',
    'AdaptiveConnectStrategy',
    'LinearStrategy',
    'ArplsStrategy',
    'AirplsStrategy',
    # Generators
    'BaselineGenerator',
    'PostProcessor',
    # Evaluators
    'BaselineQualityEvaluator',
]
