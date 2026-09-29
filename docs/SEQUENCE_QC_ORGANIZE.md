# ChemStation sequences: identify, verify and organize before quantitation

Applies to a ChemStation sequence directory (`.D` run folders, usually accompanied by the
sequence summary, log, batch and method files) that is about to be analysed or handed back
to ChemStation for review. Code:

- `src/peakpicker/infrastructure/file_readers/sequence_qc.py` -- header reader, aborted-run
  detection, rename planning, copy-and-rename, md5 verification (tests:
  `tests/test_sequence_qc.py`)
- `src/peakpicker/infrastructure/file_readers/chem_layout_qc.py` -- read-only layout checker
  for a folder handed to ChemStation; its rules, their evidence and their status live in
  `chem_layout_spec.yaml` next to it (tests: `tests/test_chem_layout_qc.py`). This document
  refers to those rules by id (L1-L10) and does not repeat the rule table.

## 1. Identify samples by the header sample name, never by vial or folder number

- **Vial numbers are reused inside one sequence.** Instrument-generated folder names encode
  position, typically `<vial>-<line><rep>.D`, so two different samples injected from the same
  vial position on different sequence lines share a vial prefix, and a vial number alone
  does not tell them apart.
- The **sample name stored in the signal file header** (`RID1A.ch` for a RID channel) is the
  identity of a run. `SequenceIntegrityChecker.read_run(d_folder)` reads it, together with
  the acquisition date, the method name and the start/end time, without decoding the trace;
  `scan_sequence(seq_dir)` returns one `RunInfo` per `.D`.
- Header fields used by `sequence_qc` (ChemStation "130" format, big-endian):

  | Offset | Field | Encoding |
  |---|---|---|
  | `0x11A` | start time | int32, milliseconds |
  | `0x11E` | end time | int32, milliseconds |
  | `0x35A` | sample name | 1-byte character count, then UTF-16LE text from `0x35B` |
  | `0x957` | acquisition date | same length-prefixed UTF-16LE form |
  | `0xA0E` | method name | same length-prefixed UTF-16LE form |
  | `0x1800` | start of the signal data region | -- |

- Map every run to its sample through the header name and keep that mapping in a sample map
  (section 4). If a whole sequence may have been started one index off,
  `detect_label_shift(series, reference)` scores candidate offsets against a reference series
  (typically one analyte's area) and returns every candidate, best first.
- The `Acq. Method` name stored in a `.D` is not reliable for column identification; use the
  stoptime (run time) and your local method notes instead. The same column can be run with a
  different runtime, so declare runtimes per method.

## 2. Detect aborted runs from the header

- A run whose header end time is below **95 %** of its method's nominal runtime is
  incomplete (`DEFAULT_COMPLETE_FRACTION = 0.95`). The nominal runtime is the one declared
  for that method (`nominal_runtimes`) or, if none is declared, the modal end time of the runs
  sharing the method. `RUN.LOG` is not used: a truncated run has no usable runtime there.
- Declare nominal runtimes whenever possible. The modal fallback is computed from the runs
  in the folder being checked, so a folder holding a single aborted run would be judged
  complete against itself (this is why rule L4 takes `nominal_min_by_method`).
- A run copied while the sequence was still acquiring is truncated in the copy even if it
  later finished on the instrument. Copy again after the last run ends and re-verify; an md5
  pass made while the sequence was running is not valid for the final data.
- An aborted run and its re-run can carry the same folder name in different copies;
  `find_duplicate_labels` groups them so the complete member can be selected.

## 3. Organizing recipe (raw data are never modified)

1. **Copy the whole sequence folder untouched** to the working location and verify the copy
   byte for byte: `directory_manifest` gives md5 of every file inside every subdirectory
   (runs and `.M` folders); compare the top-level sequence files (.S, .LOG, .B,
   ACQUIRING.TXT, METHODS.REG) separately by md5. The source on the instrument side is never
   renamed or edited.
2. **Build the mapping** `{original folder: new folder}` from the header sample names
   (section 1), not from vial numbers.
3. **Rename on a copy**: `apply_rename_to_copy(src, dst, mapping)` builds a collision-free plan
   (`build_rename_plan`, which orders steps so no rename overwrites a folder a later step still
   needs, and reports cycles and duplicate targets as conflicts instead of executing them),
   copies the tree, renames inside the copy only, writes `_RELABEL_LOG.csv` into the copy and
   runs `verify_rename`. Folders left unrenamed are added as identity entries so verification
   covers them too.
4. **Judge the verification**: `verify_rename` returns `passed = True` only when there is no
   `differing` entry, no `unmapped` entry on either side and `src_bytes == dst_bytes`. An entry
   missing from the copy is reported under `differing` ("missing from copy"). If an aborted run
   was deliberately set aside after the copy, re-running `verify_rename` with the full mapping
   shows it as exactly one `missing from copy` item (run it before step 5; moving `.M` folders
   out adds one item each). One expected entry per set-aside run is fine, anything else must
   be investigated. Do not "fix" the result by putting the aborted run back.
5. **Split the result into three roots** (section 5): the plain ChemStation-visible run
   folder, the analysis folder, and the provenance archive. `apply_rename_to_copy` leaves the
   sequence files and `_RELABEL_LOG.csv` next to the renamed runs; move them to the provenance
   archive before the folder is opened in ChemStation.
6. **Write a sample map** (CSV) in the analysis or provenance root with at least:
   `orig_folder`, `header_sample`, `folder` (the current directory name), `complete`, plus
   whatever the analysis needs (acquisition time, end time, dilution factor, note). Rules L7 and
   L10 read `folder`, `header_sample`, `complete` and `orig_folder`.
7. **Run the layout checker** (section 8) and keep its JSON report with the analysis.

Scripts that locate the run folder relative to their own location break when folders are
moved in step 5; give analysis scripts an explicit path to the run folder instead.

## 4. Naming scheme

```
<experiment>_<minutes>_<condition>_<E|NE>_<replicate>_<original id>.D
```

- `<minutes>` is zero-padded to four digits followed by `min` (`0030min`, `0480min`), so an
  alphabetical listing -- which is what the ChemStation navigation table shows -- sorts by
  experiment, then time, then condition.
- `E` = treated sample, `NE` = its no-treatment control.
- `<replicate>` = `R1`, `R2`, ...
- `<original id>` keeps the header sample name (or its short form), so every renamed run can
  be traced back to the original injection without a lookup table.
- Use only `[A-Za-z0-9_]`, keep names unique ignoring case (Windows file systems are
  case-insensitive; rule L6) and keep them short: ChemStation upper-cases names in its tree,
  and very long names are impractical in its tables; check that the longest name you intend
  to use displays in full before adopting the scheme.
- The packaged spec's L5 pattern expects an `EXP<number>_` prefix and an original id of the
  form `<letter><digits>`; a lab with a different scheme overrides the pattern in its private
  spec overlay (section 8).

## 5. Keep the ChemStation-visible folder plain; three separate roots

- **Run folder (raw, ChemStation-visible):** a folder that ChemStation should list as runs
  holds **only `.D` directories** (rules L1, L2). Sequence summary (`.S`), log (`.LOG`),
  batch (`.B`), `ACQUIRING.TXT`, `METHODS.REG` and method folders (`.M`) must not sit next to
  renamed runs; neither may CSV files, READMEs or aborted runs (rule L4). Observed behaviour:
  a folder holding renamed `.D` runs together with the original sequence files and a CSV was
  **not listed at all** in the offline Data Analysis navigation tree, while a folder holding
  only `.D` directories was listed as single runs. The batch file carries the original
  data-file names, which no longer exist after a rename. Instrument-native sequence folders
  that were never renamed are legitimate and out of scope for L1/L2; do not point `check` at
  them (their sequence files would be reported as L2 errors).
- **Analysis root:** peak lists, re-quantitation tables, figures, method YAMLs, scripts and
  the sample map live in a separate tree, never inside the raw data tree (rule L8 scans a data
  root for such files).
- **Provenance archive:** the untouched copy with the original folder names, the sequence
  files, `_RELABEL_LOG.csv`, aborted runs and any pre-change snapshot of the run folder. Mark
  it as not-for-analysis so nobody opens it by mistake.

```
<data_root>/<project>/<sequence_label>/          .D directories only
<analysis_root>/<sequence_label>/                sample map, rename log, results, scripts
<archive_root>/<sequence_label>/
    raw_original_names/                          untouched copy, original names
    sequence_metadata/                           .S .LOG .B ACQUIRING.TXT METHODS.REG .M _RELABEL_LOG.csv
    aborted_runs/                                incomplete .D
```

## 6. Optional: rewrite the header sample name (copies only)

A folder rename does not change the sample name stored in the header, so ChemStation's
sample-name column keeps showing the original short name. If the readable name should also
appear there, the header field can be rewritten -- on the organized **copy only**, never on
the instrument data or the provenance copy. PeakPicker does not ship a writer for this
field; this section states what a writer must do and how to verify it.

Field facts (ChemStation "130" `.ch` header):

- Location: offset `0x35A` holds the character count (1 byte); the UTF-16LE text starts at
  `0x35B`. It is the only place in a `.D` found to hold the sample name (the other files in
  the run folder were searched in ASCII and UTF-16); some third-party readers call this field
  `notebook`.
- Capacity: the field occupies the fixed region `0x35A`-`0x757` (the next field starts at
  `0x758`) and is zero-padded after the string, with no terminator. The count byte bounds the
  length at 255 characters (511 bytes, inside the region). Use names no longer than those you
  have seen displayed correctly in ChemStation.
- No checksum was found: every header byte that differs between runs of one sequence is
  explained by a known field (vial and sequence line, end time and signal extrema, sample
  name, date, first data point).

Writing procedure:

1. Write `len(name)` at `0x35A`, `name` encoded as UTF-16LE from `0x35B`, and zeros for the
   rest of the region up to `0x757`. The file size must not change. Only those bytes change.
2. Check that the new name is at most the length chosen above and uses only
   `[A-Za-z0-9_]`.

Verification (per run, against the provenance copy):

- md5 of the whole file with `0x35A`-`0x757` masked (zeroed on both sides) equals the
  original; rule L10 does this when the spec sets
  `masked_ranges: {"RID1A.ch": [[858, 1879]]}` (decimal for `0x35A`-`0x757`).
- The signal data region (from `0x1800`) is byte-identical, and a parser returns identical
  time and signal arrays.
- The date and method fields are unchanged, and every other file in the `.D` is md5-identical.
- `read_run` returns the new name as `sample`.

Status: confirmed in ChemStation Data Analysis - after the folder rename and the header
rewrite, the file list and the Sample Name column both show the readable name. Rule L9
(`observed`, severity warning) therefore runs by default and warns for every run whose header
sample name differs from its folder label. Record the original header names in the sample map
(`header_sample`) so the change is reversible.

## 7. Verification summary

| What | How |
|---|---|
| copy equals source | `directory_manifest` / `verify_rename` (every file in every subdirectory) plus md5 of the top-level sequence files |
| rename lost nothing | `verify_rename`: `passed`, one expected `differing` item per run set aside |
| renamed runs equal provenance | rule L10 with `--map` and `--raw` |
| header name rewritten correctly | L10 with the name field masked; data region and parsed arrays identical |
| run folder is plain | rules L1, L2 |
| no aborted runs visible | rule L4 |
| identity preserved | rule L7 (header sample equals the map's `header_sample` or the folder label) |
| name shown in ChemStation | rule L9 (warning until the header is rewritten) |

## 8. Running `chem_layout_qc`

The checker is strictly read-only; it writes nothing next to the data (the JSON report goes
where `--json` points).

```bash
# one run folder: layout, completeness, names, identity, provenance
python src/peakpicker/infrastructure/file_readers/chem_layout_qc.py check <run_folder> \
    --map <analysis_root>/<sequence_label>/sample_map.csv \
    --raw <archive_root>/<sequence_label>/raw_original_names \
    --json <analysis_root>/<sequence_label>/layout_qc.json

# a whole data root: analysis outputs inside the raw tree (rule L8)
python src/peakpicker/infrastructure/file_readers/chem_layout_qc.py tree <data_root>
```

- Rules L7 and L10 run only when `--map` (and, for L10, `--raw`) are given; otherwise they are
  listed under "skipped" with the missing option.
- A rule whose status in the spec is `pending_evidence` or `disabled` is never run and is
  reported under "skipped".
- **Spec resolution:** `--spec <file>`, else the environment variable `CHEM_LAYOUT_SPEC`,
  else a private overlay `methods/chem_layout_spec.lab.yaml` in the repository checkout if it
  exists, else the packaged generic `chem_layout_spec.yaml`. Keep lab-specific settings
  (experiment-name pattern for L5, declared runtimes for L4, masked ranges for L10) in the
  private overlay, not in the packaged spec.
- **Exit codes:** `0` = no errors (warnings allowed), `1` = findings (errors, or warnings too
  with `--strict`), `2` = usage, IO or spec problem.

## 9. Worked example (synthetic)

All names and numbers below are synthetic (the example was executed on generated files
with the packaged spec). A sequence `SEQ_DEMO` produced six runs; vial 11 was used on
lines 1 and 4 for two different samples:

| orig_folder | header_sample | condition | E/NE | minutes | folder (new) |
|---|---|---|---|---|---|
| `011-0101.D` | `s1` | CondA | NE | 30 | `EXP01_0030min_CondA_NE_R1_s1.D` |
| `012-0201.D` | `s2` | CondA | E | 30 | `EXP01_0030min_CondA_E_R1_s2.D` |
| `013-0301.D` | `s3` | CondB | E | 30 | `EXP01_0030min_CondB_E_R1_s3.D` |
| `011-0401.D` | `s4` | CondA | NE | 120 | `EXP01_0120min_CondA_NE_R1_s4.D` |
| `012-0501.D` | `s5` | CondA | E | 120 | `EXP01_0120min_CondA_E_R1_s5.D` |
| `013-0601.D` | `s6` | CondB | E | 120 | (aborted) |

1. `scan_sequence` reads the header names: `011-0101.D` is `s1` and `011-0401.D` is `s4`, so the
   shared vial prefix `011` is not an identity. `013-0601.D` ends at 14.2 of a declared 30.0 min
   (47 %, synthetic) and is flagged incomplete.
2. The sequence folder is copied and verified by md5; `apply_rename_to_copy` renames five runs
   in the copy and its own verification passes. After `013-0601.D` is moved to the archive's
   `aborted_runs/`, re-running `verify_rename` with the full mapping reports one
   `missing from copy` item -- the expected one.
3. Sequence files and `_RELABEL_LOG.csv` move to `sequence_metadata/`; the sample map goes to
   the analysis root with `complete = False` for `013-0601.D`.
4. `chem_layout_qc.py check` on the run folder with `--map` and `--raw` exits `0`: five `.D`
   directories and nothing else, every header sample matches its map row, every run is
   byte-identical to its provenance copy. L9 reports five warnings (the headers still carry
   the short names); warnings do not change the exit code unless `--strict` is given, which
   exits `1`.
5. Had `SEQ_DEMO.S` been left in the run folder, L2 would report it as an error and the
   checker would exit `1`.
6. After the header names are rewritten as in section 6, the packaged spec (empty
   `masked_ranges`) reports every run under L10 as not byte-identical and exits `1`; with
   `masked_ranges: {"RID1A.ch": [[858, 1879]]}` in the overlay there are no findings (L7
   accepts the folder label as header name, L9 is satisfied) and it exits `0`.
