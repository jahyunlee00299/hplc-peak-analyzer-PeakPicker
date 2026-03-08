"""
Regex Sample Name Parser
=========================

Concrete implementation of ISampleNameParser that extracts experimental
conditions from Agilent .D folder names using configurable regex patterns.

Example folder name:
    ``EXP01_D3_RO_GO_2_24H.D``
       ^cofactor ^enzyme ^rep ^time
"""

import re
from typing import Dict, Any

from ...interfaces import ISampleNameParser
from ...domain import SampleConditions
from ...config.quantification_config import SampleNameParserConfig


class RegexSampleNameParser(ISampleNameParser):
    """
    Parses experimental conditions from sample/folder names using regex.

    All patterns are configurable via SampleNameParserConfig.  The parser
    first checks for the negative-control marker and short-circuits with
    default NC values if found.  Otherwise each regex is applied
    independently against the sample name.

    Parameters
    ----------
    config : SampleNameParserConfig, optional
        Configuration with regex patterns.  Uses sensible defaults if
        not provided.
    """

    def __init__(self, config: SampleNameParserConfig | None = None):
        self._config = config or SampleNameParserConfig()

    # ------------------------------------------------------------------
    # ISampleNameParser interface
    # ------------------------------------------------------------------

    def parse(self, sample_name: str) -> SampleConditions:
        """
        Parse a sample name string into structured SampleConditions.

        Parameters
        ----------
        sample_name : str
            Raw sample / folder name, e.g. ``EXP01_D3_RO_GO_2_24H.D``.

        Returns
        -------
        SampleConditions
            Parsed experimental conditions.
        """
        cfg = self._config

        # --- Negative control short-circuit ---
        if cfg.negative_control_marker and cfg.negative_control_marker in sample_name:
            return SampleConditions(
                sample_name=sample_name,
                cofactor_dose='NC',
                enzyme='NC',
                replicate='',
                time_h=cfg.nc_time_label,
                is_negative_control=True,
            )

        # --- Extract each field independently ---
        cofactor_dose = self._search(cfg.cofactor_dose_pattern, sample_name)
        enzyme = self._search(cfg.enzyme_pattern, sample_name)
        replicate = self._search(cfg.replicate_pattern, sample_name)
        time_h = self._search(
            cfg.time_pattern, sample_name, flags=re.IGNORECASE,
        )

        return SampleConditions(
            sample_name=sample_name,
            cofactor_dose=cofactor_dose,
            enzyme=enzyme,
            replicate=replicate,
            time_h=time_h,
            is_negative_control=False,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _search(pattern: str, text: str, flags: int = 0) -> str:
        """
        Apply a regex pattern and return the first captured group, or ``""``
        if there is no match.

        Parameters
        ----------
        pattern : str
            Regex with at least one capturing group.
        text : str
            The string to search.
        flags : int, optional
            Regex flags (e.g., ``re.IGNORECASE``).

        Returns
        -------
        str
            Matched group(1) or empty string.
        """
        if not pattern:
            return ''
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1)
        return ''
