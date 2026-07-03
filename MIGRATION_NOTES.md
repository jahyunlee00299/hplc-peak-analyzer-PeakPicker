# Detector Consolidation — Migration Notes (branch `refactor/detector-consolidation-260704`)

## Goal
Peak detection was reimplemented in several divergent copies while the
sophisticated canonical detector
`src/peakpicker/peak_analysis/detectors/two_pass_detector.py::TwoPassPeakDetector`
was used only by `application/workflow.py` + tests. This branch consolidates
general-purpose peak detection onto that ONE canonical detector, **without
changing any numerical result** (this repo produces manuscript data).

## Diagnosis — held, with one correction
- **Canonical detector confirmed**: `TwoPassPeakDetector.detect(time, signal, baseline)`
  — prominence-based two-pass `find_peaks`, MAD-of-derivative noise, 1%-descent
  boundaries capped at adjacent valleys, trapezoid-in-seconds area. Consumed
  only by `application/workflow.py` (via `WorkflowBuilder.with_two_pass_peak_detector`).
- **Divergent copies confirmed**:
  - `scripts/batch_analyze_all.py::_detect_peaks` — two-pass mirror.
  - `scripts/hplc_analyzer_enhanced.py::_detect_peaks_adaptive` — two-pass mirror + half-peak logic.
  - `analyses/*.py` — per-experiment `detect_peaks(prominence=<magic>, distance_pts=<magic>)`
    (e.g. 260317: 300/40, 260225: 500/50) and `batch_cofactor_analysis.py` two-pass variant.
- **Correction to the diagnosis**: `src/peakpicker/peak_quantifier.py:77` was
  listed as a "divergent copy" of the detector. It is **not** — it is a
  fundamentally different *targeted single-compound quantifier* (per-compound RT
  window, single tallest peak, valley drop-line baseline, and
  `min_prominence_factor` used as a **noise multiplier** = 3.0, not a
  signal-range fraction). Routing it through `TwoPassPeakDetector` would change
  every quantified area. It is therefore **deliberately left as its own path**
  (documented in its module docstring). The same applies to the
  `analyses/quantify_*.py` family, which share this targeted pattern.

### Divergences that made a naive redirect number-changing
The two script copies differ from the canonical detector in two ways that
**change which peaks are found and their areas**:
1. **Noise estimation** — scripts use a *percentile-based* estimator; canonical
   default is *MAD-of-derivative*. Measured >2x difference on synthetic data
   (MAD 17.1 vs percentile 7.6 → minor-pass prominence 34.3 vs 15.3).
2. **Max-width cap** — scripts shrink over-wide peaks to a 2-minute window
   around the apex; canonical has no such cap.

## What was consolidated (numerically verified identical)

### 1. Canonical detector — additive, behavior-preserving hooks
`TwoPassPeakDetector.__init__` gained four **optional** parameters, all
defaulting to `None` so existing callers (workflow.py) are byte-for-byte
unchanged:
- `noise_estimator` — inject an alternative noise function (else MAD default).
- `max_width_samples` — opt-in 2-minute-style width cap (else no cap).
- `major_min_width` / `minor_min_width` — override the per-pass `width=` (else config default).

Verified: default construction leaves all four `None` and reproduces the
original algorithm (see smoke test in commit).

### 2. `scripts/_two_pass_detect.py` (new) — shared script-level entry point
Routes the batch/enhanced scripts through the canonical detector with the
scripts' exact parameters (percentile noise + 2-min width cap). Provides:
- `estimate_noise_percentile()` — the scripts' original percentile estimator (SSOT).
- `detect_peaks_two_pass()` — full `(peaks, peak_data)` tuple, routed through `TwoPassPeakDetector`.
- `detect_two_pass_indices_props()` — shared two-pass **index + properties** logic
  for callers that own their own boundary/half-peak post-processing.

**Equivalence proven**: on 8 synthetic chromatograms, both the full
`peak_data` dicts (batch path) and the `(peaks, properties)` (enhanced path)
are **identical** to the removed inline copies.

### 3. `scripts/batch_analyze_all.py`
Private `_estimate_noise` + `_detect_peaks` **removed**; now calls
`estimate_noise_percentile` + `detect_peaks_two_pass`. Also fixed a
pre-existing path bug (`Path(__file__).parent/'src'` → `.parent.parent/'src'`)
and dropped now-unused `scipy` imports.

### 4. `scripts/hplc_analyzer_enhanced.py`
The duplicated two-pass detection+merge block and private `_estimate_noise`
**removed**; detection now delegates to `detect_two_pass_indices_props` +
`estimate_noise_percentile`. The half-peak / asymmetry / area post-processing
is **unchanged** (operates on the same peaks/properties). Same path-bug fix.

### 5. `analyses/_detect.py` (new) — thin shared wrapper for per-experiment scripts
- `detect_peaks_legacy_single_pass()` — exact repro of the old single-pass
  `detect_peaks`, centralising the magic numbers at the call site.
- `detect_peaks_canonical()` — recommended path for NEW analyses (canonical two-pass).

### 6. Representative analyses migrated (2, as a proven pattern)
- `analyses/peakpicker_260317_Xul5P_AcP_Pre.py` — the cited example (300/40).
- `analyses/peakpicker_260324_Xul5P_Test.py` (300/40).
Both now call `detect_peaks_legacy_single_pass` (byte-identical). Note: in these
scripts `detect_peaks` feeds only a **printed RT summary** — areas come from
`get_area` window integration, so no published area/yield number is affected.

## What was deliberately left (and why)

| File | Left as-is because | TODO left in code |
|---|---|---|
| `src/peakpicker/peak_quantifier.py` | Targeted single-compound quantifier, different algorithm; redirect would change all areas. | Docstring note (no code change needed) |
| `analyses/quantify_260302_48H_GO.py`, `quantify_260307.py`, `quantify_rpm_buffer.py` | Same targeted pattern as `peak_quantifier` — belong to `PeakQuantifier`, not the two-pass detector. | TODO on each `quantify_peak` |
| `analyses/batch_cofactor_analysis.py` | Two-pass **variant** but uses `noise_level*5` (not *3) for the major pass — a drop-in swap would change numbers. | TODO on `detect_peaks` |
| `analyses/peakpicker_260225_ACP_analysis.py` | Single-pass RT-summary (500/50); trivially migratable but left for a reviewable batch. | TODO on `detect_peaks` |

## Test results (honest)
`pytest tests/` — **26 failed, 2 passed**, identical to the pre-change baseline
on this branch. **All 26 failures are pre-existing and unrelated**: `tests/test_solid_refactor.py`
imports the stale `solid.*` package (the code was renamed `solid` → `peakpicker`
but the test file was never repointed), and `tests/test_half_peak.py::test_real_data`
hits the same missing module. None of the failures touch any file changed here.

Equivalence of the consolidation was verified separately with dedicated
byte-for-byte comparison scripts against the original inline implementations
(8 synthetic chromatograms each, all identical).

## Remaining steps for the user
1. **Finish the `analyses/` migration** using the two worked examples:
   - Trivial single-pass (`peakpicker_260225_ACP_analysis.py`) → swap to
     `detect_peaks_legacy_single_pass` (exact) or `detect_peaks_canonical` (upgrade).
   - `batch_cofactor_analysis.py` → migrate to canonical two-pass **only with a
     reference-output regression test** (it uses `*5`, not `*3`).
   - `quantify_*.py` → route through `PeakQuantifier` (targeted family), not the
     two-pass detector.
2. **Magic-number relativization**: the single-pass analyses hard-code
   `prominence`/`distance_pts` per experiment. Consider moving these into a
   small per-experiment config (or deriving prominence from noise) once the
   detection path is unified.
3. **Repo hygiene (out of scope here, flagged)**:
   - `tests/test_solid_refactor.py` still imports `solid.*` — repoint to
     `peakpicker.*` (or delete the stale `src/solid/` duplicate) so the suite runs.
   - `peakpicker.utils` is missing (only `src/solid/utils` exists), which makes
     `peakpicker.infrastructure` un-importable. Restore `peakpicker/utils` (move
     `plot_utils.py`) so the package imports cleanly.
