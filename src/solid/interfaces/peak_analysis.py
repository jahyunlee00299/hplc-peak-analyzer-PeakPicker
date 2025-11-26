"""
Peak Analysis Interfaces
========================

Abstract interfaces for peak detection and analysis.
Following Interface Segregation Principle (ISP).
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
import numpy as np

from ..domain import Peak, DeconvolutionResult, DeconvolvedPeak


class IPeakDetector(ABC):
    """
    Interface for peak detection.

    Single Responsibility: Only detects peaks.
    """

    @abstractmethod
    def detect(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        baseline: np.ndarray = None
    ) -> List[Peak]:
        """
        Detect peaks in signal.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        baseline : np.ndarray, optional
            Baseline for correction

        Returns
        -------
        List[Peak]
            Detected peaks
        """
        pass


class IPeakBoundaryFinder(ABC):
    """
    Interface for finding peak boundaries.

    Single Responsibility: Only finds boundaries.
    """

    @abstractmethod
    def find_boundaries(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int,
        baseline: np.ndarray = None
    ) -> Tuple[int, int]:
        """
        Find peak start and end indices.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_index : int
            Index of peak maximum
        baseline : np.ndarray, optional
            Baseline for reference

        Returns
        -------
        Tuple[int, int]
            Start and end indices
        """
        pass


class IAreaCalculator(ABC):
    """
    Interface for peak area calculation.

    Single Responsibility: Only calculates areas.
    """

    @abstractmethod
    def calculate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        start_idx: int,
        end_idx: int,
        baseline: np.ndarray = None
    ) -> float:
        """
        Calculate peak area.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        start_idx : int
            Peak start index
        end_idx : int
            Peak end index
        baseline : np.ndarray, optional
            Baseline to subtract

        Returns
        -------
        float
            Calculated area
        """
        pass


class IDeconvolutionAnalyzer(ABC):
    """
    Interface for analyzing if deconvolution is needed.

    Single Responsibility: Only analyzes need for deconvolution.
    """

    @abstractmethod
    def needs_deconvolution(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int
    ) -> Tuple[bool, str]:
        """
        Determine if peak needs deconvolution.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_index : int
            Index of peak maximum

        Returns
        -------
        Tuple[bool, str]
            (needs_deconvolution, reason)
        """
        pass


class IPeakCenterEstimator(ABC):
    """
    Interface for estimating peak center positions.

    Single Responsibility: Only estimates centers.
    """

    @abstractmethod
    def estimate_centers(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        max_components: int = 4
    ) -> List[float]:
        """
        Estimate positions of peak centers.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        max_components : int
            Maximum number of components

        Returns
        -------
        List[float]
            Estimated retention times of centers
        """
        pass


class ICurveFitterStrategy(ABC):
    """
    Strategy interface for curve fitting in deconvolution.

    Open/Closed: New fitting strategies can be added.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name."""
        pass

    @abstractmethod
    def fit(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        centers: List[float]
    ) -> Tuple[List[DeconvolvedPeak], float, float]:
        """
        Fit peaks to signal.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        centers : List[float]
            Initial center estimates

        Returns
        -------
        Tuple[List[DeconvolvedPeak], float, float]
            (peaks, r2_score, rmse)
        """
        pass


class IDeconvolver(ABC):
    """
    High-level interface for peak deconvolution.

    Composes other interfaces for complete deconvolution.
    """

    @abstractmethod
    def deconvolve(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_start_idx: int,
        peak_end_idx: int,
        initial_centers: List[float] = None
    ) -> DeconvolutionResult:
        """
        Deconvolve overlapping peaks.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_start_idx : int
            Peak region start
        peak_end_idx : int
            Peak region end
        initial_centers : List[float], optional
            Initial center estimates

        Returns
        -------
        DeconvolutionResult
            Deconvolution result
        """
        pass


class IAsymmetryCalculator(ABC):
    """
    Interface for peak asymmetry calculation.
    """

    @abstractmethod
    def calculate(
        self,
        time: np.ndarray,
        signal: np.ndarray,
        peak_index: int
    ) -> float:
        """
        Calculate peak asymmetry factor.

        Parameters
        ----------
        time : np.ndarray
            Time array
        signal : np.ndarray
            Signal intensity array
        peak_index : int
            Index of peak maximum

        Returns
        -------
        float
            Asymmetry factor (1.0 = symmetric)
        """
        pass
