# PROJECT_STRUCTURE — PeakPicker (hplc-peak-analyzer-PeakPicker)

> Auto-generated structure map (written by TRACK A repo audit, 2026-08-21).
> Note: a Korean-language structure doc already exists at `docs/PROJECT_STRUCTURE.md`;
> this file is the English root-level version the audit workorder requires.
> **Public GitHub repo** (`jahyunlee00299/hplc-peak-analyzer-PeakPicker`) — treat
> every commit here as publicly visible.

## Purpose

HPLC chromatogram peak-picking and quantification toolkit for enzyme cascade
reaction samples (Agilent ChemStation `.D` folders). Covers baseline correction,
peak deconvolution/integration, per-method calibration (xylulose-5-phosphate,
D-galactose/D-tagatose, deoxynucleosides, L-ribose, generic sugars), mass-balance
cross-checks, and result export to Excel.

## Top-Level Layout

| Path | Description |
|---|---|
| `CLAUDE.md` | Repo-specific Claude Code instructions |
| `README.md` | Project overview |
| `pytest.ini` / `requirements.txt` | Test config and Python dependencies |
| `src/` | Core library: `chemstation_parser.py`, baseline correction (`hybrid_baseline.py`, `improved_baseline.py`), `peak_deconvolution.py`, `peak_integrator.py`, `peak_models.py`, `result_exporter.py`, `sample_metadata.py`, `lc_quant_agent.py`; `src/peakpicker/` package (incl. `sample_parser.py`); `src/solid/` (SOLID-refactored components) |
| `scripts/` | Batch/one-off analysis run scripts and the HPLC quant agent entry points (`run_hplc_agent.py`, `run_all.py`, per-date quantification/comparison scripts) |
| `analyses/` | Per-experiment analysis notebooks-as-scripts (cofactor, RPM-buffer, Xul5P/AcP series) |
| `methods/` | YAML method definitions per HPLC column/analyte (ChiralPak IA5 sugars, deoxynucleoside, D-Gal/D-Tagatose, L-Rib, Xyl5P, generic HPX87H) |
| `examples/` | Minimal usage example (`baseline_example.py`) |
| `docs/` | Usage/workflow/timing/output-organization guides + Korean `PROJECT_STRUCTURE.md` |
| `tests/` | Pytest suite (peak integrator, half-peak handling, sequence QC, SOLID refactor) |
| `archive/` | Superseded scripts kept for reference (`archive/backup_scripts/`) |
| `.idea/` | PyCharm project metadata (should generally stay untracked/gitignored) |
| `.claude/settings.local.json` | Local Claude Code permission overrides |

## Audit notes (260821)

- Public-repo leak scan (grep for real names/emails/`C:\Users\Jahyun`/secrets/tokens)
  found no leak markers at HEAD — see `REPORT_repos.md` for the full grep methodology
  and false-positive filtering.
