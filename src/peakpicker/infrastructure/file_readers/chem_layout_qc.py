"""ChemStation folder layout QC.

Checks that a folder we hand to Agilent ChemStation (offline Data Analysis, opened from the ChemStation data root) has
the layout ChemStation displays, that its runs are complete, that sample identity survived a rename, and (optionally)
that a whole data tree holds raw data only.

The rules and their evidence live in ``chem_layout_spec.yaml`` (the SSOT). This module only executes the spec:
a rule whose status is ``pending_evidence`` or ``disabled`` is reported under ``rules_skipped`` and never run.

Strictly READ-ONLY: nothing is created, renamed or written next to the data (the JSON report goes where the caller
points ``--json``).

CLI::

    python chem_layout_qc.py check <folder> [--map sample_map.csv] [--raw <provenance dir>] [--spec spec.yaml]
                                            [--json report.json] [--strict]
    python chem_layout_qc.py tree  <root>   [--spec spec.yaml] [--json report.json] [--strict]

Exit codes: 0 = no error (warnings allowed unless ``--strict``), 1 = findings, 2 = usage / IO / spec problem.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import importlib.util
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml

_HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = _HERE / "chem_layout_spec.yaml"

EXIT_OK, EXIT_FINDINGS, EXIT_USAGE = 0, 1, 2
SEVERITIES = ("error", "warning", "info")
STATUSES = ("observed", "pending_evidence", "disabled")


class SpecError(ValueError):
    """The spec file is unreadable, malformed or names an unknown rule."""


def _sequence_qc():
    """Load the sibling ``sequence_qc`` module whether or not the package imports cleanly."""
    try:
        from . import sequence_qc  # type: ignore
        return sequence_qc
    except Exception:  # noqa: BLE001 - run by file path, or package chain unavailable
        pass
    existing = sys.modules.get("sequence_qc")
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location("sequence_qc", _HERE / "sequence_qc.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["sequence_qc"] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class Finding:
    rule: str
    severity: str
    path: str
    message: str


@dataclass
class Report:
    target: str
    mode: str
    spec_version: int
    spec_path: str = ""
    runs: int = 0
    rules_run: List[str] = field(default_factory=list)
    rules_skipped: List[dict] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    def exit_code(self, strict: bool = False) -> int:
        if self.errors or (strict and self.warnings):
            return EXIT_FINDINGS
        return EXIT_OK

    def to_dict(self) -> dict:
        return {
            "target": self.target, "mode": self.mode, "spec_version": self.spec_version, "spec_path": self.spec_path, "runs": self.runs,
            "summary": {"errors": self.errors, "warnings": self.warnings, "findings": len(self.findings)},
            "rules_run": self.rules_run, "rules_skipped": self.rules_skipped,
            "findings": [asdict(f) for f in self.findings],
        }

    def render(self) -> str:
        lines = [f"[{self.mode}] {self.target}  runs={self.runs}  errors={self.errors}  warnings={self.warnings}"]
        lines.append(f"  spec: {self.spec_path or '-'}")
        lines.append(f"  rules run: {', '.join(self.rules_run) or '-'}")
        for s in self.rules_skipped:
            lines.append(f"  skipped {s['id']}: {s['reason']}")
        for f in self.findings:
            lines.append(f"  {f.severity.upper():7} {f.rule:4} {f.path}  {f.message}")
        if not self.findings:
            lines.append("  no findings")
        return "\n".join(lines)


# --------------------------------------------------------------------------------------------- spec

def resolve_spec_path(explicit: Optional[Path] = None) -> Path:
    """Spec search order: explicit path, $CHEM_LAYOUT_SPEC, private overlay <repo>/methods/chem_layout_spec.lab.yaml, packaged default."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("CHEM_LAYOUT_SPEC")
    if env:
        return Path(env)
    overlay = _HERE.parents[3] / "methods" / "chem_layout_spec.lab.yaml"
    return overlay if overlay.exists() else DEFAULT_SPEC


def load_spec(path: Optional[Path] = None) -> dict:
    path = resolve_spec_path(path)
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SpecError(f"cannot read spec {path}: {exc}") from exc
    if not isinstance(spec, dict) or not isinstance(spec.get("rules"), list) or "spec_version" not in spec:
        raise SpecError(f"spec {path} needs spec_version and a rules list")
    seen = set()
    for rule in spec["rules"]:
        rid = rule.get("id") if isinstance(rule, dict) else None
        if not rid or rid in seen:
            raise SpecError(f"rule without id or duplicated id: {rid!r}")
        seen.add(rid)
        if rid not in RULES:
            raise SpecError(f"unknown rule id {rid!r} (known: {', '.join(sorted(RULES))})")
        if rule.get("severity") not in SEVERITIES:
            raise SpecError(f"{rid}: severity must be one of {SEVERITIES}")
        if rule.get("status") not in STATUSES:
            raise SpecError(f"{rid}: status must be one of {STATUSES}")
    spec["_path"] = str(path)
    return spec


# --------------------------------------------------------------------------------------------- context

def _is_run_dir(p: Path) -> bool:
    return p.is_dir() and p.suffix.lower() == ".d"


@dataclass
class Ctx:
    folder: Path
    entries: List[Path]
    run_dirs: List[Path]
    params: dict
    severity: str
    spec: dict
    map_path: Optional[Path] = None
    raw_dir: Optional[Path] = None

    def finding(self, rule: str, path: Path | str, message: str, severity: Optional[str] = None) -> Finding:
        return Finding(rule, severity or self.severity, str(path), message)


def _rule_params(spec: dict, rid: str) -> dict:
    for rule in spec["rules"]:
        if rule["id"] == rid:
            return rule.get("params") or {}
    return {}


def _matches(name: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatch(name.upper(), pat.upper()) for pat in patterns)


# --------------------------------------------------------------------------------------------- rules (one folder)

def rule_l1(c: Ctx) -> List[Finding]:
    l2 = _rule_params(c.spec, "L2")
    seq_files, seq_dirs = l2.get("file_patterns", []), l2.get("dir_patterns", [])
    out = []
    for e in c.entries:
        if _is_run_dir(e):
            continue
        if e.is_file() and _matches(e.name, seq_files):
            continue          # reported by L2
        if e.is_dir() and _matches(e.name, seq_dirs):
            continue
        kind = "directory" if e.is_dir() else "file"
        if e.suffix.lower() == ".d" and e.is_file():
            out.append(c.finding("L1", e, f"'{e.name}' is a FILE named like a run; ChemStation runs are .D directories"))
        else:
            out.append(c.finding("L1", e, f"non-run {kind} '{e.name}' beside the .D runs; a plain run folder holds only .D directories"))
    return out


def rule_l2(c: Ctx) -> List[Finding]:
    fp, dp = c.params.get("file_patterns", []), c.params.get("dir_patterns", [])
    out = []
    for e in c.entries:
        if _is_run_dir(e):
            continue
        if (e.is_file() and _matches(e.name, fp)) or (e.is_dir() and _matches(e.name, dp)):
            out.append(c.finding("L2", e, f"sequence/method file '{e.name}' next to the runs; move it to the provenance archive"))
    return out


def rule_l3(c: Ctx) -> List[Finding]:
    globs = c.params.get("signal_globs", ["*.ch"])
    expected = c.params.get("expected_files", [])
    exp_sev = c.params.get("expected_severity", "warning")
    out = []
    for d in c.run_dirs:
        names = [p.name for p in d.iterdir() if p.is_file()]
        if not any(_matches(n, globs) for n in names):
            out.append(c.finding("L3", d, "run has no signal file (*.ch)"))
        for want in expected:
            if not any(n.upper() == want.upper() for n in names):
                out.append(c.finding("L3", d, f"expected file {want} missing", exp_sev))
    return out


def rule_l4(c: Ctx) -> List[Finding]:
    seqqc = _sequence_qc()
    signal = c.params.get("signal_file", "RID1A.ch")
    checker = seqqc.SequenceIntegrityChecker(
        nominal_runtimes=c.params.get("nominal_min_by_method") or {},
        complete_fraction=float(c.params.get("complete_fraction", 0.95)), signal_file=signal)
    out = []
    for r in checker.scan_sequence(c.folder):
        if r.complete:
            continue
        if not r.readable:
            if signal in (r.reason or ""):
                continue      # missing signal is L3's finding
            out.append(c.finding("L4", r.path, f"header unreadable: {r.reason}"))
            continue
        ratio = r.completion_ratio
        pct = f"{ratio * 100:.0f} %" if ratio is not None else "unknown"
        out.append(c.finding("L4", r.path, f"aborted run: {r.end_min:.2f} of {r.nominal_min or 0:.2f} min ({pct}); keep it out of the ChemStation tree"))
    return out


def rule_l5(c: Ctx) -> List[Finding]:
    prefix = re.compile(c.params.get("applies_to_prefix", "^$"))
    pats = [re.compile(p) for p in c.params.get("patterns", [])]
    out = []
    for d in c.run_dirs:
        if prefix.match(d.name) and not any(p.match(d.name) for p in pats):
            out.append(c.finding("L5", d, "name does not follow <exp>_<min>_<arm/TCA>_<E|NE>_<rep>_<sampleid>.D"))
    return out


def rule_l6(c: Ctx) -> List[Finding]:
    out, seen = [], {}
    for d in c.run_dirs:
        key = d.name.lower()
        if key in seen:
            out.append(c.finding("L6", d, f"name collides (ignoring case) with '{seen[key]}'"))
        seen[key] = d.name
    limit = int(c.params.get("max_path_chars", 200))
    sev = c.params.get("path_length_severity", "warning")
    for d in c.run_dirs:
        n = len(str(d.resolve() / "RID1A.ch"))
        if n > limit:
            out.append(c.finding("L6", d, f"path is {n} characters (limit {limit})", sev))
    return out


def rule_l9(c: Ctx) -> List[Finding]:
    """Header sample name equals the folder label. Off until the spec marks it observed."""
    checker = _sequence_qc().SequenceIntegrityChecker()
    out = []
    for d in c.run_dirs:
        info = checker.read_run(d)
        if info.readable and info.sample != d.name[:-2]:
            out.append(c.finding("L9", d, f"header sample '{info.sample}' differs from folder label '{d.name[:-2]}'"))
    return out


def _read_map(path: Path, folder_col: str, header_col: str, complete_col: str) -> List[dict]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for col in (folder_col, header_col):
        if rows and col not in rows[0]:
            raise SpecError(f"map {path} has no column {col!r}")
    return rows


def rule_l7(c: Ctx) -> List[Finding]:
    if not c.map_path:
        return []
    fc, hc, cc = (c.params.get(k, d) for k, d in (("folder_column", "folder"), ("header_column", "header_sample"), ("complete_column", "complete")))
    rows = _read_map(c.map_path, fc, hc, cc)
    by_folder = {r[fc]: r for r in rows if r.get(fc)}
    seqqc = _sequence_qc()
    checker = seqqc.SequenceIntegrityChecker()
    out, present = [], set()
    for d in c.run_dirs:
        present.add(d.name)
        row = by_folder.get(d.name)
        if row is None:
            out.append(c.finding("L7", d, "run folder is not in the sample map"))
            continue
        info = checker.read_run(d)
        if info.readable and info.sample not in (row[hc], d.name[:-2]):
            out.append(c.finding("L7", d, f"header sample '{info.sample}' is neither the recorded original '{row[hc]}' nor the folder label (vial numbers are reused; header name is the identity)"))
    for r in rows:
        done = str(r.get(cc, "True")).strip().lower() in ("true", "1", "yes")
        if done and r.get(fc) and r[fc] not in present:
            out.append(c.finding("L7", c.folder / r[fc], "map lists a complete run that is not in the folder"))
    return out


def _same_outside_mask(a: Path, b: Path, ranges: List[List[int]]) -> bool:
    """True when two files are equal after zeroing the inclusive byte ranges (e.g. a rewritten name field); a size change never is."""
    if not ranges or not a.is_file() or not b.is_file():
        return False
    x, y = bytearray(a.read_bytes()), bytearray(b.read_bytes())
    for lo, hi in ranges:
        x[lo:hi + 1] = bytes(len(x[lo:hi + 1]))
        y[lo:hi + 1] = bytes(len(y[lo:hi + 1]))
    return x == y


def rule_l10(c: Ctx) -> List[Finding]:
    if not (c.map_path and c.raw_dir):
        return []
    seqqc = _sequence_qc()
    fc = c.params.get("folder_column", "folder")
    rows = _read_map(c.map_path, fc, "header_sample", "complete")
    raw_man = seqqc.directory_manifest(c.raw_dir)
    dst_man = seqqc.directory_manifest(c.folder)
    masked = c.params.get("masked_ranges") or {}
    out = []
    for r in rows:
        if str(r.get("complete", "True")).strip().lower() not in ("true", "1", "yes"):
            continue
        orig, new = r.get("orig_folder", ""), r.get(fc, "")
        if orig not in raw_man:
            out.append(c.finding("L10", c.raw_dir / orig, "provenance copy of this run is missing"))
            continue
        if new not in dst_man:
            out.append(c.finding("L10", c.folder / new, "run missing from the folder"))
            continue
        if raw_man[orig] != dst_man[new]:
            diff = sorted(set(raw_man[orig]) ^ set(dst_man[new]) | {k for k in raw_man[orig] if k in dst_man[new] and raw_man[orig][k] != dst_man[new][k]})
            diff = [k for k in diff if not _same_outside_mask(c.raw_dir / orig / k, c.folder / new / k, masked.get(k, []))]
            if diff:
                out.append(c.finding("L10", c.folder / new, f"not byte-identical to provenance copy ({', '.join(diff[:3])})"))
    return out


RULES: Dict[str, Callable[[Ctx], List[Finding]]] = {
    "L1": rule_l1, "L2": rule_l2, "L3": rule_l3, "L4": rule_l4, "L5": rule_l5, "L6": rule_l6, "L7": rule_l7,
    "L8": lambda c: [], "L9": rule_l9, "L10": rule_l10,
}
FOLDER_RULES = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L9", "L10")
REQUIRES = {"L7": ("map_path",), "L10": ("map_path", "raw_dir")}


# --------------------------------------------------------------------------------------------- entry points

def check_folder(folder: Path, spec: Optional[dict] = None, map_path: Optional[Path] = None, raw_dir: Optional[Path] = None) -> Report:
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"not a directory: {folder}")
    spec = spec or load_spec()
    entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
    run_dirs = [e for e in entries if _is_run_dir(e)]
    report = Report(str(folder), "check", int(spec["spec_version"]), spec.get("_path", ""), runs=len(run_dirs))
    if not run_dirs:
        report.findings.append(Finding("L0", "info", str(folder), "no .D runs directly in this folder; nothing to check (use 'tree' for a data root)"))
        return report
    for rule in spec["rules"]:
        rid = rule["id"]
        if rid not in FOLDER_RULES:
            continue
        if rule["status"] != "observed":
            report.rules_skipped.append({"id": rid, "reason": rule["status"]})
            continue
        ctx = Ctx(folder, entries, run_dirs, rule.get("params") or {}, rule["severity"], spec, map_path, raw_dir)
        missing = [name for name in REQUIRES.get(rid, ()) if getattr(ctx, name) is None]
        if missing:
            report.rules_skipped.append({"id": rid, "reason": "needs " + " and ".join("--" + m.replace("_path", "").replace("_dir", "") for m in missing)})
            continue
        report.rules_run.append(rid)
        report.findings.extend(RULES[rid](ctx))
    return report


def check_tree(root: Path, spec: Optional[dict] = None) -> Report:
    """L8: analysis outputs outside .D folders in a raw data tree (never descends into .D)."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"not a directory: {root}")
    spec = spec or load_spec()
    rule = next((r for r in spec["rules"] if r["id"] == "L8"), None)
    report = Report(str(root), "tree", int(spec["spec_version"]), spec.get("_path", ""))
    if rule is None or rule["status"] != "observed":
        report.rules_skipped.append({"id": "L8", "reason": (rule or {}).get("status", "absent")})
        return report
    p = rule.get("params") or {}
    ext = {e.lower() for e in p.get("analysis_extensions", [])}
    if p.get("csv_extension_is_analysis"):
        ext.add(".csv")
    ignore = {n.lower() for n in p.get("ignore_names", [])}
    dir_re = re.compile(p.get("analysis_dir_regex", r"^$"))
    report.rules_run.append("L8")
    for cur, dirs, files in os.walk(root):
        runs_here = [d for d in dirs if d.lower().endswith(".d")]
        report.runs += len(runs_here)
        dirs[:] = [d for d in dirs if not d.lower().endswith(".d")]
        for d in list(dirs):
            if dir_re.search(d):
                report.findings.append(Finding("L8", rule["severity"], str(Path(cur) / d), "analysis-like directory inside the raw data tree"))
                dirs.remove(d)       # count it once, do not list its contents
        for f in files:
            if Path(f).suffix.lower() in ext and f.lower() not in ignore:
                report.findings.append(Finding("L8", rule["severity"], str(Path(cur) / f), "analysis output file inside the raw data tree"))
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="ChemStation folder layout QC (read-only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "tree"):
        sp = sub.add_parser(name)
        sp.add_argument("target")
        sp.add_argument("--spec", default=None)
        sp.add_argument("--json", dest="json_out", default=None)
        sp.add_argument("--strict", action="store_true", help="warnings also give exit 1")
        if name == "check":
            sp.add_argument("--map", default=None)
            sp.add_argument("--raw", default=None)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:            # argparse exits 2 on usage errors already
        return int(exc.code or 0)
    try:
        spec = load_spec(args.spec)
        if args.cmd == "check":
            report = check_folder(Path(args.target), spec, Path(args.map) if args.map else None, Path(args.raw) if args.raw else None)
        else:
            report = check_tree(Path(args.target), spec)
    except (SpecError, FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(report.render())
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report.exit_code(args.strict)


if __name__ == "__main__":
    sys.exit(main())
