"""
Baseline Correction Interfaces
==============================

Abstract interfaces for baseline correction operations.
Following Interface Segregation Principle (ISP) - multiple
small interfaces instead of one large interface.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
import numpy as np

from ..domain import AnchorPoint, BaselineResult, BaselineMethod


class IAnchorFinder(ABC):
    """
    Interface for finding baseline anchor points.

    Single Responsibility: Only finds anchor points.
    """

    @abstractmethod
    def find_anchors(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> List[AnchorPoint]:
        """
        Find baseline anchor points in signal.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        List[AnchorPoint]
            Detected anchor points sorted by index
        """
        pass


class IBaselineGenerator(ABC):
    """
    Interface for generating baseline from anchor points.

    Single Responsibility: Only generates baseline.
    """

    @abstractmethod
    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint]
    ) -> np.ndarray:
        """
        Generate baseline from anchor points.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        anchors : List[AnchorPoint]
            Anchor points for baseline

        Returns
        -------
        np.ndarray
            Generated baseline
        """
        pass


class IBaselineStrategy(ABC):
    """
    Strategy interface for baseline generation methods.

    Open/Closed Principle: New strategies can be added
    without modifying existing code.
    """

    @property
    @abstractmethod
    def method(self) -> BaselineMethod:
        """Return the baseline method enum."""
        pass

    @abstractmethod
    def generate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        anchors: List[AnchorPoint],
        **kwargs
    ) -> np.ndarray:
        """
        Generate baseline using this strategy.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        anchors : List[AnchorPoint]
            Anchor points
        **kwargs
            Strategy-specific parameters

        Returns
        -------
        np.ndarray
            Generated baseline
        """
        pass


class ISignalPostProcessor(ABC):
    """
    Interface for post-processing corrected signals.

    Single Responsibility: Only handles post-processing.
    """

    @abstractmethod
    def process(
        self,
        corrected_signal: np.ndarray,
        original_signal: np.ndarray = None,
        baseline: np.ndarray = None
    ) -> np.ndarray:
        """
        Post-process baseline corrected signal.

        Parameters
        ----------
        corrected_signal : np.ndarray
            Baseline corrected signal
        original_signal : np.ndarray, optional
            Original signal for reference
        baseline : np.ndarray, optional
            Applied baseline for reference

        Returns
        -------
        np.ndarray
            Post-processed signal
        """
        pass


class IBaselineEvaluator(ABC):
    """
    Interface for evaluating baseline quality.

    Single Responsibility: Only evaluates quality.
    """

    @abstractmethod
    def evaluate(
        self,
        signal: np.ndarray,
        baseline: np.ndarray,
        corrected: np.ndarray
    ) -> Dict[str, float]:
        """
        Evaluate baseline correction quality.

        Parameters
        ----------
        signal : np.ndarray
            Original signal
        baseline : np.ndarray
            Applied baseline
        corrected : np.ndarray
            Corrected signal

        Returns
        -------
        Dict[str, float]
            Quality metrics:
            - negative_ratio: fraction of negative values
            - smoothness: baseline smoothness
            - peak_preservation: how well peaks are preserved
            - overall_score: combined quality score
        """
        pass


class IBaselineOptimizer(ABC):
    """
    Interface for optimizing baseline parameters.

    Single Responsibility: Only handles optimization.
    """

    @abstractmethod
    def optimize(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        strategies: List[IBaselineStrategy],
        anchor_finder: IAnchorFinder
    ) -> Tuple[BaselineResult, Dict[str, Any]]:
        """
        Find optimal baseline parameters.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        strategies : List[IBaselineStrategy]
            Available baseline strategies
        anchor_finder : IAnchorFinder
            Anchor point finder

        Returns
        -------
        BaselineResult
            Best baseline result
        Dict[str, Any]
            Optimization information
        """
        pass


class IBaselineCorrector(ABC):
    """
    High-level interface for complete baseline correction.

    Composes other interfaces to provide complete functionality.
    Follows Dependency Inversion - depends on abstractions.
    """

    @abstractmethod
    def correct(
        self,
        time: np.ndarray,
        signal: np.ndarray
    ) -> BaselineResult:
        """
        Perform complete baseline correction.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array

        Returns
        -------
        BaselineResult
            Complete baseline correction result
        """
        pass
