"""
qc_checker.py — QC flag determination.

SRP: Only responsible for producing QC flags for QuantResult objects.
"""
from .method_config_lc import QcConfig
from .models import QuantResult, SampleMeta


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
