"""
Peak Models for HPLC Peak Deconvolution
========================================

This module provides mathematical models for different peak shapes commonly
encountered in HPLC chromatography.

Author: PeakPicker Project
Date: 2025-11-10
"""

import numpy as np
from scipy.special import wofz


def gaussian(x, amplitude, center, sigma):
    """
    Gaussian (normal) peak model.

    Most common peak shape in HPLC chromatography.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    amplitude : float
        Peak height
    center : float
        Peak center position (retention time)
    sigma : float
        Standard deviation (related to peak width)

    Returns
    -------
    array-like
        Peak intensities at each x position
    """
    return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))


def lorentzian(x, amplitude, center, gamma):
    """
    Lorentzian (Cauchy) peak model.

    Used for peaks with significant tailing.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    amplitude : float
        Peak height
    center : float
        Peak center position (retention time)
    gamma : float
        Half-width at half-maximum (HWHM)

    Returns
    -------
    array-like
        Peak intensities at each x position
    """
    return amplitude * (gamma ** 2) / ((x - center) ** 2 + gamma ** 2)


def voigt(x, amplitude, center, sigma, gamma):
    """
    Voigt peak model (convolution of Gaussian and Lorentzian).

    Provides better fit for real chromatographic peaks that have
    both Gaussian and Lorentzian character.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    amplitude : float
        Peak height
    center : float
        Peak center position (retention time)
    sigma : float
        Gaussian width parameter
    gamma : float
        Lorentzian width parameter

    Returns
    -------
    array-like
        Peak intensities at each x position
    """
    z = ((x - center) + 1j * gamma) / (sigma * np.sqrt(2))
    return amplitude * np.real(wofz(z)) / (sigma * np.sqrt(2 * np.pi))


def exponentially_modified_gaussian(x, amplitude, center, sigma, tau):
    """
    Exponentially Modified Gaussian (EMG) peak model.

    Excellent for modeling asymmetric peaks with tailing,
    common in reversed-phase HPLC.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    amplitude : float
        Peak height
    center : float
        Peak center position (retention time)
    sigma : float
        Gaussian width parameter
    tau : float
        Exponential decay time constant (tailing parameter)
        Positive tau = right tailing
        Negative tau = left tailing (fronting)

    Returns
    -------
    array-like
        Peak intensities at each x position
    """
    if abs(tau) < 1e-10:
        # If tau is very small, just return Gaussian
        return gaussian(x, amplitude, center, sigma)

    # EMG calculation using error function
    from scipy.special import erf

    term1 = (sigma ** 2) / (2 * tau ** 2)
    term2 = (x - center) / tau

    exponent = term1 - term2
    erf_arg = (x - center) / (np.sqrt(2) * sigma) - sigma / (np.sqrt(2) * tau)

    return (amplitude * sigma * np.sqrt(2 * np.pi) / (2 * tau)) * \
           np.exp(exponent) * (1 - erf(erf_arg))


def multi_gaussian(x, *params):
    """
    Multiple Gaussian peaks superimposed.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    *params : variable length argument list
        Parameters for each peak: [amp1, center1, sigma1, amp2, center2, sigma2, ...]
        Must be in groups of 3 (amplitude, center, sigma)

    Returns
    -------
    array-like
        Sum of all Gaussian peaks at each x position

    Examples
    --------
    >>> # Two Gaussian peaks
    >>> y = multi_gaussian(x, amp1, center1, sigma1, amp2, center2, sigma2)
    """
    if len(params) % 3 != 0:
        raise ValueError("Parameters must be in groups of 3 (amplitude, center, sigma)")

    n_peaks = len(params) // 3
    result = np.zeros_like(x, dtype=float)

    for i in range(n_peaks):
        amplitude = params[i * 3]
        center = params[i * 3 + 1]
        sigma = params[i * 3 + 2]
        result += gaussian(x, amplitude, center, sigma)

    return result


def multi_voigt(x, *params):
    """
    Multiple Voigt peaks superimposed.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    *params : variable length argument list
        Parameters for each peak: [amp1, center1, sigma1, gamma1, amp2, center2, sigma2, gamma2, ...]
        Must be in groups of 4 (amplitude, center, sigma, gamma)

    Returns
    -------
    array-like
        Sum of all Voigt peaks at each x position
    """
    if len(params) % 4 != 0:
        raise ValueError("Parameters must be in groups of 4 (amplitude, center, sigma, gamma)")

    n_peaks = len(params) // 4
    result = np.zeros_like(x, dtype=float)

    for i in range(n_peaks):
        amplitude = params[i * 4]
        center = params[i * 4 + 1]
        sigma = params[i * 4 + 2]
        gamma = params[i * 4 + 3]
        result += voigt(x, amplitude, center, sigma, gamma)

    return result


def multi_emg(x, *params):
    """
    Multiple Exponentially Modified Gaussian (EMG) peaks superimposed.

    Ideal for fitting asymmetric peaks with tailing commonly seen in HPLC.

    Parameters
    ----------
    x : array-like
        X-axis values (retention times)
    *params : variable length argument list
        Parameters for each peak: [amp1, center1, sigma1, tau1, amp2, center2, sigma2, tau2, ...]
        Must be in groups of 4 (amplitude, center, sigma, tau)

    Returns
    -------
    array-like
        Sum of all EMG peaks at each x position
    """
    if len(params) % 4 != 0:
        raise ValueError("Parameters must be in groups of 4 (amplitude, center, sigma, tau)")

    n_peaks = len(params) // 4
    result = np.zeros_like(x, dtype=float)

    for i in range(n_peaks):
        amplitude = params[i * 4]
        center = params[i * 4 + 1]
        sigma = params[i * 4 + 2]
        tau = params[i * 4 + 3]
        result += exponentially_modified_gaussian(x, amplitude, center, sigma, tau)

    return result


def estimate_tau_from_asymmetry(asymmetry, sigma):
    """
    Estimate EMG tau parameter from peak asymmetry factor.

    Parameters
    ----------
    asymmetry : float
        Asymmetry factor (b/a at 10% height)
        1.0 = symmetric, >1.0 = tailing, <1.0 = fronting
    sigma : float
        Gaussian width parameter

    Returns
    -------
    float
        Estimated tau value for EMG model
    """
    # Empirical relationship: tau ≈ sigma * (asymmetry - 1) for moderate tailing
    # For asymmetry close to 1, tau should be small
    if asymmetry <= 1.0:
        return sigma * 0.01  # Near-symmetric, minimal tau
    elif asymmetry < 1.5:
        return sigma * (asymmetry - 1.0) * 0.5
    else:
        # Strong tailing
        return sigma * (asymmetry - 1.0) * 0.7


def estimate_peak_width(x, y, center_idx):
    """
    Estimate peak width (sigma) from data.

    Uses FWHM (Full Width at Half Maximum) to estimate Gaussian sigma.

    Parameters
    ----------
    x : array-like
        X-axis values
    y : array-like
        Y-axis values (peak intensities)
    center_idx : int
        Index of peak center

    Returns
    -------
    float
        Estimated sigma value
    """
    if center_idx < 0 or center_idx >= len(y):
        return 0.1  # Default fallback

    peak_height = y[center_idx]
    half_max = peak_height / 2

    # Find left half-maximum point
    left_idx = center_idx
    while left_idx > 0 and y[left_idx] > half_max:
        left_idx -= 1

    # Find right half-maximum point
    right_idx = center_idx
    while right_idx < len(y) - 1 and y[right_idx] > half_max:
        right_idx += 1

    # Calculate FWHM
    fwhm = x[right_idx] - x[left_idx]

    # Convert FWHM to sigma: FWHM = 2.355 * sigma
    sigma = fwhm / 2.355

    return max(sigma, 0.01)  # Ensure minimum width


def calculate_peak_asymmetry(x, y, center_idx):
    """
    Calculate peak asymmetry factor.

    Asymmetry = b/a where:
    - a = distance from leading edge to peak center at 10% height
    - b = distance from peak center to tailing edge at 10% height

    Parameters
    ----------
    x : array-like
        X-axis values
    y : array-like
        Y-axis values
    center_idx : int
        Index of peak center

    Returns
    -------
    float
        Asymmetry factor (1.0 = symmetric, >1.0 = tailing, <1.0 = fronting)
    """
    if center_idx < 1 or center_idx >= len(y) - 1:
        return 1.0

    peak_height = y[center_idx]
    ten_percent_height = peak_height * 0.1

    # Find left point at 10% height
    left_idx = center_idx
    while left_idx > 0 and y[left_idx] > ten_percent_height:
        left_idx -= 1

    # Find right point at 10% height
    right_idx = center_idx
    while right_idx < len(y) - 1 and y[right_idx] > ten_percent_height:
        right_idx += 1

    a = x[center_idx] - x[left_idx]  # Leading edge
    b = x[right_idx] - x[center_idx]  # Tailing edge

    if a < 1e-10:
        return 1.0

    return b / a


if __name__ == "__main__":
    # Test and visualize peak models
    import matplotlib.pyplot as plt

    x = np.linspace(0, 10, 1000)

    # Test different peak models
    gauss = gaussian(x, amplitude=100, center=5, sigma=0.5)
    lorentz = lorentzian(x, amplitude=100, center=5, gamma=0.3)
    voigt_peak = voigt(x, amplitude=100, center=5, sigma=0.5, gamma=0.3)
    emg = exponentially_modified_gaussian(x, amplitude=100, center=5, sigma=0.5, tau=0.3)

    plt.figure(figsize=(12, 8))

    plt.subplot(2, 2, 1)
    plt.plot(x, gauss, 'b-', linewidth=2)
    plt.title('Gaussian Peak')
    plt.xlabel('Retention Time')
    plt.ylabel('Intensity')
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 2, 2)
    plt.plot(x, lorentz, 'r-', linewidth=2)
    plt.title('Lorentzian Peak')
    plt.xlabel('Retention Time')
    plt.ylabel('Intensity')
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 2, 3)
    plt.plot(x, voigt_peak, 'g-', linewidth=2)
    plt.title('Voigt Peak')
    plt.xlabel('Retention Time')
    plt.ylabel('Intensity')
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 2, 4)
    plt.plot(x, emg, 'm-', linewidth=2)
    plt.title('EMG Peak (Tailing)')
    plt.xlabel('Retention Time')
    plt.ylabel('Intensity')
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('peak_models_test.png', dpi=150)
    print("Peak models test plot saved to 'peak_models_test.png'")

    # Test multi-peak fitting
    plt.figure(figsize=(10, 6))
    multi = multi_gaussian(x, 80, 4, 0.3, 60, 5.5, 0.4, 40, 6.5, 0.35)
    plt.plot(x, multi, 'b-', linewidth=2, label='Multi-Gaussian (3 peaks)')
    plt.plot(x, gaussian(x, 80, 4, 0.3), 'r--', alpha=0.6, label='Peak 1')
    plt.plot(x, gaussian(x, 60, 5.5, 0.4), 'g--', alpha=0.6, label='Peak 2')
    plt.plot(x, gaussian(x, 40, 6.5, 0.35), 'm--', alpha=0.6, label='Peak 3')
    plt.title('Multi-Gaussian Peak Fitting')
    plt.xlabel('Retention Time')
    plt.ylabel('Intensity')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('multi_gaussian_test.png', dpi=150)
    print("Multi-Gaussian test plot saved to 'multi_gaussian_test.png'")
