# Re-quantification runbook

How to (re-)quantify a set of HPLC runs with PeakPicker, change an integration
window or baseline for a subset, record why, and hand off a table that can be
trusted. Every command below was run on 261003 against a synthetic fixture
(section 10) or with `--help`; the output shapes quoted are from those runs.

Typical requests this runbook answers:

- "quantify all of these runs with PeakPicker"
- "re-integrate only the low-signal replicate with a wider window; does the answer change?"
- "quantify the additional runs, merge them in, and open the time course"

Scope: this file describes the public tool. Lab-specific sample-name parsers,
real calibration curves, method YAMLs and data paths live in the private overlay
(see [PLUGINS.md](PLUGINS.md)) and are not repeated here. Read
[QUANTITATION_PITFALLS.md](QUANTITATION_PITFALLS.md) before touching a baseline,
and the local `docs/QUANTITATION_RULES.md` when your checkout carries the overlay.

## 1. Pick the entry point

| Situation | Entry point | Proven by |
|---|---|---|
| Exported ChemStation CSV files, quick peak table (area, half-peak, deconvolution) | `scripts/hplc_analyzer_enhanced.py` | `--help` + fixture run |
| Raw `.D` folders, no ChemStation needed | `scripts/analyze_direct.py` (needs `PYTHONPATH=.`) | `--help` |
| Whole data tree, auto-selected method | `scripts/batch_analyze_all.py` | `--help` |
| Compounds, calibration, concentration in mM from a method YAML | `peakpicker.agent.LCQuantAgent` (Python API) | fixture run |
| Calibration-curve object only (`area -> conc`) | `peakpicker.QuantMethod` / `StandardCurve` | fixture run |
| One folder of CSVs, legacy summary + calibration plot | `scripts/quantify_peaks.py <folder>` | fixture run |

`quantify_peaks.py` has no argparse (a `--help` is read as a folder name), writes
`<folder>/quantification/` next to the input, and compares against a hard-coded
reference curve. Use it for a look, never as the concentration of record.

Environment (from the repo root; Windows Git Bash):

```bash
conda activate PeakPicker            # or any env with pip install -e .
PYTHONPATH=src python scripts/hplc_analyzer_enhanced.py --help
```

`numpy >= 2.0` is required for the detectors (`np.trapezoid`); check
`python -c "import numpy; print(numpy.__version__)"` before trusting a
"no peaks" result.

## 2. Input formats and where the data lives

| Format | Reader | Note |
|---|---|---|
| ChemStation CSV export | `hplc_analyzer_enhanced.py`, `quantify_peaks.py` | UTF-16 LE with BOM, tab-separated `time_min<TAB>signal`, CRLF |
| `.D` folders (`RID1A.ch`, `VWD1A.ch`, ...) | `analyze_direct.py`, `LCQuantAgent`, `batch_analyze_all.py` | decoded with `rainbow-api`; never hand-write a parser |

Raw-data root, resolved by `peakpicker.config.paths.get_data_root()` in this
order: explicit path, `$CHEM32_DATA`, `<OneDrive root>/HPLC_DATA` (also under
`/mnt/c/Users/*/` on WSL), then `C:\Chem32\1\DATA`. Rules that have bitten before:

1. The raw tree holds raw data only. Send every output to a separate analysis
   directory (`-o`, `--output`, `output_dir`).
2. Identify a sample by the name stored in the `.D` acquisition header, never by
   vial number or folder prefix (vial numbers repeat inside one sequence, and a
   run cut short keeps its name).
3. Identify the column by run time (stop time), not by the stored method name.
4. Do not edit or rename raw `.D` folders; rename only a copy.

## 3. First pass (whole set)

```bash
# CSV export -> one <name>_peaks.xlsx per file (sheets: Summary, Peaks, Deconvolved_Peaks)
PYTHONPATH=src python scripts/hplc_analyzer_enhanced.py <csv_dir> -o <analysis_dir> --jobs 4

# .D folders, filtered by name regex, no plots
PYTHONPATH=. python scripts/analyze_direct.py <seq_dir> -o <analysis_dir> --pattern "<regex>" --no-plots

# Whole tree, restricted to one project folder; --test = max 3 files per folder
PYTHONPATH=src python scripts/batch_analyze_all.py --base-dir <data_root> --folder <name> --output <analysis_dir> --test
```

`--jobs N` is file-level parallelism and gives identical numbers to `--jobs 1`
(pinned by `tests/test_parallel_batch.py`). A file that fails does not stop the
batch; the exit code is 1 when any file failed, so check it.

Concentrations in mM come from the method layer:

```python
from peakpicker.agent import LCQuantAgent
agent = LCQuantAgent("methods/<method>.yaml")        # warns on missing r2 / source
df = agent.run(data_dir="<seq_dir>", output_dir="<analysis_dir>", experiment_id="<run_id>", plot=True)
# df columns: sample_id, compound, rt_min, area_nRIU_s, conc_mM, qc_flag, condition, time_h, is_ne, <factors>
```

Method YAML schema, calibration sign convention and the two loaders: see
section 2 of the local `QUANTITATION_RULES.md` and `methods/example_hpx87h.yaml`.
Two conventions to keep apart (both verified on 261003):

| Loader | Schema | Conversion |
|---|---|---|
| `LCQuantAgent` (`method_config_lc.py`) | `compounds.<name>.calibration.{slope,intercept}` | `conc = area * slope + intercept` |
| `QuantMethod.from_yaml` | `standard_curves.<name>.{slope,intercept}` | `conc = (area - intercept) / slope` |

Loading the example method with `QuantMethod.from_yaml` raises `TypeError`; copy
a sibling of the loader you will actually use.

## 4. Area convention and unit traps

- Areas are nRIU*s: the time axis is integrated in **seconds**. A minute-axis area is 60x too small.
- Measured on the fixture: the `Peaks` sheet `area` is in seconds, but
  `Deconvolved_Peaks.Component_Area` is on the minute axis (a 80-height, sigma 0.1 min
  Gaussian gave 20.3 against 1203 in seconds). Multiply a component area by 60
  before using a seconds-based calibration.
- Half-peak and whole-peak areas are different quantities. `--half-peak left|right|auto`
  reports `2 x half` in `area` and keeps `half_area`, `full_area`,
  `half_peak_mode` and `asymmetry_warning` in the `Peaks` sheet. A calibration built
  on whole peaks must not be applied to half-peak areas, and the reverse. Always
  state the basis next to the number.

## 5. Integration window and baseline: what can be changed

Allowed (they measure the true area better): baseline strategy, anchors, peak
boundary rule, per-compound RT window, smoothing, trapezoid vs Simpson.
Forbidden (they manufacture agreement): calibration coefficients fitted to a target,
per-condition correction factors, any closure factor. The objective is a correct
area, not a balance that closes.

Where each lever lives:

| Lever | Where | Effect |
|---|---|---|
| Apex search window and flanking valley search | `compounds.<name>.rt_window` in the method YAML (valley search margin = half the window width) | measured: widening the window of a small peak on a tail moved its area 180.3 -> 174.8 nRIU*s on the fixture |
| Smoothing | `baseline.smoothing_window`, `baseline.smoothing_poly` | apex location only |
| Detection sensitivity | `peak_detection.min_prominence_factor`, `min_height_fraction`, `distance_pts`, `trim_rt_start/_end` | which peak is taken |
| Baseline floor (arPLS path) | `negative_threshold` in `config/baseline_config.py` (-50 nRIU default) | see PITFALLS section 1 |
| Tail or shoulder peak | standalone local-baseline script (PITFALLS sections 2 and 3) | not implemented in the library |

Always integrate a no-analyte control (or blank) with exactly the settings used for
the samples; a clearly non-zero area means the baseline, not the chemistry, is wrong.

## 6. Re-integrating a subset and recording why

Never edit the method YAML that produced the original numbers. Make a variant,
rerun only the affected folders, and keep both result sets.

1. Copy the YAML to `<method>_reint_<YYMMDD>.yaml`, set a new `method_id`, change
   only the intended `rt_window` / baseline keys.
2. Add a top-level `reintegration:` block. `LCQuantAgent` ignores unknown keys (verified on 261003; `QuantMethod` reads only
   `method`, `compounds` and `standard_curves`), so it is the in-file record of the rationale:

   ```yaml
   method_id: <base>_reint_<YYMMDD>
   reintegration:
     base_method: <base method_id>
     date: "<YYMMDD>"
     samples: [<sample ids re-integrated>]
     changed: {"<Compound>.rt_window": [[<old lo>, <old hi>], [<new lo>, <new hi>]]}
     why: <what was wrong with the old window, in one or two sentences>
     validated_on: <control/blank used, or "not independent">
   ```

3. Run on the subset only (a directory holding just those `.D` folders, or `--pattern`
   with `analyze_direct.py`) and write to a new output directory named for the variant.
4. Copy the variant YAML into that output directory as `method_used.yaml`, so the
   record travels with the numbers.
5. Add a row per re-integrated sample/compound to the result table with the
   columns `window_used`, `reint_of` (original run id) and `note`. The original row stays.
6. Report both values and the difference. If the conclusion changes with the
   window, the conclusion is not robust; say UNDECIDED, do not pick the window that
   gives the expected answer.

A suspect single value is flagged and left raw, not replaced by a marker-corrected
number. Confirm it with a re-injection or more replicates.

## 7. Replicates: the n decision

Quantify every replicate that exists and decide n from what is valid, not from what
was planned.

- Build one long table with a row per sample x compound and the columns
  `condition, rep, time_h, <compound>_mM, valid_for_quant, skip_reason`.
  Allowed `skip_reason` values: `truncated_chromatogram`, `missing_window`,
  `no_peak_detected`, `qc_flag:<text>`, `not_injected`.
- n per condition and time point = the number of rows with `valid_for_quant == True`.
  It is reported in the table, not assumed.
- Never impute a missing replicate (no copying the mean, no borrowing from another
  series). Never pool replicates across series with different initial charges.
- n >= 3: mean and sample SD (`ddof=1`). n = 2: show both points, give the range, no SD
  bars. n = 1: one point, flagged. A figure and its caption must state the n actually
  used per point.
- A missing replicate is listed with its reason in the hand-off note, so a later run can
  fill the gap without re-deciding.

## 8. Time-course output

From the `LCQuantAgent.run` frame (condition and `time_h` come from the sample parser;
a lab parser is registered through a plugin):

```python
ok = df[(df.qc_flag == "") & df.conc_mM.notna() & ~df.is_ne]
tc = (ok.groupby(["compound", "condition", "time_h"])["conc_mM"]
        .agg(n="count", mean="mean", sd=lambda s: s.std(ddof=1)).reset_index())
tc.loc[tc.n < 3, "sd"] = float("nan")
```

On the fixture this printed `n = 3` for every point except one deliberately removed
replicate, which showed `n = 2` and `sd = NaN`. Write three tables next to each other:
`raw_quant.csv` (every row, valid or not), `timecourse_quant.csv` (per replicate),
`summary_by_condition.csv` (the `tc` frame), plus an `.xlsx` with the same sheets and
the time-course PNG. Open the PNG and judge it yourself before reporting.

Where the quantified result of record is saved is a lab decision: keep it in an analysis
directory outside the raw tree, one directory per run, holding the three tables, the
`method_used.yaml` and the hand-off note; in the private overlay this is the documented
analysis root. A copy pasted into a manuscript is a stale-copy candidate: cite the
directory, do not paste the value.

## 9. Verification

| Check | How |
|---|---|
| Tool behaviour unchanged | `python -m pytest tests/test_parallel_batch.py tests/test_standard_curve_loq.py tests/test_solid_refactor.py tests/test_half_peak.py -q` (38 passed, 1 skipped on 261003) |
| Controls | no-analyte control and blank integrate to about zero with the same settings |
| Independent area | compare against the ChemStation area of the same run; quote the agreement band, two single areas inside it are not "different" |
| Units | seconds, half vs whole peak, minute-axis deconvolution areas (section 4) |
| Replicates | n per point is stated and no value was imputed |

A number that enters a manuscript, report, e-mail or billing sheet, a converged
calibration or fit, or a number produced on another machine is re-verified before
it is trusted: freeze the provenance (script, commit, method YAML, run ids), run the
mechanical gates (`Skill(verification-gates)`; the repo's `.fiducial.toml` for
parameter drift), then the plausibility, identifiability and mass-balance checks in
`Skill(scientific-validation)`. Results from a remote or home machine stay
provisional until reproduced on the laptop.

## 10. Reproducing the fixture

```bash
python - <<'EOF'
import numpy as np
from pathlib import Path
d = Path("fixture"); d.mkdir(exist_ok=True)
for i in range(3):
    rng = np.random.default_rng(i); t = np.linspace(0, 10, 1200)
    y = (50*np.exp(-0.5*((t-3.0)/0.08)**2) + 80*np.exp(-0.5*((t-6.0)/0.1)**2)
         + 30*np.exp(-0.5*((t-6.25)/0.1)**2) + rng.normal(0, 0.2, t.size) + 5)
    txt = ''.join(f'{a:.4f}\t{b:.5f}\r\n' for a, b in zip(t, y))
    (d/f"S_rep{i+1}.CSV").write_bytes(b'\xff\xfe' + txt.encode('utf-16-le'))
EOF
PYTHONPATH=src python scripts/hplc_analyzer_enhanced.py fixture -o fixture_out --half-peak left --jobs 1
```

Expected: `Successfully analyzed: 3/3 files`, three `S_rep*_peaks.xlsx`; with
`--half-peak none` the second peak has `area == full_area` (1666.6), with `left` it
is about 1268.5 and `asymmetry_warning` is true.
