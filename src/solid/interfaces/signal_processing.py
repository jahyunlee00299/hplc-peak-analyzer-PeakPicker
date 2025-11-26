"""
Signal Processing Interfaces
============================

Abstract interfaces for signal processing operations.
Following Dependency Inversion Principle (DIP) - high-level modules
depend on abstractions, not concrete implementations.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Callable, List
import numpy as np


class ISignalProcessor(ABC):
    """
    Interface for signal processing operations.

    Abstracts scipy.signal operations for testability
    and flexibility to swap implementations.
    """

    @abstractmethod
    def find_peaks(
        self,
        signal: np.ndarray,
        prominence: float = None,
        distance: int = None,
        height: float = None,
        width: float = None
    ) -> Tuple[np.ndarray, dict]:
        """
        Find peaks in signal.

        Parameters
        ----------
        signal : np.ndarray
            Input signal array
        prominence : float, optional
            Minimum prominence of peaks
        distance : int, optional
            Minimum distance between peaks
        height : float, optional
            Minimum height of peaks
        width : float, optional
            Minimum width of peaks

        Returns
        -------
        peaks : np.ndarray
            Indices of peaks
        properties : dict
            Peak properties (prominences, widths, etc.)
        """
        pass

    @abstractmethod
    def smooth(
        self,
        signal: np.ndarray,
        window_length: int,
        polyorder: int = 2
    ) -> np.ndarray:
        """
        Smooth signal using Savitzky-Golay filter.

        Parameters
        ----------
        signal : np.ndarray
            Input signal
        window_length : int
            Window length for filter
        polyorder : int
            Polynomial order

        Returns
        -------
        np.ndarray
            Smoothed signal
        """
        pass

    @abstractmethod
    def derivative(
        self,
        signal: np.ndarray,
        order: int = 1,
        window_length: int = 5
    ) -> np.ndarray:
        """
        Calculate signal derivative.

        Parameters
        ----------
        signal : np.ndarray
            Input signal
        order : int
            Derivative order (1, 2, etc.)
        window_length : int
            Window length for smoothing

        Returns
        -------
        np.ndarray
            Derivative signal
        """
        pass


class IInterpolator(ABC):
    """
    Interface for interpolation operations.

    Abstracts scipy.interpolate functions.
    """

    @abstractmethod
    def linear(
        self,
        x: np.ndarray,
        y: np.ndarray,
        x_new: np.ndarray
    ) -> np.ndarray:
        """
        Linear interpolation.

        Parameters
        ----------
        x : np.ndarray
            Original x values
        y : np.ndarray
            Original y values
        x_new : np.ndarray
            New x values to interpolate

        Returns
        -------
        np.ndarray
            Interpolated y values
        """
        pass

    @abstractmethod
    def spline(
        self,
        x: np.ndarray,
        y: np.ndarray,
        x_new: np.ndarray,
        smoothing: float = 0.0,
        weights: np.ndarray = None
    ) -> np.ndarray:
        """
        Spline interpolation.

        Parameters
        ----------
        x : np.ndarray
            Original x values
        y : np.ndarray
            Original y values
        x_new : np.ndarray
            New x values to interpolate
        smoothing : float
            Smoothing factor
        weights : np.ndarray, optional
            Weights for each point

        Returns
        -------
        np.ndarray
            Interpolated y values
        """
        pass


class ICurveFitter(ABC):
    """
    Interface for curve fitting operations.

    Abstracts scipy.optimize.curve_fit.
    """

    @abstractmethod
    def fit(
        self,
        func: Callable,
        x: np.ndarray,
        y: np.ndarray,
        p0: List[float],
        bounds: Tuple[List[float], List[float]] = None,
        maxfev: int = 5000
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fit function to data.

        Parameters
        ----------
        func : Callable
            Model function to fit
        x : np.ndarray
            X data
        y : np.ndarray
            Y data
        p0 : List[float]
            Initial parameter guesses
        bounds : tuple, optional
            Parameter bounds (lower, upper)
        maxfev : int
            Maximum function evaluations

        Returns
        -------
        popt : np.ndarray
            Optimal parameters
        pcov : np.ndarray
            Covariance matrix
        """
        pass


class IIntegrator(ABC):
    """
    Interface for numerical integration.

    Abstracts scipy.integrate functions.
    """

    @abstractmethod
    def trapezoid(
        self,
        y: np.ndarray,
        x: np.ndarray = None,
        dx: float = 1.0
    ) -> float:
        """
        Trapezoidal integration.

        Parameters
        ----------
        y : np.ndarray
            Values to integrate
        x : np.ndarray, optional
            X coordinates
        dx : float
            Spacing if x not provided

        Returns
        -------
        float
            Integrated value
        """
        pass

    @abstractmethod
    def simpson(
        self,
        y: np.ndarray,
        x: np.ndarray = None,
        dx: float = 1.0
    ) -> float:
        """
        Simpson's rule integration.

        Parameters
        ----------
        y : np.ndarray
            Values to integrate
        x : np.ndarray, optional
            X coordinates
        dx : float
            Spacing if x not provided

        Returns
        -------
        float
            Integrated value
        """
        pass
