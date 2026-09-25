"""
Batch Quantifier
=================

Concrete implementation of IQuantifier that orchestrates batch quantification
by delegating to ISampleNameParser, IPeakMatcher, and ICalibrationCalculator.

Following Dependency Inversion Principle (DIP) - depends on abstractions,
not concrete implementations.
"""

import logging
from typing import List

from ...interfaces.quantification import (
    IQuantifier,
    ISampleNameParser,
    IPeakMatcher,
    ICalibrationCalculator,
)
from ...domain.models import (
    BatchResult,
    CompoundDefinition,
    QuantifiedPeak,
    QuantificationResult,
)

logger = logging.getLogger(__name__)


class BatchQuantifier(IQuantifier):
    """
    Orchestrates batch quantification: parsing + matching + calibration.

    For each sample in a BatchResult, this class:
    1. Parses the sample name to extract experimental conditions
    2. Matches detected peaks to known compounds by retention time
    3. Calculates concentrations using calibration curves
    4. Assembles QuantifiedPeak objects into a QuantificationResult

    Constructor Dependencies:
        parser: Extracts SampleConditions from sample names
        matcher: Matches detected peaks to compound RT windows
        calculator: Converts peak area to concentration via calibration
    """

    def __init__(
        self,
        parser: ISampleNameParser,
        matcher: IPeakMatcher,
        calculator: ICalibrationCalculator,
    ) -> None:
        self._parser = parser
        self._matcher = matcher
        self._calculator = calculator

    def quantify(
        self,
        batch_result: BatchResult,
        compounds: List[CompoundDefinition],
        dilution_factor: float,
    ) -> QuantificationResult:
        """
        Quantify all samples in a batch.

        Args:
            batch_result: Batch of chromatogram analysis results.
            compounds: Target compound definitions with RT windows and calibration.
            dilution_factor: Dilution factor applied during sample preparation.

        Returns:
            QuantificationResult containing all quantified peaks.
        """
        quantified_peaks: List[QuantifiedPeak] = []

        for analysis_result in batch_result.results:
            sample_name = analysis_result.chromatogram.sample_name

            # Step 1: Parse sample name to extract experimental conditions
            try:
                conditions = self._parser.parse(sample_name)
            except Exception as e:
                logger.warning(
                    "Failed to parse sample name '%s': %s. Skipping sample.",
                    sample_name, e,
                )
                continue

            # Step 2: Match detected peaks to known compounds by RT window
            try:
                matched = self._matcher.match(analysis_result.peaks, compounds)
            except Exception as e:
                logger.warning(
                    "Failed to match peaks for sample '%s': %s. Skipping sample.",
                    sample_name, e,
                )
                continue

            # Step 3: For each matched compound/peak, calculate concentration
            for compound in compounds:
                peak = matched.get(compound.name)
                if peak is None:
                    logger.debug(
                        "No peak matched for compound '%s' in sample '%s'.",
                        compound.name, sample_name,
                    )
                    continue

                try:
                    conc_diluted, conc_original = self._calculator.calculate_concentration(
                        area=peak.area,
                        compound=compound,
                        dilution_factor=dilution_factor,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to calculate concentration for compound '%s' "
                        "in sample '%s': %s. Skipping.",
                        compound.name, sample_name, e,
                    )
                    continue

                # Step 4: Create QuantifiedPeak
                qp = QuantifiedPeak(
                    peak=peak,
                    compound=compound,
                    sample_conditions=conditions,
                    area=peak.area,
                    concentration_diluted=conc_diluted,
                    concentration_original=conc_original,
                    dilution_factor=dilution_factor,
                )
                quantified_peaks.append(qp)

        logger.info(
            "Quantified %d peaks across %d samples for %d compounds.",
            len(quantified_peaks),
            batch_result.total_samples,
            len(compounds),
        )

        return QuantificationResult(
            quantified_peaks=quantified_peaks,
            compounds=compounds,
            dilution_factor=dilution_factor,
        )
