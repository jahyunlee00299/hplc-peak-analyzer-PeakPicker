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

## Refactor batch 3 (2026-10-02)

### Unit 1 - package weighted_spline / adaptive_connect flank anchors (opt-in, follow-up after independent verification)

- **Defect**: the batch-2 flank-anchor fix (Unit I) was applied to the legacy `hybrid_baseline` only. `WeightedSplineStrategy` and `AdaptiveConnectStrategy`
  in `src/peakpicker/baseline/strategies/weighted_spline.py` interpolated through every anchor. With the window-minimum composition (`LocalMinAnchorFinder` + `ValleyAnchorFinder` + `BoundaryAnchorFinder`)
  a flat-baseline single peak was recovered at 36.5 % (weighted_spline) / 52 % (adaptive_connect). The production composition (`PeakBoundaryAnchorFinder` + `BoundaryAnchorFinder`,
  `WorkflowBuilder.with_default_baseline`) never anchors inside a peak and was already accurate (100.6-101.4 %).
- **First attempt (b6c403c) was wrong**: the filter was applied to every use of the strategies, so the production composition changed too. Independent verification measured the damage on peak-free curved drift
  (rmse 1.061 -> 7.267, max 6.1 -> 33.1; 16 of 120 no-peak runs changed, 18 of 40 changed cases worse).
- **Fix**: `BaselineStrategyConfig.drop_flank_anchors` (default `False`) gates the shared `baseline/anchor_filters.baseline_anchor_mask`. Off = the exact pre-batch-3 code path. Window-minimum compositions set it to `True`.
  `RobustFitStrategy`, `LinearStrategy` and the anchor finders are untouched.
- **Evidence**: with the flag on, flat single peak within 3 % for 3 seeds x 2 strategies (pre-fix: 12 failures, 35-65 %), close pair (2.7 sigma) within 5 %, tailing EMG within 5 % (`tests/test_package_baseline_flank.py`).
  Production composition bit-identical to a verbatim frozen copy of 9790964 (`tests/frozen_weighted_spline_9790964.py`) over 10 seeds x noise {0.2, 1, 5} x {linear, curved, sinusoidal wander, 6 peaks + drift, broad sigma 1.5,
  low SNR} x 2 strategies = 360 comparisons, `assert_array_equal` (`tests/test_production_baseline_bit_identity.py`); the matrix is sensitive (flag on changes 58 of 180 weighted_spline cases).
- **Refutation / honest residual**: peak-free drift with the flag ON for window-minimum finders, 60 runs per strategy (seeds 0-9 x noise 0.2/1/5 x linear/curved, no seed picked): 5 of 60 baselines change per strategy;
  rmse vs truth moves by -0.054 .. +0.013 (weighted_spline better 4 / worse 1, adaptive_connect better 2 / worse 3), the rest bit-identical. The filter never rejects end anchors or below-baseline dips.

### Unit 2a - EMG / Gaussian dedup (`src/peak_models.py` -> `peakpicker`)

- **Survivor**: `peakpicker/peak_analysis/deconvolution/emg_fitter.exponentially_modified_gaussian` (the batch-2 overflow-free erfcx form, tau < 0 mirror, |tau| < 1e-10 Gaussian) and
  `gaussian_fitter.gaussian`. `emg_fitter.emg` is now a thin guard wrapper (|sigma|, |tau| >= 1e-10) around it. `src/peak_models.py` keeps its public signatures
  (`gaussian`, `exponentially_modified_gaussian`, `multi_gaussian` / `multi_emg` incl. their ValueError validation) and delegates; `lorentzian`, `voigt`, asymmetry helpers stay (no duplicate).
- **Proof** (`tests/test_peak_model_dedup.py`, frozen copies of both old implementations): legacy output bit-identical on a 48-point parameter grid and the tau = 0 / +-1e-12 / tau < 0 branches;
  Gaussians bit-identical; EMG matches scipy `exponnorm` to 1e-6 on the whole grid; `EmgFitter` R2 / area on three noisy tailing peaks unchanged (1e-6 / 1e-4).
- **Measured difference (old package EMG was wrong)**: `emg_fitter.emg` clipped the exponent at +-500 and used a plain `erfc`. Measured with sigma = 0.3 on a 40001-point grid: identical to the new values
  (rel. 2e-13) up to sigma/tau = 25; from sigma/tau ~ 28-30 the tail is wrong (rel. error 1.0 in the region above 1e-6 of the peak at 28, above 1e-3 at 30; area -4.2 % at 30); the peak collapses at sigma/tau >= 33
  (height ratio 0.42 at 33, 0.006 at 35, 0 at 40; e.g. sigma 0.8 / tau 0.02, or EmgFitter's lower bound tau = 1e-6). The new values follow the old ones exactly wherever the clip was inactive (rtol 1e-9).
- **Cost**: `src/peak_models.py` now imports the `peakpicker` package (a leaf module no longer standalone; `src.peak_deconvolution` already did).

### Unit 2b - ChemStation readers: NOT merged (they differ), difference pinned

- **Measured** on two real format-130 lab files: `src/chemstation_parser.ChemstationParser` returns 3472 / 3473 points, bit-identical to the independent `rainbow` decoder (max abs diff 0.0);
  `ChemstationReader` (package) returns 5819 / 5753 points and a different intensity maximum (105190 vs 27302 for the first file) - it reads time at 0x282, scale at 0x127A + offset 0x1282 and decodes
  the body as variable-length byte deltas, none of which matches format 130 (Pascal "130" header, time 0x11A, scale 0x127C, int16-delta segments at 0x1800).
- **Decision**: no shim - a delegating shim would change every number the package reader returns. `tests/test_chemstation_readers_characterization.py` pins: legacy round-trips a synthetic format-130 file exactly
  (incl. the absolute escape), legacy rejects other versions, the package reader's difference is asserted, and a strict xfail marks "package reader recovers format 130" (flips when fixed).
  Optional `PEAKPICKER_REAL_CH` env var compares against rainbow on a real file.
- **Follow-up (independent verification, same day)**: `WorkflowBuilder().build()` without a reader, `create_default_workflow` and the package docstring example routed to the package `ChemstationReader`
  (real file: 5692 points / max 151941 vs rainbow and legacy 3473 / 126086). The default is now `with_auto_reader()`: rainbow (.D and .ch) -> CSV -> new `LegacyParserReader` (wraps `src/chemstation_parser`,
  bit-identical to rainbow on real files). `RainbowReader.can_read` is False when rainbow is not installed, and `AutoReader` falls through to the next compatible reader when one fails (the first error is re-raised if all fail).
  `with_chemstation_reader()` and `ChemstationReader` stay, with a WARNING in their docstrings; the strict xfail keeps documenting the decoder bug. `tests/test_default_reader.py`: default build decodes a synthetic format-130 file
  identically to the legacy parser (rainbow rejects the synthetic file, so the chain falls through), explicit no-rainbow behaviour is the legacy fallback, and `PEAKPICKER_REAL_CH` compares against rainbow on a real file (passes).
  Replacing the package decoder by the legacy one is a behaviour change (bug fix), not a dedup.

### Unit 2c - baseline anchor finding: finders NOT merged, flank mask deduplicated

- **Measured** (3 synthetic chromatograms, 3001 points, noise sd 1; anchors hybrid / improved / package `LocalMin+Valley+Boundary`): flat single peak 60 / 84 / 63, drifting 3-peak 73 / 20 / 84, curved 3-peak 75 / 29 / 87;
  index overlap hybrid-vs-package 59 / 46 / 44 of 60-87, hybrid-vs-improved 45 / 6 / 5. The algorithms differ by design (adaptive percentile and MAD outlier cut in hybrid; smoothing window, `width=1`, cluster minima,
  priority dedup and a negative-value shift in improved; fixed windows over the whole signal and a composite filter in the package), so no shim. `improved_baseline` has no caller besides `examples/` and docs.
  `tests/test_anchor_finders_characterization.py` pins "not identical" and the partial overlap.
- **Deduplicated**: `HybridBaselineCorrector._baseline_anchor_mask` now delegates to `peakpicker.baseline.anchor_filters.baseline_anchor_mask` (the Unit 1 helper, same algorithm). Equal to a frozen copy of the old method
  on 3 fixtures x 3 seeds; the batch-2 golden tests (flank filter, area recovery) pass unchanged.

### Unit 3 - `scripts/quantify_peaks.py`: plotting extracted

- **Change**: `_plot_peak_information`, `create_individual_chromatograms`, `create_overlay_chromatograms` moved verbatim (mechanical extraction, `self.sample_details` -> parameter) to
  `src/peakpicker/infrastructure/quantification/chromatogram_plots.py` (`plot_peak_information`, `create_individual_chromatograms`, `create_overlay_chromatograms`). The three `PeakQuantifier` methods remain as one-line
  delegates, so every caller keeps working (no overlay script imports `quantify_peaks`; checked by grep over the main checkout incl. gitignored overlay). Script 961 -> 438 lines; new module 557 lines.
  `QuantificationPlotExporter` (bar / time-course / comparison charts over `QuantificationResult`) shares no code with these per-sample panels, so nothing was merged into it.
- **Proof** (`tests/test_quantify_peaks_characterization.py`, written and committed before the move): synthetic 4-sample folder -> results table and `all_peaks_detailed.csv` hash-identical, and a canonical fingerprint of
  every figure's artist data (titles, labels, scales, limits, line xy, texts, annotations, table cells, scatter offsets, legends) identical for all 6 figures. One-off: the 6 PNGs and the CSV written before and after the
  move are byte-identical (SHA-256, same machine / matplotlib).
- **Refutation**: the fingerprint harness is shown to change under a 0.001 data change and a title change; the CLI (`python scripts/quantify_peaks.py <folder>` from another cwd) still runs end to end.

### Unit 4 - `src/peak_integrator.py` import prefix

- `from src.peakpicker.utils.numeric import trapezoid` -> `from peakpicker...` with a `ModuleNotFoundError` fallback to `src.peakpicker...`, the same pattern as `peak_models` / `hybrid_baseline`.
  Before: `import peak_integrator` with only `src` on `sys.path` failed (needed the repo root); now both layouts work (`tests/test_legacy_import_paths.py`, subprocess per layout; the `src` case fails on the old code).
- `pytest.ini` keeps `pythonpath = src .`: the private lab tests (`from src.peak_integrator import ...`) and `src.peak_deconvolution` still need the repo root, so the `.` entry is not removable yet.

## Deconvolution speed (2026-10-02, branch `peakpicker/fix/deconv-speed-261002`)

### Unit S1 - `src/peak_fit_engine.py` replaces `curve_fit` inside `PeakDeconvolution`

- **Wiring**: `_fit_n_gaussians` / `_fit_n_emg` call `fit_peak_sum` (same `least_squares`: trf, 2-point Jacobian, same bounds and
  `max_nfev` 10000 / 15000). `curve_fit` raised on a failed or capped fit; `fit_peak_sum` raises the same `RuntimeError`, so the
  callers' failure paths are unchanged. Only `src/peak_deconvolution.py` imports the engine; `peakpicker` package untouched.
- **Profile (c53f76e, slowest real input, 47 points)**: 8 fits, 36k Jacobians, 483k model evaluations, 82 s; every slow fit is an EMG fit
  (91 % of fit time over a 60-input random sample) and fits that end at the iteration cap (about 5 % of EMG fits) are 42 % of EMG time.
- **Change**: only the perturbed component is re-evaluated for each finite-difference column (cached partial sums, original summation order),
  and `erfcx` / `erfc` run only on their own branch. Same floating-point operations per element -> bit-identical results.
- **Proof**: `tests/test_peak_fit_engine.py` (bit-identical to `curve_fit`, same exception at the cap, component equals reference model);
  `tests/test_deconv_decision_golden.py` (20 synthetic cases frozen from c53f76e: single Gaussian, 2.15 sigma pair, tailing EMG,
  10/15/20 % shoulders, 6 and 12 point windows). Real data (not committed): 40-file sample, 908 unique inputs / 1096 peak rows, decisions
  and areas identical, max deviation 0 (`tests/golden/deconv_decision_golden.py real --data <dir> --golden <json outside the repo>`).
- **Refuted (decisions change, not adopted)**: iteration cap 3000 (28 of 908 inputs change), `ftol` 1e-6 (25 change) and 1e-5 (52 change).
  The n / model decision depends on how deep slow-valley EMG fits converge, so any speed-up that shortens convergence is not behaviour-preserving.

## Parallel deconvolution (2026-10-02, branch `peakpicker/feature/parallel-deconv-261002`)

### Unit P1 - `--jobs N` file-level process pool in `scripts/hplc_analyzer_enhanced.py`

- **Wiring**: `main()` -> `batch_analyze(jobs=)` -> `_analyze_parallel` -> top-level `_analyze_file_worker` (replays the analyzer constructor kwargs, returns result + captured stdout). `--jobs 1` (or one file) runs the unchanged serial loop. Default `min(cpu_count-1, 8)`. `batch_analyze_all.py` has no deconvolution (already has its own pool) and is untouched.
- **Design**: one file per task, no shared state; each worker writes its own xlsx; results and console output are collected/replayed in sorted input order. Workers run with OMP/MKL/OPENBLAS threads = 1 (set in the parent env before spawn). A worker exception becomes an `{error, file}` entry, same as the serial path. Peak-level parallelism deliberately not added (file-level already saturates cores on batches).
- **Proof**: `tests/test_parallel_batch.py` (3 synthetic files + 1 corrupt, serial == jobs 2 on arrays, peak_data, every xlsx cell, order, error entry). Real data (not committed): 12 files, serial vs `--jobs 8`, all xlsx cells identical (timestamp column excluded).
