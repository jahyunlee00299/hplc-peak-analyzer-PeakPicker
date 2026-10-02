# Feature connectivity ledger

One entry per delivered unit: scope, layer, inputs/outputs, evidence, refutation, deferred risk.

## 2026-09-29 - ChemStation folder layout checker (`chem_layout_qc`)

- **Scope / layer**: read-only validator and its SSOT spec (`chem_layout_spec.yaml`); sub-feature of the sequence-QC family
  (cross-cutting data-integrity gate that runs after any copy/rename of chromatography data).
- **Inputs**: a folder handed to ChemStation (`check`), optional sample map CSV and provenance folder (sample identity, md5), or
  a raw data root (`tree`). Spec resolution: explicit path, `$CHEM_LAYOUT_SPEC`, private overlay `methods/chem_layout_spec.lab.yaml`,
  packaged default.
- **Outputs**: text report, optional JSON (`--json`, written wherever the caller points), exit code 0 / 1 / 2. Never writes next to the data.
- **Evidence (prove)**: 44 unit tests on synthetic `.D` fixtures; a real-data build in the private overlay reproduced the observed
  ChemStation problem (a folder with sequence files and a stray csv flagged, a single aborted run flagged, names / sample identity /
  provenance md5 clean) and a raw-tree scan of a large archive.
- **Refutation**: mutation check (17 deliberate breakages of the implementation, each killed by the tests after one test was added for
  spec status validation); adverse fixtures (sequence files, stray/hidden files, a file named like a run, lower-case `.d`, empty folder,
  runs one level down, missing/truncated signal, aborted run alone in a folder, vial-reuse header mismatch, missing map rows, flipped byte in a
  copy, malformed/unknown spec, read-only guarantee by md5 snapshot). Known limitation, tested and documented: a single run with an
  unknown method cannot be judged complete without a declared runtime.
- **Regress**: neighbouring `test_sequence_qc.py` (20 tests) unchanged and green.
- **Connect**: `sequence_qc.py` docstring and `PROJECT_STRUCTURE.md` reference the checker; private overlay spec holds the lab names.
- **Deferred**: rule L9 (header sample name equals readable label) stays `pending_evidence` until it is established what the
  ChemStation navigation table displays; wiring the call into the organizing recipe and registering the spec with `fiducial pointers`.

## 2026-10-02 - Refactor batch 1 (branch `peakpicker/fix/refactor-batch1-261002`)

### Unit A - personal absolute path out of `.fiducial.toml`

- **Scope / layer**: repo config hygiene (public repo); fiducial `pointers` rule input.
- **Inputs / outputs**: `.fiducial.toml` `pointers_paths` now repo-relative (`methods/standards/hpx87h_response_factors.index.yaml`);
  owner override = git-ignored `.fiducial.local.toml` (whole-file copy, absolute path) selected with `fiducial --config`.
  fiducial 0.1.0 has no env-var, include or merge mechanism (checked `fiducial/config.py`), so no unsupported key was invented.
- **Evidence**: override file with the OneDrive master -> `pointers clean, 22 pointers all resolve`; `git status` ignores the local file.
- **Refutation**: committed default run where the index is only a stub -> `pointers CANNOT CHECK` (reported as BLIND, never a false pass).
- **Deferred risk**: the old absolute path stays in git history (not rewritten, by instruction). The default config cannot verify pointers
  on a fresh clone (by design, the SSOT is private).

### Unit B - dependency SSOT

- **Scope / layer**: packaging. `pyproject.toml` is the SSOT; `requirements.txt` is `-e .`; README install section updated.
- **Evidence**: `git grep` for `import|from (pyautogui|keyboard|PIL)` = 0 hits; `pyyaml` was already in pyproject (5 `import yaml` sites);
  `pip install --dry-run -r requirements.txt` resolves `hplc-peakpicker`; `scripts/batch_analyze_all.py --help` runs from another cwd after
  removing the wrong `sys.path` line 29 (line 30 is the correct `parents[1]/'src'`).
- **Refutation**: module imported from a different cwd (`plot_utils` OK). `plot_utils.py:10` is a docstring usage example, not import-time
  code, so nothing was removed there.
- **Deferred risk**: same wrong `Path(__file__).parent / 'src'` insert in `scripts/hplc_analyzer_enhanced.py:17` and `scripts/quantify_peaks.py:12`;
  `docs/PROJECT_STRUCTURE.md` still mentions pyautogui.

### Unit C - tests sys.path unification

- **Scope / layer**: test infrastructure. `pytest.ini` `pythonpath = src` replaces 10 per-file `sys.path.insert` blocks (plus newly unused imports).
- **Evidence**: before 142 collected with 1 collection error (`test_data_root.py`, no path insert) and 141 passed / 1 skipped;
  after 146 collected, 145 passed / 1 skipped, 0 errors. The 4 extra tests are `test_data_root.py` now collecting; all other results identical.
- **Refutation**: `-o pythonpath=` reproduces the collection error, proving the ini key is what supplies the path; run from another cwd
  with `-c/--rootdir` passes.
- **Deferred risk**: `test_chem_layout_qc.py` and `test_sequence_qc.py` still load by file path on purpose (documented in those files).

### Unit D - golden tests for legacy numerics

- **Scope / layer**: `tests/test_golden_numerics.py` (39 tests: 29 pass, 10 strict xfail). `pytest.ini` also gets `.` on pythonpath because
  `src/peak_integrator.py` does `from src.peakpicker...`.
- **Inputs / outputs**: synthetic Gaussian / EMG (scipy `exponnorm` as independent truth) peaks on known linear/curved baselines, seeded noise;
  asserts against analytic area `A*sigma*sqrt(2*pi)`, RT, component count.
- **Evidence**: robust_fit and `optimize_baseline_with_linear_peaks` (the production path) recover areas within 1-5 %; Gaussian deconvolution
  (single, resolved pair, shoulder pair) and `peak_integrator` (full, half modes, unit x60, neighbours, error paths) within 1-5 %.
- **Refutation**: `test_area_check_rejects_biased_baseline` (a lifted baseline must fail the criterion); strict xfails flip to failure when fixed.
- **Findings (xfail, not loosened)**: (1) `peak_models.exponentially_modified_gaussian` erf argument has the wrong sign; (2) `_fit_n_emg` therefore
  fails on clean EMG peaks; (3) `deconvolve_peak` stops at R2 > 0.95 so overlapped pairs stay one component; (4) default `weighted_spline` and
  `adaptive_connect` baselines are lifted under peaks by flank anchors (single flat-baseline peak: area 64 %); (5) `find_peak_boundaries`
  cutoff is not baseline-subtracted, boundaries fall to the window edge on offset baselines.
- **Deferred risk**: the findings are not fixed here; fixing each one should remove its xfail marker.

### Unit E - zero-import module triage (no deletions)

- **Evidence**: `git grep -w` on the tracked tree, the private overlay in the main checkout (`analyses/ plugins/ tests/lab/ scripts/ archive/`),
  and docs. `PeakPicker-analyses` does not exist as a separate directory (the overlay lives in the main checkout, tracked by `.git-analyses`).

| Module | Tracked refs | Private-overlay refs | Recommendation |
|---|---|---|---|
| `result_exporter.py` (339 lines) | docs only (stale) | `archive/` copies only | move-to-legacy; package equivalent is `peakpicker/result_writer.py`; fix 2 docs |
| `lc_quant_agent.py` (7-line shim) | none | `scripts/run_all.py` (`from src.lc_quant_agent`) | keep until `run_all.py` imports `peakpicker.agent` |
| `sample_metadata.py` | none | `compare_260212_vs_260225.py`, `requantify_halfpeak.py` | keep; candidate to move into `peakpicker.infrastructure` |
| `peak_integrator.py` | none | `tests/lab/test_peak_integrator.py` | keep (now has golden tests); fix the `src.` import prefix later |
| `deconvolution_visualizer.py` (428 lines) | none | none | delete (or legacy); demo-only, git history preserves it |
| `improved_baseline.py` (659 lines) | `examples/baseline_example.py`, `docs/BASELINE_IMPROVEMENTS.md` | none | keep while the example and doc exist, else legacy |

- `hybrid_baseline.test_hybrid_baseline` (line 816) is a plotting demo, not a test: it reads `peakpicker/examples/EXPORT.CSV` (path does not exist),
  has no assertions and is never collected (`testpaths = tests`). Listed, not moved.
- **Deferred risk**: nothing was deleted or moved; the table is a proposal for the owner's decision.

## Refactor batch 2 (2026-10-02) - numerical fixes for the batch-1 xfails

Branch `peakpicker/fix/numerics-batch2-261002`. Suite: 174 passed / 1 skipped / 10 xfailed -> 240 passed / 1 skipped / 0 xfailed.
Every strict xfail was removed only because it XPASSed; no tolerance was loosened.

### Unit F - EMG model and `_fit_n_emg` (bugs 1 and 2)

- **Change**: `peak_models.exponentially_modified_gaussian` now uses the standard EMG (erfc, correct sign), written overflow-free with `erfcx`,
  Gaussian-equivalent amplitude (area = amp*sigma*sqrt(2 pi), unchanged convention), tau < 0 = mirrored fronting peak. `_fit_n_emg` bounds widened
  (amp x2 -> x5, tau 3 sigma -> max(15 sigma, 5 % of window)) and the initial guess clipped into them.
- **Evidence**: matches `scipy.stats.exponnorm` to 1e-6 (shape) and 2e-3 (area) up to tau/sigma = 20. Tailing peaks (tau/sigma 1.5-5): area error
  -5..-7 % (Gaussian fallback) -> < 1 %.
- **Refutation**: tau = 1e-9..1e-3 finite and -> Gaussian; negative tau mirror; pure Gaussian fed to `_fit_n_emg` keeps Gaussian area/centre;
  strongly tailing peak test fails on the old bounds (-4 % area).
- **Connect**: used by `peak_deconvolution` only (EMG + `multi_emg`); `scripts/hplc_analyzer_enhanced.py` reaches it through `PeakDeconvolution`.

### Unit G - `find_peak_boundaries` (bug 5)

- **Change**: cutoff and valley half-height are measured above the local baseline (mean of the lowest 10 % of the search window).
- **Behaviour change**: with an offset baseline the boundaries no longer run to the window edge, so `integrate_peak` is offset-invariant and carries
  the 0.3 % cutoff truncation bias (-0.77 % on a noise-free Gaussian) that the zero-baseline case always had. Real Chemstation D-Xylose file
  (`tests/lab/test_peak_integrator.py`, overlay): Chemstation difference -0.89 % -> -1.49 %. Recalibrate or lower `threshold_ratio` if a calibration was
  built on the old integrator output.
- **Refutation**: negative / zero / +100 / +5000 baselines give identical bounds and area; offset baseline + neighbour 0.9 min away stops at the valley.

### Unit H - `deconvolve_peak` component count (bug 3)

- **Change**: component count and Gaussian-vs-EMG are chosen by BIC (delta > 10 to add a component or a tail), not by R2 > 0.95. Seeds: detected
  maxima and area quantiles. Resolution guard: components < 10 % of the largest or closer than 1.5 mean sigma are rejected (unidentifiable).
- **Evidence**: 2.15-sigma pair -> 2 components, areas within 2 % of analytic over 4 seeds.
- **Refutation**: single Gaussian (noise sd 0 / 1 / 4), tailing EMG (tau/sigma 1.6 and 5) x 6 seeds each: always 1 component, area within 5 %.
- **Deferred risk**: pairs closer than ~1.5 sigma stay one component by design; runtime of `deconvolve_peak` rose (up to 4 fits x 2 seed sets).

### Unit I - weighted_spline / adaptive_connect flank anchors (bug 4)

- **Change**: `HybridBaselineCorrector._baseline_anchor_mask` drops anchors > 3 robust sigma above the median of their 7 nearest anchors; applied to
  `weighted_spline` and `adaptive_connect` only. `robust_fit` and the anchor finder are untouched.
- **Evidence**: flat baseline + single peak area recovery 64 % -> 100.7 % (weighted_spline), 56 % -> 100.3 % (adaptive_connect); 3-peak drifting/curved
  baseline recovery within 8 % for all three methods.
- **Refutation**: peak-free drift/curvature keeps every anchor; the flank anchor (511) is rejected while flat-baseline anchors (< 105) stay.
- **Deferred risk**: the filter is not applied to the package strategy `src/peakpicker/baseline/strategies/weighted_spline.py` (not audited here).
  Pre-existing and unchanged: on a peak-free steep drift the anchor finder's own low-value outlier rule costs up to ~26 units at the record ends.

### Unit J - cleanup

- `scripts/hplc_analyzer_enhanced.py`, `scripts/quantify_peaks.py`: the `Path(__file__).parent / 'src'` insert pointed at `scripts/src`; both scripts failed
  with `ModuleNotFoundError` from any cwd but `src/`. Replaced by repo root + `src` from `__file__`; verified `--help` / import from another cwd.
- Deleted: `docs/PROJECT_STRUCTURE.md` (stale, unlinked; root `PROJECT_STRUCTURE.md` stays), `src/deconvolution_visualizer.py` (0 references incl. overlay),
  `src/result_exporter.py` (0 importers; `docs/USAGE_EXAMPLES.md` now names `peakpicker/result_writer.py`). Left: pyautogui text in `docs/TIMING_OPTIMIZATION_GUIDE.md` (historical).

### Unit G follow-up - noise-robust boundaries (2026-10-02, after independent verification)

- **Defect found**: a77141c made the cutoff baseline-relative, which exposed a pre-existing flaw: the valley test (`cur > prev and prev < half`) was unsmoothed and
  had no noise margin, so the scan locked on the first noise up-tick (SNR 20/50/100 areas -65/-59/-37 % median; the same flaw existed at offset 0 on main).
- **Fix**: scans run on a Savitzky-Golay smoothed copy (window <= FWHM/3 points, 5-15) with noise sigma from the MAD of first differences; the cutoff is
  `max(threshold_ratio * height, 3 sigma_s)` above the baseline; a valley needs a rebound > 3 sigma_s above the running minimum; valley-line anchors are 7-point means.
  Integration still uses the raw signal.
- **Result** (median / worst of 10 seeds, area error, offset 0 and 100 identical): SNR 20 -4.9/-7.1 %, 50 -2.5/-3.5 %, 100 -1.8/-2.5 %, 1000 -0.7/-0.8 %
  (a77141c: -65/-70, -59/-66, -37/-46, -2.1/-3.1 %). Residual error = the documented cutoff truncation bias plus noise; tests assert a bound derived from both.
- **Lab file** (D-Xylose, Chemstation reference): -0.89 % (main) -> -1.49 % (a77141c) -> -1.53 %; L+R / full ratio 1.0001.
- `DeconvolvedPeak.apex_time` added (backward compatible); EMG `retention_time` is mu, not the apex (documented).
