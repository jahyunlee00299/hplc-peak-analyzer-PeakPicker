# PROJECT_STRUCTURE — PeakPicker

> Auto-generated structure map. Last updated: 2026-06-12

## Purpose

Chromatography peak detection, deconvolution, and quantification tool for Agilent Chemstation
HPLC data. Reads `.ch` files (format 130/131) and `.D` folder structures, applies baseline
correction (ArPLS / weighted spline / hybrid valley-based), detects and deconvolves peaks
(Gaussian and EMG models via `lmfit`), builds calibration curves, and exports Excel reports and
publication-quality plots.

## Top-Level Layout

| Path | Description |
|---|---|
| `src/` | Main package root (clean architecture) |
| `src/peakpicker/` | Core library: application, baseline, config, domain, infrastructure, peak_analysis, quant sub-packages |
| `src/solid/` | Alternative quantification module (legacy parallel path) |
| `analyses/` | Per-experiment analysis scripts and batch outputs (e.g., Xul-5P/AcP, ATP titration, timecourse) |
| `scripts/` | Standalone run/batch/plot scripts |
| `tests/` | Pytest test suite |
| `examples/` | Example usage scripts |
| `methods/` | Method configuration files |
| `results/` | Output reports and plots from analysis runs |
| `docs/` | Documentation |
| `archive/` | Deprecated scripts (never delete) |
| `requirements.txt` | Python dependency list |
| `CLAUDE.md` | Claude Code project config (machine-path rules) |
| `.claude/` | Claude Code project-level settings |
| `_tmp_check_e2r3.py` | One-off diagnostic script (root-level, WIP) |
| `_tmp_vial_order.py` | One-off vial ordering helper (root-level, WIP) |

### `src/peakpicker/` internal packages

| Sub-package | Role |
|---|---|
| `application/` | Workflows and batch processing orchestration |
| `baseline/` | Baseline correction strategies (ArPLS, spline, hybrid) |
| `config/` | Configuration dataclasses |
| `domain/` | Domain models and enums |
| `infrastructure/` | File I/O (Chemstation reader, Rainbow API), exporters, signal processing |
| `peak_analysis/` | Two-pass peak detection and EMG/Gaussian deconvolution |
| `quant/` | Calibration curves, quantification, statistical analysis |

## Key Entry Points

| Script | Description |
|---|---|
| `analyses/run_all.py` | Batch analysis runner for all experiments |
| `analyses/run_analysis.bat` | Windows batch wrapper for `run_all.py` |
| `analyses/quantify_peaks.py` | Single-file quantification entry point |
| `analyses/batch_analyze_all.py` | Batch quantification across all `.D` folders |
| `analyses/run_hplc_agent.py` | HPLC agent-driven analysis pipeline |

## Environment

- Conda env: `PeakPicker` (dedicated environment, separate from KineticModeling)
- Python: ≥ 3.8 (inferred from dependency versions)
- Key dependencies: `numpy`, `pandas`, `scipy`, `matplotlib`, `openpyxl`, `lmfit`, `pybaselines`, `rainbow-api`, `pillow`

## Data & Outputs

- Input data: Agilent Chemstation `.ch` files and `.D` folders (external, not tracked in repo)
- Calibration and quantification outputs: `results/` and `analyses/result/`
- Batch outputs: `analyses/batch_output/`, `analyses/260324_agent_output/`
- Raw data references: `analyses/*.xlsx` (pre-processed summary sheets)
- Always use `Path.home()` for user-specific paths; do not hardcode usernames

## Current Git State

- Branch: `refactor/chem32-path-config`
- Latest commit: `1a75568 2026-06-04 18:16:35 +0900 refactor: remove hardcoded CHEM32 data paths (#11)`
