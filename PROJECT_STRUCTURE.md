# PROJECT_STRUCTURE — PeakPicker

HPLC chromatogram peak picking and quantification for Agilent ChemStation
`.D` folders: baseline correction, peak detection and deconvolution,
calibration-curve quantification, QC, and Excel/plot export.

This is a **public repository**. Experiment-specific code and data are kept in
a private overlay and plugged in at run time — see [docs/PLUGINS.md](docs/PLUGINS.md).

## Top-level layout

| Path | Description |
|---|---|
| `src/` | Library. `src/peakpicker/` is the main package (application, baseline, config, domain, infrastructure, peak_analysis, quant); `plugins.py` loads private plugins. Legacy single-file modules (`chemstation_parser.py`, `peak_integrator.py`, …) sit beside it. |
| `scripts/` | Generic entry points (batch analysis, direct analysis, peak quantification). |
| `methods/` | Method YAML files; only the synthetic `example_hpx87h.yaml` is public. |
| `examples/` | Minimal usage example (`baseline_example.py`). |
| `docs/` | Usage, workflow, timing and output-organization guides; plugin mechanism. |
| `tests/` | Pytest suite. `tests/lab/` (private, gitignored) holds tests that need real lab data. |

## Not in this repository (private overlay, gitignored)

`analyses/`, real `methods/*.yaml` and `methods/standards/`, `plugins/`,
`tests/lab/`, `archive/`, repo-specific agent instructions.
