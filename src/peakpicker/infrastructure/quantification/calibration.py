"""
Linear Calibration Calculator
==============================

Concrete implementation of ICalibrationCalculator that converts a
measured peak area into analyte concentration using a linear calibration
model:

    Area = y0 + a * C

Rearranging:

    C_diluted  = (Area - y0) / a
    C_original = C_diluted * dilution_factor

where
    y0 = calibration_intercept   (CompoundDefinition.calibration_intercept)
    a  = calibration_slope       (CompoundDefinition.calibration_slope)
"""

import logging
from typing import Tuple

from ...interfaces import ICalibrationCalculator
from ...domain import CompoundDefinition

logger = logging.getLogger(__name__)


class LinearCalibrationCalculator(ICalibrationCalculator):
    """
    Calculates analyte concentration from peak area using a linear
    calibration curve.

    The calibration parameters (intercept ``y0`` and slope ``a``) are
    stored on each CompoundDefinition so that different compounds can
    have independent calibrations.

    No additional configuration is required; all parameters come from
    the CompoundDefinition and the per-sample dilution factor.
    """

    # ------------------------------------------------------------------
    # ICalibrationCalculator interface
    # ------------------------------------------------------------------

    def calculate_concentration(
        self,
        area: float,
        compound: CompoundDefinition,
        dilution_factor: float,
    ) -> Tuple[float, float]:
        """
        Convert a peak area to concentration using linear calibration.

        Parameters
        ----------
        area : float
            Integrated peak area (same units as the calibration curve,
            e.g. nRIU*min).
        compound : CompoundDefinition
            Compound with calibration_intercept (y0) and
            calibration_slope (a).
        dilution_factor : float
            Dilution factor applied to recover the original sample
            concentration.  Use 1.0 if the sample was not diluted.

        Returns
        -------
        Tuple[float, float]
            ``(concentration_diluted, concentration_original)``
            in the units defined by ``compound.unit``.

        Raises
        ------
        ValueError
            If the calibration slope is zero (division by zero).
        """
        y0 = compound.calibration_intercept
        a = compound.calibration_slope

        if a == 0.0:
            raise ValueError(
                f"Calibration slope for compound '{compound.name}' is zero; "
                f"cannot compute concentration."
            )

        concentration_diluted = (area - y0) / a
        concentration_original = concentration_diluted * dilution_factor

        logger.debug(
            "Compound '%s': area=%.4f, y0=%.4f, a=%.4f, DF=%.4f -> "
            "C_dil=%.6f, C_orig=%.6f %s",
            compound.name, area, y0, a, dilution_factor,
            concentration_diluted, concentration_original, compound.unit,
        )

        return concentration_diluted, concentration_original
