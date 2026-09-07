# PROJECT_STRUCTURE — PeakPicker (hplc-peak-analyzer-PeakPicker)

> Auto-generated structure map (written by TRACK A repo audit, 2026-08-21;
> branch section refreshed 2026-09-07 after single-branch consolidation).
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
| `methods/` | YAML method definitions per HPLC column/analyte (ChiralPak IA5 sugars, deoxynucleoside, D-Gal/D-Tagatose, HPX-87P Gal/Tag/galactitol, L-Rib, Xyl5P, generic HPX87H) |
| `examples/` | Minimal usage example (`baseline_example.py`) |
| `docs/` | Usage/workflow/timing/output-organization guides, `QUANTITATION_RULES.md` (area convention, calibration YAML schema, peak-assignment/tuning rules — read first for any HPLC quantitation work), + Korean `PROJECT_STRUCTURE.md` |
| `tests/` | Pytest suite (peak integrator, half-peak handling, sequence QC, SOLID refactor) |
| `archive/` | Superseded scripts kept for reference (`archive/backup_scripts/`) |
| `.idea/` | PyCharm project metadata (should generally stay untracked/gitignored) |
| `.claude/settings.local.json` | Local Claude Code permission overrides |

## Audit notes (260821)

- Public-repo leak scan (grep for real names/emails/`C:\Users\Jahyun`/secrets/tokens)
  found no leak markers at HEAD — see `REPORT_repos.md` for the full grep methodology
  and false-positive filtering.

## Branch state (260907 consolidation)

- `main` is the sole working branch. It holds all quantitation/tuning work that had
  previously lived on `peakpicker/feature/hpx87p-quant-260827` (merged, then the local
  and remote copies of that branch were deleted — see `git log` for the merge commit).
- `security/pii-scrub-main-260807` is retained (local branch + worktree at
  `~/scratch/worktrees/pii-scrub-260807`) even though it is already fully merged into
  `main` — it is tied to an open history-rewrite TODO expecting this branch to still
  exist for a future `filter-repo` pass. Do not delete it without resolving that TODO.
- Two remote branches carry unmerged, unreviewed work and were intentionally left
  untouched by this consolidation (out of scope — no local tracking branch existed for
  either before or after): `origin/peakpicker/fix/cottonii-go-requant-260903` (3 commits
  ahead of `main`) and `origin/peakpicker/fix/track-260810-sp0810-quant-260906`
  (2 commits ahead of `main`).
