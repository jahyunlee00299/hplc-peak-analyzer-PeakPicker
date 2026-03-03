"""
Baseline Generation Strategies
==============================

Strategy pattern implementations for baseline generation.
"""

from .weighted_spline import (
    WeightedSplineStrategy,
    RobustFitStrategy,
    AdaptiveConnectStrategy,
    LinearStrategy,
)
from .arpls_strategy import ArplsStrategy, AirplsStrategy

__all__ = [
    'WeightedSplineStrategy',
    'RobustFitStrategy',
    'AdaptiveConnectStrategy',
    'LinearStrategy',
    'ArplsStrategy',
    'AirplsStrategy',
]
