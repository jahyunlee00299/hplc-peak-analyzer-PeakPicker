# Quantitation pitfalls and recipes for RID peak areas

This guide collects pitfalls and recipes for quantifying refractive-index detector (RID)
peak areas from ChemStation data. It describes the method only; all examples are synthetic,
and method-specific values must come from your own method notes.

## 1. RID baseline floor: a clamped arPLS baseline over-integrates late peaks

`BaselineGenerator._apply_constraints` constrains the fitted baseline with
`np.maximum(baseline, negative_threshold)` whenever `allow_negative` is set (the default), and
`BaselineGeneratorConfig.negative_threshold` defaults to **-50.0 nRIU**
(`BaselineCorrectorConfig.negative_clip_threshold` carries the same default but is not read
by the clamp).
Evidence:

- `src/peakpicker/baseline/generators/baseline_generator.py` (`_apply_constraints`, the
  `allow_negative` branch)
- `src/peakpicker/config/baseline_config.py` (`negative_threshold`, `negative_clip_threshold`)

On a refractive-index (RID) trace the signal can make a large **negative excursion
late in the run** (a system or solvent dip well below zero). arPLS follows that dip, the
fitted baseline dives below the floor over the last minutes of the run, and the clamp holds
it at exactly -50 nRIU. A peak eluting in that region is then integrated from -50 nRIU
instead of from the true local baseline near zero: a **pedestal** of roughly the floor depth
times the integration window is added to the peak area. The bias is additive but **not
constant** -- its size follows the depth and position of the dip and the integration
window, and it varies from run to run -- so it cannot be removed by subtracting one fixed
offset. The relative error is largest for small peaks.

How to detect it:

- **Integrate a control that must read ~0** (a no-analyte control or a blank) with exactly the
  same settings as the samples. A clearly non-zero area in that control means the baseline,
  not the chemistry, is wrong. This is the most sensitive test, because in a real sample the
  pedestal hides inside a plausible-looking area.
- **Look for baseline points sitting exactly on the floor.** If the baseline under or next to
  the peak equals `negative_threshold` over a stretch of points, the clamp is active there.
- **Compare with a fixed-anchor diagnostic baseline** (a straight or Hermite line anchored on
  flat signal on both sides of the peak, section 2). A large, systematic difference between
  the two areas, concentrated in late peaks, points at the clamp.

What to do: treat the baseline as the problem (change the baseline strategy, anchors and
windows); use a local baseline for the affected peak (section 2) or re-examine the floor for
RID data. Never absorb the pedestal into the calibration or a correction factor.

## 2. Local baseline recipe for a peak on the tail of a large earlier peak

A peak that sits on the descending tail of a large earlier peak (or of a broad hump) has
neither a horizontal baseline nor a flat valley to anchor on. The recipe below fits the tail
locally on both sides of the peak and bridges it with a smooth curve.

| Step | Setting |
|---|---|
| Apex | maximum of a lightly smoothed trace (e.g. Savitzky-Golay), optionally after subtracting a chord, searched within `RT_expected +/- w_apex`; smoothing is used **for locating the apex only** |
| Anchor windows | two windows straddling the apex, `[apex - a_far, apex - a_near]` on the left and `[apex + b_near, apex + b_far]` on the right, placed on tail signal that is free of the peak |
| Anchor fit | a straight-line fit in each window gives the baseline **value and slope** at that window |
| Baseline | cubic Hermite curve between the two anchors, matching value and slope at both ends |
| Integration | on the **raw** (unsmoothed) trace, from `apex - l` to `apex + r` (fixed offsets from the apex), time axis in seconds, area in nRIU*s |
| Detection gate (optional) | smoothed apex height above the baseline >= `h_min`, else report "not detected" (the area may still be recorded) |

Per-method choices: `w_apex`, the smoothing window and order, the four anchor offsets,
`l`, `r` and `h_min`. They depend on the column, flow, runtime and the shapes of the
neighbouring peaks, so a value that works for one method is not a default for another.

How to choose them:

- Choose them **on controls**: a no-analyte control must integrate to about zero (within
  the noise area of the window), and, where available, reference areas from an independent
  integration of the same runs should be reproduced within their usual spread.
- **Never tune them to reach a target** concentration, yield, balance or expected trend.
  Record the chosen values and how they were chosen next to the results.
- If the controls and reference areas were used to choose the windows, they are no longer
  an independent validation of the recipe; say so, and validate on runs that were not used.
- Quote the agreement band with the reference integration when comparing single areas:
  two single areas that differ by less than that band are not "different".

Implementation status: PeakPicker's `Quantifier` (`src/peakpicker/quant/quantifier.py`) does not implement this baseline. A method
YAML may carry an `integration:` block describing it, but `QuantMethod.from_yaml` reads only
`method:`, `compounds:` and `standard_curves:` and ignores that block;
the recipe has to be executed by a script until a library
implementation exists.

## 3. Split peaks: two analytes on one peak

When an early analyte and a later analyte elute as one peak (or as a peak with a shoulder):

- Draw **one common baseline** for both parts, from a left anchor before the peak to a right
  anchor after the later analyte. Two separately drawn baselines double-count or lose area
  at the junction.
- Integrate the **left part up to the apex** for the early analyte, and a **defined, fixed
  window** for the later analyte. The rule (split point, window limits) must be written down
  with the result; different split rules give different areas for the same run.
- A left-part ("half-peak") area and a whole-peak area are different quantities. A
  calibration built on half-peak areas must only be applied to half-peak areas; applied to a
  whole-peak area it is off by a factor of about two for a symmetric peak, and by more for a
  tailing one -- that mismatch is not evidence that the calibration is wrong. **Report the
  basis (half or whole peak) with the number.**
- **If no standard has been injected on the current method:** anchor the response to a control whose nominal
  concentration is known (for example a no-reaction control of the same series, same
  dilution): `RF_eff = area_control / (C_nominal / DF)`, and
  `C_sample = C_nominal * area_sample / area_control` when sample and control share the
  dilution. This is a relative measurement tied to that control, not a calibration; a curve
  that was never injected on the current method is at best provisional.
- **A large neighbouring peak lifts the left anchor.** If the tail of a large earlier peak
  is still well above the baseline at the usual left anchor, the common baseline tilts and
  the early analyte's area can even come out negative. Anchor instead at the **valley**
  between the large peak and the split peak (minimum within a small search window) and at
  the **flat right end** after the later analyte (mean over a flat stretch), and use the
  **identical integration bounds for treated and control samples**, taken from the control.
- **Baseline-free cross-check** for the later analyte: build the difference trace
  `D(t) = S(t) - f * C(t)`, where `S` is the treated sample, `C` the control and `f` the
  fraction of the early analyte remaining (scaled so that the early analyte's left half
  cancels). Integrate `D` over the later analyte's window and compare it with the noise area
  of the same window (noise standard deviation times window length). If the window reading
  and the difference-trace reading disagree in sign or by more than the noise area, the later
  analyte is **unresolved** (baseline-dependent) -- report it as unresolved, not as absent
  and not as a number.
- Different read-outs of the same analyte (window integration, difference trace, a fitted
  model of the control shift) can give different values. Quote the method with every number.

## 4. Never convert a peak height to concentration with a guessed ratio

A peak height is not an area. Converting a height to a concentration by assuming an
area/height ratio (a "typical width") produces a number that looks like a measurement but
depends entirely on the assumed ratio; the ratio changes with peak width, tailing, retention
time and the baseline used. Report a height only as a height, and wait for the area. If a
height has to be discussed before the area exists, label it as a height, give no
concentration, and replace it as soon as the area is available.

## 5. Carry-over ("ghost" peaks) from a run injected several runs earlier

A late-eluting component from an earlier injection can appear several runs later as a
**broad hump**, at a retention time where nothing from the current injection elutes. It
adds area under any peak it overlaps and can make a no-analyte control look contaminated.

How to test for it by lag:

1. For every run, record whether the hump is present (a measured criterion, e.g. apex height
   and width above set thresholds, decided before looking at the source runs).
2. For each candidate lag `k` (1, 2, ... up to a plausible maximum `K`), label each run by the
   type of the run injected `k` positions earlier (e.g. contains the component or not). Runs
   with no source run `k` positions earlier (the start of the sequence) are excluded for that
   lag -- and are themselves a useful check: they should show no hump.
3. Compare hump presence between the two groups for each lag (e.g. a one-sided Fisher exact
   test on the 2x2 table).
4. If the lag was picked after looking at several lags, **correct for the number of lags
   tested** (e.g. multiply the p-value by `K`). A lag that separates the groups perfectly is
   strong evidence, but it is still an inference about carry-over.
5. The retention time of the ghost in the later run follows from the lag and the injection cycle:
   `t_elution_total = k * t_cycle + t_in_run`, where `t_cycle` is the time between consecutive
   injections (run time plus any post-run or injection delay). A component with this total
   elution time under the method conditions is a plausible source.

Confirmation and prevention: inject **wash or blank runs** after samples that carry the
late-eluting component, and include at least one blank in each sequence at a position
where carry-over would show. Without a blank injection, "carry-over" stays an inference.
A sharp feature that is also present in the controls is not a product of the treatment
by itself; check whether a smaller copy of it appears in other runs before assigning it.

## 6. Do not inherit claims from old notes; re-measure

Statements such as "the control trace is flat in this window", "no co-elution" or "no
carry-over" are properties of a specific set of runs. Before relying on one, re-measure it
on the runs in front of you: for each control run, measure the elevation relative to a flat
reference stretch at several time points across the window of interest, and quote those
numbers. A statement copied from a note about a different acquisition, a different column
or a different method is not evidence for the current data, and a corrected statement is
rarely corrected everywhere it was copied -- go back to the measured source.
