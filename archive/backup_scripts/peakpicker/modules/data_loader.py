"""
Data loading module for chromatography data
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import sys
import os

# Add parent directory to path to import chemstation_parser
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class DataLoader:
    """Load chromatography data from various file formats"""

    SUPPORTED_FORMATS = ['.csv', '.txt', '.xlsx', '.xls', '.ch']

    def __init__(self):
        self.time = None
        self.intensity = None
        self.file_path = None
        self.file_format = None

    def load_file(self, file_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load chromatography data from file

        Args:
            file_path: Path to data file

        Returns:
            Tuple of (time, intensity) numpy arrays
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self.file_path = file_path
        self.file_format = file_path.suffix.lower()

        if self.file_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format: {self.file_format}. "
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        # Load based on file format
        if self.file_format == '.ch':
            self.time, self.intensity = self._load_chemstation(file_path)
        elif self.file_format in ['.xlsx', '.xls']:
            self.time, self.intensity = self._load_excel(file_path)
        else:  # .csv, .txt
            self.time, self.intensity = self._load_csv(file_path)

        # Validate data
        self._validate_data()

        return self.time, self.intensity

    def _load_csv(self, file_path: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Load data from CSV or TXT file"""
        try:
            # Try reading with pandas (handles various delimiters)
            df = pd.read_csv(file_path)

            # Check for common column names
            time_col = None
            intensity_col = None

            for col in df.columns:
                col_lower = str(col).lower()
                if 'time' in col_lower or 'rt' in col_lower or 'retention' in col_lower:
                    time_col = col
                elif 'intensity' in col_lower or 'signal' in col_lower or 'absorbance' in col_lower:
                    intensity_col = col

            # If columns not found, use first two columns
            if time_col is None:
                time_col = df.columns[0]
            if intensity_col is None:
                intensity_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

            time = df[time_col].values
            intensity = df[intensity_col].values

            return time, intensity

        except Exception as e:
            # Fallback: try reading as space-delimited or tab-delimited
            data = np.loadtxt(file_path, delimiter=None)
            if data.ndim == 1:
                # Single column, create time index
                time = np.arange(len(data))
                intensity = data
            else:
                time = data[:, 0]
                intensity = data[:, 1]

            return time, intensity

    def _load_excel(self, file_path: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Load data from Excel file"""
        df = pd.read_excel(file_path)

        # Check for common column names (same logic as CSV)
        time_col = None
        intensity_col = None

        for col in df.columns:
            col_lower = str(col).lower()
            if 'time' in col_lower or 'rt' in col_lower:
                time_col = col
            elif 'intensity' in col_lower or 'signal' in col_lower:
                intensity_col = col

        if time_col is None:
            time_col = df.columns[0]
        if intensity_col is None:
            intensity_col = df.columns[1]

        time = df[time_col].values
        intensity = df[intensity_col].values

        return time, intensity

    def _load_chemstation(self, file_path: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Load data from Agilent ChemStation .ch file"""
        try:
            from chemstation_parser import read_chemstation_file
            time, intensity = read_chemstation_file(str(file_path))
            return time, intensity
        except ImportError:
            raise ImportError(
                "ChemStation parser not available. "
                "Make sure chemstation_parser.py is in the project root."
            )

    def _validate_data(self):
        """Validate loaded data"""
        if self.time is None or self.intensity is None:
            raise ValueError("Failed to load data")

        if len(self.time) == 0 or len(self.intensity) == 0:
            raise ValueError("Loaded data is empty")

        if len(self.time) != len(self.intensity):
            raise ValueError(
                f"Time and intensity arrays have different lengths: "
                f"{len(self.time)} vs {len(self.intensity)}"
            )

        # Check for NaN values
        if np.any(np.isnan(self.time)) or np.any(np.isnan(self.intensity)):
            raise ValueError("Data contains NaN values")

    def get_data_info(self) -> dict:
        """Get information about loaded data"""
        if self.time is None or self.intensity is None:
            return {}

        return {
            'file_path': str(self.file_path),
            'file_format': self.file_format,
            'data_points': len(self.time),
            'time_range': (float(np.min(self.time)), float(np.max(self.time))),
            'intensity_range': (float(np.min(self.intensity)), float(np.max(self.intensity))),
            'intensity_mean': float(np.mean(self.intensity)),
            'intensity_std': float(np.std(self.intensity)),
        }
