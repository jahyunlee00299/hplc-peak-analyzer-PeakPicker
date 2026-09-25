"""
RT Window Peak Matcher
=======================

Concrete implementation of IPeakMatcher that assigns detected peaks to
known compounds based on retention-time windows.

Matching strategy:
1. For each compound, find all peaks whose RT falls within
   [rt_window_start - tolerance, rt_window_end + tolerance].
2. If ``require_single_match`` is True and multiple peaks match,
   the behaviour depends on ``prefer_largest_area``:
   - True  -> select the peak with the largest integrated area.
   - False -> raise an ambiguity error.
3. If no peak falls in the window the compound maps to ``None``.
"""

import logging
from typing import Dict, List, Optional

from ...interfaces import IPeakMatcher
from ...domain import Peak, CompoundDefinition
from ...config.quantification_config import RTMatchingConfig

logger = logging.getLogger(__name__)


class RTWindowPeakMatcher(IPeakMatcher):
    """
    Matches detected peaks to CompoundDefinitions using RT windows.

    Parameters
    ----------
    config : RTMatchingConfig, optional
        Matching configuration.  Defaults give zero extra tolerance,
        require a single match, and prefer the largest-area peak when
        there are multiple candidates.
    """

    def __init__(self, config: RTMatchingConfig | None = None):
        self._config = config or RTMatchingConfig()

    # ------------------------------------------------------------------
    # IPeakMatcher interface
    # ------------------------------------------------------------------

    def match(
        self,
        peaks: List[Peak],
        compounds: List[CompoundDefinition],
    ) -> Dict[str, Optional[Peak]]:
        """
        Match a list of detected peaks to target compounds.

        Parameters
        ----------
        peaks : List[Peak]
            Detected peaks (unordered).
        compounds : List[CompoundDefinition]
            Target compounds with RT windows.

        Returns
        -------
        Dict[str, Optional[Peak]]
            Mapping of ``compound.name`` to matched Peak (or ``None``
            if no peak was found in the compound's RT window).
        """
        result: Dict[str, Optional[Peak]] = {}
        tol = self._config.rt_tolerance

        for compound in compounds:
            window_start = compound.rt_window_start - tol
            window_end = compound.rt_window_end + tol

            candidates = [
                peak for peak in peaks
                if window_start <= peak.rt <= window_end
            ]

            if len(candidates) == 0:
                logger.debug(
                    "No peak found for compound '%s' in RT window [%.3f, %.3f]",
                    compound.name, window_start, window_end,
                )
                result[compound.name] = None

            elif len(candidates) == 1:
                result[compound.name] = candidates[0]

            else:
                # Multiple candidates
                if self._config.prefer_largest_area:
                    best = max(candidates, key=lambda p: p.area)
                    logger.info(
                        "Multiple peaks (%d) in RT window for '%s'; "
                        "selected peak at RT=%.3f with area=%.1f (largest).",
                        len(candidates), compound.name, best.rt, best.area,
                    )
                    result[compound.name] = best
                elif self._config.require_single_match:
                    rts = ', '.join(f'{p.rt:.3f}' for p in candidates)
                    raise ValueError(
                        f"Ambiguous match for compound '{compound.name}': "
                        f"found {len(candidates)} peaks at RT [{rts}] within "
                        f"window [{window_start:.3f}, {window_end:.3f}]. "
                        f"Set prefer_largest_area=True to auto-select."
                    )
                else:
                    # Take first by RT order (deterministic fallback)
                    best = min(candidates, key=lambda p: abs(p.rt - (window_start + window_end) / 2))
                    result[compound.name] = best

        return result
