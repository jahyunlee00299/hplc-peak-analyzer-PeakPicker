# PeakPicker

Chromatography peak detection, deconvolution, and quantification tool for Agilent Chemstation data.

## Features

- **File reading**: Agilent Chemstation `.ch` files (format 130/131), `.D` folder scanning, Rainbow API support
- **Baseline correction**: ArPLS, weighted spline, hybrid valley-based strategies with quality evaluation
- **Peak detection**: Two-pass detection with configurable parameters
- **Peak deconvolution**: Gaussian and EMG (Exponentially Modified Gaussian) fitting via `lmfit`
- **Quantification**: Calibration curves, sample parsing, statistical analysis, batch processing
- **Export**: Excel reports and publication-quality plots

## Installation

```bash
conda activate PeakPicker
pip install -r requirements.txt
```

## Project Structure

```
src/
  peakpicker/          # Main package (clean architecture)
    application/       # Workflows and batch processing
    baseline/          # Baseline correction strategies
    config/            # Configuration dataclasses
    domain/            # Domain models and enums
    infrastructure/    # File I/O, exporters, signal processing
    peak_analysis/     # Peak detection and deconvolution
    quant/             # Quantification methods
  solid/               # Alternative quantification module
```

## Dependencies

numpy, pandas, scipy, matplotlib, openpyxl, lmfit, pybaselines, rainbow-api
