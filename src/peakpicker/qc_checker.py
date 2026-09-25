"""
qc_checker.py — QC flag determination.

SRP: Only responsible for producing QC flags for QuantResult objects.
"""
import logging
from typing import List

from .method_config_lc import QcConfig
from .models import CompoundMethod, QuantResult, SampleMeta

logger = logging.getLogger(__name__)


def check_calibration_quality(
    compounds: List[CompoundMethod],
    config: QcConfig,
) -> List[str]:
    """Audit calibration provenance at method-load time.

    `qc.min_r2_calibration` sat in the config unread for as long as it existed:
    the loader never parsed `r2`, so nothing could compare against it. Now that
    r2 and source survive loading, check them once when the method is loaded
    rather than per result — a bad calibration curve is a property of the method,
    not of an individual peak.

    Advisory by design: these YAMLs are the record of past experiments, and
    raising here would make historical methods unloadable. Returns the warnings
    so callers can surface or escalate them.
    """
    warnings: List[str] = []
    for c in compounds:
        if c.slope is None:
            continue  # no calibration declared at all — not a provenance problem
        if c.r2 is None:
            warnings.append(
                f"{c.name}: calibration r2 not recorded "
                f"(qc.min_r2_calibration={config.min_r2_calibration} cannot be checked)"
            )
        elif c.r2 < config.min_r2_calibration:
            warnings.append(
                f"{c.name}: calibration r2={c.r2:.4f} "
                f"below min_r2_calibration={config.min_r2_calibration}"
            )
        if not c.source:
            warnings.append(f"{c.name}: calibration source not recorded")

    for w in warnings:
        logger.warning("Calibration QC — %s", w)
    return warnings


class QcChecker:
    """Assigns a QC flag string to each QuantResult."""

    def __init__(
        self,
        config: QcConfig,
        product_compound_name: str = "Xul-5P",
    ):
        self._cfg = config
        self._product = product_compound_name

    def check(self, result: QuantResult, sample: SampleMeta) -> str:
        """
        Returns:
            ""         — no issue
            "NO_PEAK"  — area is None (peak not detected)
            "NE_WARN"  — NE control sample has unexpectedly large product area
            "LOW_AREA" — area below detection threshold (future use)
        """
        if result.area is None:
            return "NO_PEAK"

        if (
            sample.is_ne
            and result.compound == self._product
            and result.area > self._cfg.max_product_area_ne
        ):
            return "NE_WARN"

        return ""
