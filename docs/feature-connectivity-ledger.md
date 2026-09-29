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
  provenance md5 clean) and a raw-tree scan of about 20 000 runs.
- **Refutation**: mutation check (17 deliberate breakages of the implementation, each killed by the tests after one test was added for
  spec status validation); adverse fixtures (sequence files, stray/hidden files, a file named like a run, lower-case `.d`, empty folder,
  runs one level down, missing/truncated signal, aborted run alone in a folder, vial-reuse header mismatch, missing map rows, flipped byte in a
  copy, malformed/unknown spec, read-only guarantee by md5 snapshot). Known limitation, tested and documented: a single run with an
  unknown method cannot be judged complete without a declared runtime.
- **Regress**: neighbouring `test_sequence_qc.py` (20 tests) unchanged and green.
- **Connect**: `sequence_qc.py` docstring and `PROJECT_STRUCTURE.md` reference the checker; private overlay spec holds the lab names.
- **Deferred**: rule L9 (header sample name equals readable label) stays `pending_evidence` until it is established what the
  ChemStation navigation table displays; wiring the call into the organizing recipe and registering the spec with `fiducial pointers`.
