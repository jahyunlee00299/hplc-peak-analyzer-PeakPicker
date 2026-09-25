"""Numeric compatibility shims.

numpy>=2.0 removed ``np.trapz``; numpy<2.0 (e.g. 1.26.x) lacks ``np.trapezoid``.
Measured 260828 across this project's interpreters:

    interpreter                                    numpy    trapezoid   trapz
    /usr/bin/python3                                1.26.4   missing     OK
    ~/miniconda3/bin/python                         2.4.3    OK          removed
    ~/miniconda3/envs/KineticModeling/bin/python    2.4.2    OK          removed

Neither name works everywhere, so resolve once at import time and export a
single name the rest of the codebase can call unconditionally.
"""
import numpy as np

trapezoid = getattr(np, "trapezoid", None) or np.trapz

__all__ = ["trapezoid"]
