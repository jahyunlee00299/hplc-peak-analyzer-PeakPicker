"""
Signal Processing Infrastructure
================================

Concrete implementations of signal processing interfaces.
"""

from .scipy_adapter import (
    ScipySignalProcessor,
    ScipyInterpolator,
    ScipyCurveFitter,
    ScipyIntegrator,
    create_scipy_processors,
)

__all__ = [
    'ScipySignalProcessor',
    'ScipyInterpolator',
    'ScipyCurveFitter',
    'ScipyIntegrator',
    'create_scipy_processors',
]
