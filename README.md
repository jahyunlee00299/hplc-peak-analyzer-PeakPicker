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
pip install hplc-peakpicker        # from PyPI
pip install -U hplc-peakpicker     # upgrade to the latest release
```

From a clone (development):

```bash
conda activate PeakPicker
pip install -r requirements.txt
```

### Update notice

Building a workflow checks PyPI at most once a day (1.5 s timeout, silent when
offline) and prints a one-line upgrade hint to stderr when a newer release
exists. Ask explicitly with `peakpicker.check_for_update()`; turn the check off
with `PEAKPICKER_NO_UPDATE_CHECK=1` (it is also skipped under CI and pytest).

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
    quant/             # Quantification methods (public API: QuantMethod, StandardCurve)
```

## Lab-specific code: plugins

The library is generic. Sample-name conventions, quantification presets and
method-selection rules for a particular lab live outside this repository as
plugins and method YAMLs — see [docs/PLUGINS.md](docs/PLUGINS.md).

## Related

- [sci-toolkit](https://github.com/jahyunlee00299/sci-toolkit) — the lab's research
  skill bundle. Its `scripts/hplc_parser.py` is a stdlib-only port of this
  project's peak detection for quick trace reads; its `lab-data-analysis` skill
  routes full quantification here.

## Dependencies

numpy, pandas, scipy, matplotlib, openpyxl, lmfit, pybaselines, rainbow-api
