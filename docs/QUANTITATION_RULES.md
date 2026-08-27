# HPLC Quantitation Rules

SSOT for HPX-87P/87H peak-area quantitation conventions. Read this before writing any
new numpy-based integration code for HPLC data -- most quantitation defects traced back
to a request bypassing this file and re-deriving the convention inline.

## 1. Area convention: SECONDS, unit nRIU*s

PeakPicker integrates against the **time axis in seconds** (`time_minutes * 60.0`) to
match the ChemStation convention. Evidence:

- `src/peakpicker/peak_analysis/detectors/peak_detector.py:131-136`
- `src/peakpicker/peak_quantifier.py:122-125`
- `src/peakpicker/models.py:26` (`area  # nRIU*s`)

**Integrating on the raw minute axis returns an area 60x too small.** Every calibration
curve in `methods/*.yaml` is fit against ChemStation seconds-areas, so a minute-axis area
fed into `StandardCurve.predict()` silently returns a concentration ~60x too high.

This exact bug cost a full re-quantitation cycle on 260827/260828 (see
`~/scratch/gpo_87p_260827/REPORT_260828.md`). A regression test pins the seconds
convention: `tests/test_solid_refactor.py::TestAreaConventionSeconds`.

🔴 **Known environment gap (260828):** `peak_detector.py`, `two_pass_detector.py`, and
`peak_integrator.py` call `np.trapezoid`, which exists only in numpy>=2.0. Any environment
running numpy<2.0 (confirmed: this machine's system `python3`, numpy 1.26.4) raises
`AttributeError` on every call to `ProminencePeakDetector.detect()` -- 8 existing tests in
`test_solid_refactor.py` already fail for this reason, independent of anything in this
quantitation work. Before trusting a "detect() returned no peaks" or a crash in this
codebase, check `python3 -c "import numpy; print(numpy.__version__)"` first. Fix is a numpy
upgrade (or reverting to `np.trapz`, which numpy 1.26 still supports but is deprecated in
2.0+) -- not attempted here because it is a cross-project environment change, out of scope
for a single quantitation task.

## 2. Calibration curves: `methods/*.yaml` is SSOT, never hardcode in code

Standard curves live in `methods/*.yaml` under `standard_curves:`, loaded by
`src/peakpicker/quant/method_config.py::QuantMethod.from_yaml()`. That loader accepts
**exactly one schema**:

```yaml
method:
  name: ...
compounds:
  - name: Compound
    rt_min: 12.7
    rt_max: 15.1
standard_curves:
  Compound:
    slope: 42799.4601      # a, in Area = slope*conc + intercept
    intercept: -2395.9675  # y0
    source: "who/when/where this came from"
```

`StandardCurve.predict(area)` computes `(area - intercept) / slope`. A `compound.rt_min`/
`rt_max` is **required as a float** if the compound appears in `compounds:` -- a compound
with an unresolved RT (e.g. galactitol, Step A3 260828) must be **omitted from
`compounds:`** and kept only under `standard_curves:` for when its RT is later resolved.
`from_yaml` will raise `TypeError` on a `null` rt_min/rt_max, and on a `null` r2 field --
omit fields you don't have rather than writing `null`.

🔴 **A second, incompatible schema exists in this repo** (`methods/dgal_tagatose_hpx87h.yaml`,
`compounds[].calibration.{slope,intercept}` nested under each compound) that
**`from_yaml` does not parse at all** -- silently ignored, not an error. Before writing a
new method YAML, check which schema `method_config.py::QuantMethod.from_yaml` actually
reads (this file, not the neighboring YAMLs) -- the two formats look similar enough to
copy the wrong one by pattern-matching a sibling file.

## 3. Column identification: use stoptime, never the stored Acq. Method name

- **stoptime ~38 min → HPX-87P** (sugars)
- **stoptime ~17 min → HPX-87H** (organic acids)

The Agilent `Acq. Method` name embedded in the `.D` folder (e.g. `KS802...`) is **stale**
and does not reliably reflect which column was actually run. Confirmed 260827/260828: the
260415 archive's non-`_87P`-suffixed folders (stoptime 17 min) share method metadata with
the `_87P`-suffixed 38-min folders despite being a different column/chemistry entirely.

## 4. Peak assignment: RT-order guesswork is forbidden; confirm by area correlation

Never assign a compound to a peak because "it elutes in the expected order." Confirm with
the actual data: correlate each candidate peak's area time-series against the reference
concentration (xlsx / independent assay) **per series/condition**, not pooled across
series with different initial charges -- pooling can hide or invert a real correlation
(Simpson's-paradox-shaped artifact measured 260828: pooling PREBO+MPSP+YIELD gave r=0.37
for the correct Gal assignment, while each series alone gave r>0.96).

Precedent this rule exists because of: `methods/dgal_tagatose_hpx87h.yaml`'s "D-Gal+Tag"
combined-peak note documents an HPX-87H case where Gal(19.0) < Tag(26.6) < Galol(41.5) in
RT but elution order did not match assumed compound order, forcing a combined-peak
treatment.

**Even a confirmed per-series correlation is not sufficient on its own.** Cross-check the
assignment at every timepoint where the reference concentration is/should be zero or
otherwise physically constrained -- a real assignment must go to (near) zero area when the
reference says zero. If area remains large while the reference reads zero, that is
evidence of co-elution with an unidentified second component, not measurement noise.
Measured 260828: the 13.9 min HPX-87P peak correlates r>0.96 with xlsx D-Galactose within
each of PREBO/MPSP/YIELD taken separately, and PREBO alone reproduces the pre-existing
anchor (median APE 1.9%) -- yet in the MPSP series, `xlsx_Gal == 0` at t>=24h while the
13.9 min peak area still implies 50-83 mM of "Galactose." The peak shape (apex RT,
half-height width, symmetry) stayed essentially unchanged from t=0h to t=48h -- no
shoulder, no double apex -- so this is a genuine co-elution with a species that shares
Galactose's exact retention time, not a baseline-integration artifact. The unidentified
co-eluting species was not resolved (galactitol, formate, and a media/host-cell background
were all considered and none fit the magnitude or the required-dilution-factor pattern);
see `~/scratch/gpo_87p_260827/REPORT_260828.md` Step A2 for the full elimination trail.
**Report a peak as "confirmed for series X, contaminated by co-elution in series Y" rather
than picking the assignment that fits best on average.**

## 5. Tuning axes: allowed vs. forbidden (260827 policy, reaffirmed 260828)

Allowed — anything that measures the true peak area more accurately:
baseline strategy (valley-to-valley / ARPLS / weighted-spline), anchor-finder parameters,
peak boundary rule, per-compound RT window width, smoothing, trapezoid vs. Simpson.

Forbidden — anything that manufactures agreement with a target:
calibration curve coefficients (SSOT is the wet-lab standard curve, not a fit-to-target),
per-condition recovery/correction factors, any multiplicative "carbon balance closure"
factor. **The objective is xlsx-reproduction error, not carbon balance.** If a tuning
choice makes an existing carbon deficit disappear, report that as a finding to investigate
(possible sign that the deficit itself was a Gal-overestimation artifact) — never treat
"deficit closes" as evidence the tuning choice is correct, and never keep iterating toward
that outcome.

Dilution factor `D` may be treated as a free parameter to **investigate** (never to fit
freely) only when: (a) at least two independent timepoints in a stable-RT window give the
same required-D within a few percent of each other, AND (b) every other analyte measured
in the same physical sample (i.e. same dilution) is consistent with the same D. Condition
(b) is the one that usually kills a tempting D-anomaly: measured 260828, the YIELD series'
D-Galactose readings imply D~109 (two points, self-consistent) while D-Tagatose readings
from the *same samples* are better explained by D=40 at some timepoints and by neither
value cleanly at others -- one physical dilution cannot produce two different effective D
for two solutes in the same vial, so the D~109 reading was reported as an unresolved
anomaly, not applied as a correction.
