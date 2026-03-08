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

__all__ = [
    'WeightedSplineStrategy',
    'RobustFitStrategy',
    'AdaptiveConnectStrategy',
    'LinearStrategy',
]
