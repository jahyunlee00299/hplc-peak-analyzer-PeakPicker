"""
Quantitative analysis module with standard curves
"""

import numpy as np
from scipy import stats
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class StandardPoint:
    """Standard curve data point"""
    concentration: float
    area: float
    height: Optional[float] = None
    name: Optional[str] = None


@dataclass
class CalibrationCurve:
    """Calibration curve data"""
    standards: List[StandardPoint]
    slope: float
    intercept: float
    r_squared: float
    equation: str
    method: str = "linear"  # linear, quadratic, etc.


class QuantitativeAnalyzer:
    """Perform quantitative analysis using standard curves"""

    def __init__(self):
        """Initialize quantitative analyzer"""
        self.curves: Dict[str, CalibrationCurve] = {}

    def create_standard_curve(
        self,
        concentrations: List[float],
        areas: List[float],
        curve_name: str = "default",
        method: str = "linear",
        force_zero: bool = False
    ) -> CalibrationCurve:
        """
        Create standard calibration curve

        Args:
            concentrations: List of standard concentrations
            areas: List of corresponding peak areas
            curve_name: Name for this curve
            method: Fitting method ('linear', 'quadratic')
            force_zero: Force curve through origin

        Returns:
            CalibrationCurve object
        """
        concentrations = np.array(concentrations)
        areas = np.array(areas)

        if len(concentrations) != len(areas):
            raise ValueError("Concentrations and areas must have same length")

        if len(concentrations) < 2:
            raise ValueError("Need at least 2 standards for calibration")

        # Create standard points
        standards = [
            StandardPoint(conc, area)
            for conc, area in zip(concentrations, areas)
        ]

        # Fit curve
        if method == "linear":
            if force_zero:
                # Force through origin
                slope = np.sum(concentrations * areas) / np.sum(concentrations ** 2)
                intercept = 0
                # Calculate R-squared
                y_pred = slope * concentrations
                ss_res = np.sum((areas - y_pred) ** 2)
                ss_tot = np.sum((areas - np.mean(areas)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            else:
                # Linear regression
                slope, intercept, r_value, p_value, std_err = stats.linregress(
                    concentrations, areas
                )
                r_squared = r_value ** 2

            equation = f"y = {slope:.4f}x + {intercept:.4f}"

        elif method == "quadratic":
            # Quadratic fit
            coeffs = np.polyfit(concentrations, areas, 2)
            slope = coeffs[1]  # Linear coefficient
            intercept = coeffs[2]  # Constant

            # Calculate R-squared
            y_pred = np.polyval(coeffs, concentrations)
            ss_res = np.sum((areas - y_pred) ** 2)
            ss_tot = np.sum((areas - np.mean(areas)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            equation = f"y = {coeffs[0]:.4f}x² + {coeffs[1]:.4f}x + {coeffs[2]:.4f}"

        else:
            raise ValueError(f"Unknown method: {method}")

        # Create curve object
        curve = CalibrationCurve(
            standards=standards,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            equation=equation,
            method=method
        )

        # Store curve
        self.curves[curve_name] = curve

        return curve

    def calculate_concentration(
        self,
        area: float,
        curve_name: str = "default",
        dilution_factor: float = 1.0
    ) -> float:
        """
        Calculate concentration from peak area

        Args:
            area: Peak area
            curve_name: Name of calibration curve to use
            dilution_factor: Dilution factor to apply

        Returns:
            Calculated concentration
        """
        if curve_name not in self.curves:
            raise ValueError(f"Curve '{curve_name}' not found")

        curve = self.curves[curve_name]

        if curve.method == "linear":
            # Solve: area = slope * conc + intercept
            concentration = (area - curve.intercept) / curve.slope

        elif curve.method == "quadratic":
            # Solve quadratic equation
            # area = a*conc² + b*conc + c
            # Need to extract coefficients
            raise NotImplementedError("Quadratic concentration calculation not yet implemented")

        else:
            raise ValueError(f"Unknown method: {curve.method}")

        # Apply dilution factor
        concentration *= dilution_factor

        return max(0, concentration)  # Ensure non-negative

    def calculate_batch_concentrations(
        self,
        areas: List[float],
        curve_name: str = "default",
        dilution_factors: Optional[List[float]] = None,
        sample_names: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Calculate concentrations for multiple samples

        Args:
            areas: List of peak areas
            curve_name: Name of calibration curve
            dilution_factors: List of dilution factors (default 1.0)
            sample_names: List of sample names

        Returns:
            List of result dictionaries
        """
        if dilution_factors is None:
            dilution_factors = [1.0] * len(areas)

        if sample_names is None:
            sample_names = [f"Sample_{i+1}" for i in range(len(areas))]

        if len(areas) != len(dilution_factors) != len(sample_names):
            raise ValueError("All input lists must have same length")

        results = []
        for area, dilution, name in zip(areas, dilution_factors, sample_names):
            concentration = self.calculate_concentration(area, curve_name, dilution)

            results.append({
                'sample_name': name,
                'area': area,
                'dilution_factor': dilution,
                'concentration': concentration
            })

        return results

    def get_curve_statistics(self, curve_name: str = "default") -> Dict:
        """
        Get statistics for calibration curve

        Args:
            curve_name: Name of calibration curve

        Returns:
            Dictionary with curve statistics
        """
        if curve_name not in self.curves:
            raise ValueError(f"Curve '{curve_name}' not found")

        curve = self.curves[curve_name]

        stats_dict = {
            'equation': curve.equation,
            'slope': curve.slope,
            'intercept': curve.intercept,
            'r_squared': curve.r_squared,
            'method': curve.method,
            'num_standards': len(curve.standards),
            'concentration_range': (
                min(s.concentration for s in curve.standards),
                max(s.concentration for s in curve.standards)
            ),
            'area_range': (
                min(s.area for s in curve.standards),
                max(s.area for s in curve.standards)
            )
        }

        return stats_dict

    def save_curve(self, curve_name: str, filename: str):
        """
        Save calibration curve to JSON file

        Args:
            curve_name: Name of curve to save
            filename: Output filename
        """
        if curve_name not in self.curves:
            raise ValueError(f"Curve '{curve_name}' not found")

        curve = self.curves[curve_name]

        data = {
            'curve_name': curve_name,
            'method': curve.method,
            'slope': curve.slope,
            'intercept': curve.intercept,
            'r_squared': curve.r_squared,
            'equation': curve.equation,
            'standards': [
                {
                    'concentration': s.concentration,
                    'area': s.area,
                    'height': s.height,
                    'name': s.name
                }
                for s in curve.standards
            ]
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def load_curve(self, filename: str) -> str:
        """
        Load calibration curve from JSON file

        Args:
            filename: Input filename

        Returns:
            Name of loaded curve
        """
        with open(filename, 'r') as f:
            data = json.load(f)

        # Reconstruct standards
        standards = [
            StandardPoint(
                concentration=s['concentration'],
                area=s['area'],
                height=s.get('height'),
                name=s.get('name')
            )
            for s in data['standards']
        ]

        # Create curve object
        curve = CalibrationCurve(
            standards=standards,
            slope=data['slope'],
            intercept=data['intercept'],
            r_squared=data['r_squared'],
            equation=data['equation'],
            method=data['method']
        )

        curve_name = data['curve_name']
        self.curves[curve_name] = curve

        return curve_name

    def validate_curve(
        self,
        curve_name: str = "default",
        min_r_squared: float = 0.98
    ) -> Tuple[bool, str]:
        """
        Validate calibration curve quality

        Args:
            curve_name: Name of curve to validate
            min_r_squared: Minimum acceptable R²

        Returns:
            Tuple of (is_valid, message)
        """
        if curve_name not in self.curves:
            return False, f"Curve '{curve_name}' not found"

        curve = self.curves[curve_name]

        # Check R²
        if curve.r_squared < min_r_squared:
            return False, f"R² ({curve.r_squared:.4f}) below minimum ({min_r_squared})"

        # Check number of standards
        if len(curve.standards) < 3:
            return False, f"Only {len(curve.standards)} standards (recommend ≥3)"

        # Check for negative slope (area should increase with concentration)
        if curve.slope <= 0:
            return False, f"Negative or zero slope ({curve.slope:.4f})"

        return True, "Curve validation passed"

    def get_lod_loq(
        self,
        curve_name: str = "default",
        std_dev_blank: float = None,
        confidence: float = 3.3  # 3.3 for LOD, 10 for LOQ
    ) -> float:
        """
        Calculate Limit of Detection (LOD) or Limit of Quantification (LOQ)

        Args:
            curve_name: Name of calibration curve
            std_dev_blank: Standard deviation of blank measurements
            confidence: Confidence factor (3.3 for LOD, 10 for LOQ)

        Returns:
            LOD or LOQ value
        """
        if curve_name not in self.curves:
            raise ValueError(f"Curve '{curve_name}' not found")

        curve = self.curves[curve_name]

        if std_dev_blank is None:
            # Estimate from curve intercept (approximate)
            std_dev_blank = abs(curve.intercept) / 3.0

        # LOD/LOQ = (confidence * std_dev) / slope
        limit = (confidence * std_dev_blank) / curve.slope

        return max(0, limit)
