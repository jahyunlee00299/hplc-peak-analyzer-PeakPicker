"""
SciPy Statistical Analyzer
============================

Concrete implementation of IStatisticalAnalyzer using SciPy for ANOVA
and a manual Tukey HSD implementation for post-hoc pairwise comparisons.

Following Dependency Inversion Principle (DIP) - this adapter can be
swapped for testing or alternative statistical backends.
"""

import logging
from itertools import combinations
from typing import List, Dict, Tuple

import numpy as np
from scipy import stats

from ...interfaces.quantification import IStatisticalAnalyzer
from ...domain.models import (
    QuantificationResult,
    StatisticalAnalysisResult,
    StatisticalTestResult,
    TukeyHSDComparison,
)
from ...config.quantification_config import StatisticalConfig

logger = logging.getLogger(__name__)


class ScipyStatisticalAnalyzer(IStatisticalAnalyzer):
    """
    Performs statistical analysis (one-way ANOVA + Tukey HSD) on
    quantification results.

    For each compound x enzyme x time_point combination, this class:
    1. Collects concentration data grouped by the specified group variable
    2. Runs one-way ANOVA to test for overall group differences
    3. Runs Tukey HSD post-hoc test for pairwise comparisons
    4. Assembles StatisticalTestResult objects

    Constructor Dependencies:
        config: StatisticalConfig controlling analysis parameters
    """

    def __init__(self, config: StatisticalConfig) -> None:
        self._config = config

    def analyze(
        self,
        quantification_result: QuantificationResult,
        group_variable: str,
        alpha: float,
    ) -> StatisticalAnalysisResult:
        """
        Perform statistical analysis across all compound/enzyme/time combinations.

        Args:
            quantification_result: Quantified peaks from batch processing.
            group_variable: Condition attribute to group by (e.g., "cofactor_dose").
            alpha: Significance level for statistical tests.

        Returns:
            StatisticalAnalysisResult containing all test results.
        """
        test_results: List[StatisticalTestResult] = []

        # Determine which compounds, enzymes, and time points are present
        compounds = self._get_unique_compounds(quantification_result)
        enzymes = self._config.enzyme_conditions
        time_points = self._config.time_points

        for compound_name in compounds:
            for enzyme in enzymes:
                for time_h in time_points:
                    result = self._analyze_single_condition(
                        quantification_result=quantification_result,
                        compound_name=compound_name,
                        enzyme=enzyme,
                        time_h=time_h,
                        group_variable=group_variable,
                        alpha=alpha,
                    )
                    if result is not None:
                        test_results.append(result)

        logger.info(
            "Completed statistical analysis: %d test results across "
            "%d compounds, %d enzymes, %d time points.",
            len(test_results), len(compounds), len(enzymes), len(time_points),
        )

        return StatisticalAnalysisResult(
            test_results=test_results,
            alpha=alpha,
        )

    def _analyze_single_condition(
        self,
        quantification_result: QuantificationResult,
        compound_name: str,
        enzyme: str,
        time_h: str,
        group_variable: str,
        alpha: float,
    ) -> StatisticalTestResult | None:
        """
        Analyze a single compound/enzyme/time_h combination.

        Returns None if insufficient data for analysis.
        """
        # Get all quantified peaks for this condition
        peaks = quantification_result.get_by_conditions(
            compound_name=compound_name,
            enzyme=enzyme,
            time_h=time_h,
        )

        # Optionally exclude negative controls
        if self._config.exclude_negative_controls:
            peaks = [qp for qp in peaks if not qp.sample_conditions.is_negative_control]

        if not peaks:
            logger.debug(
                "No data for %s / %s / %s. Skipping.",
                compound_name, enzyme, time_h,
            )
            return None

        # Group concentrations by the group variable
        groups: Dict[str, List[float]] = {}
        for qp in peaks:
            group_key = getattr(qp.sample_conditions, group_variable, "")
            if not group_key:
                continue
            groups.setdefault(group_key, []).append(qp.concentration_original)

        # Filter out groups with insufficient replicates
        groups = {
            k: v for k, v in groups.items()
            if len(v) >= self._config.min_replicates
        }

        if len(groups) < 2:
            logger.debug(
                "Fewer than 2 groups with sufficient replicates for "
                "%s / %s / %s. Skipping.",
                compound_name, enzyme, time_h,
            )
            return None

        # Order groups according to config dose_order if applicable
        ordered_names = self._order_group_names(list(groups.keys()))
        groups_data = [np.array(groups[name]) for name in ordered_names]

        # Run one-way ANOVA
        f_stat, p_value = self._run_anova(groups_data)
        anova_sig = self._significance_label(p_value, alpha)

        # Run Tukey HSD post-hoc test
        pairwise = self._tukey_hsd(groups_data, ordered_names, alpha)

        # Compute group summary statistics
        group_means = {name: float(np.mean(data)) for name, data in zip(ordered_names, groups_data)}
        group_stds = {name: float(np.std(data, ddof=1)) if len(data) > 1 else 0.0
                      for name, data in zip(ordered_names, groups_data)}
        group_ns = {name: len(data) for name, data in zip(ordered_names, groups_data)}

        return StatisticalTestResult(
            compound_name=compound_name,
            enzyme=enzyme,
            time_h=time_h,
            group_variable=group_variable,
            anova_f_statistic=f_stat,
            anova_p_value=p_value,
            anova_significance=anova_sig,
            pairwise_comparisons=pairwise,
            group_means=group_means,
            group_stds=group_stds,
            group_ns=group_ns,
        )

    @staticmethod
    def _run_anova(groups_data: List[np.ndarray]) -> Tuple[float, float]:
        """
        Run one-way ANOVA using scipy.stats.f_oneway.

        Returns (f_statistic, p_value). Returns (0.0, 1.0) if the test
        cannot be performed (e.g., zero variance within all groups).
        """
        try:
            f_stat, p_value = stats.f_oneway(*groups_data)
            # Handle NaN results (e.g., all values identical)
            if np.isnan(f_stat) or np.isnan(p_value):
                return 0.0, 1.0
            return float(f_stat), float(p_value)
        except Exception as e:
            logger.warning("ANOVA failed: %s", e)
            return 0.0, 1.0

    @staticmethod
    def _tukey_hsd(
        groups_data: List[np.ndarray],
        group_names: List[str],
        alpha: float,
    ) -> List[TukeyHSDComparison]:
        """
        Manual Tukey HSD implementation for pairwise comparisons.

        Uses the studentized range approach with Bonferroni-style
        p-value adjustment, matching the reference implementation
        from plot_cofactor_final.py.

        Args:
            groups_data: List of arrays, one per group.
            group_names: Corresponding group labels.
            alpha: Significance level.

        Returns:
            List of TukeyHSDComparison objects for all pairwise comparisons.
        """
        k = len(groups_data)
        all_data = np.concatenate(groups_data)
        n_total = len(all_data)
        ns = [len(g) for g in groups_data]
        means = [float(np.mean(g)) for g in groups_data]

        # Within-group sum of squares
        ss_within = sum(
            float(np.sum((g - np.mean(g)) ** 2)) for g in groups_data
        )
        df_within = n_total - k

        if df_within <= 0:
            logger.warning(
                "Insufficient degrees of freedom for Tukey HSD "
                "(df_within=%d). Returning empty comparisons.",
                df_within,
            )
            return []

        ms_within = ss_within / df_within

        comparisons: List[TukeyHSDComparison] = []

        for i, j in combinations(range(k), 2):
            if ns[i] == 0 or ns[j] == 0:
                continue

            diff = abs(means[i] - means[j])

            # Standard error for the studentized range statistic
            se = np.sqrt(ms_within * (1.0 / ns[i] + 1.0 / ns[j]) / 2.0)

            if se == 0:
                continue

            q_stat = diff / se

            # Convert q to t and compute p-value using t-distribution
            t_stat = q_stat / np.sqrt(2)
            p_val = 2.0 * (1.0 - stats.t.cdf(t_stat, df_within))

            # Bonferroni correction: multiply by number of comparisons
            n_comparisons = k * (k - 1) / 2
            p_adj = min(p_val * n_comparisons, 1.0)

            # Determine significance label
            if p_adj < 0.001:
                sig = "***"
            elif p_adj < 0.01:
                sig = "**"
            elif p_adj < alpha:
                sig = "*"
            else:
                sig = "ns"

            comparisons.append(TukeyHSDComparison(
                group1_name=group_names[i],
                group2_name=group_names[j],
                mean_difference=diff,
                mean_group1=means[i],
                mean_group2=means[j],
                q_statistic=float(q_stat),
                p_adjusted=float(p_adj),
                significance=sig,
            ))

        return comparisons

    def _order_group_names(self, names: List[str]) -> List[str]:
        """
        Order group names according to config dose_order.

        Groups not in dose_order are appended at the end in their
        original order.
        """
        dose_order = self._config.dose_order
        ordered = [name for name in dose_order if name in names]
        remaining = [name for name in names if name not in dose_order]
        return ordered + remaining

    def _get_unique_compounds(
        self, quantification_result: QuantificationResult
    ) -> List[str]:
        """Extract unique compound names preserving insertion order."""
        return quantification_result.compound_names

    @staticmethod
    def _significance_label(p_value: float, alpha: float) -> str:
        """Convert p-value to significance label string."""
        if p_value < 0.001:
            return "***"
        elif p_value < 0.01:
            return "**"
        elif p_value < alpha:
            return "*"
        return "ns"
