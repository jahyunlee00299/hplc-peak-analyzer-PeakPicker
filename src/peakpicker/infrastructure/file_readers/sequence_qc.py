"""
Sequence Integrity QC
=====================

Quality control for a ChemStation *sequence* directory, as opposed to a single
run. Answers three questions that must be settled before any peak in the
sequence is quantified:

1. Which runs were **aborted** mid-acquisition? An aborted run keeps its
   filename, so selecting data by name alone silently picks up a truncated
   trace. Detection uses the acquisition header, not ``RUN.LOG``: a truncated
   run has no usable ``RUN.LOG`` runtime at all (measured on four aborted runs),
   while the header still records how much signal was actually collected.

2. Are the sample **labels shifted**? A sequence started one index off produces
   files whose names are all wrong by a constant offset. The shift is invisible
   per-file and only shows up against a reference series.

3. Does a **rename preserve the bytes**? Renaming is done on a copy and then
   verified by md5 over every file, because a rename that loses data looks
   exactly like a rename that worked.

Why this is not folded into :class:`ChemstationReader`: that class reads one
chromatogram. These checks are properties of a *set* of runs and of the
filesystem layout around them, which is a different responsibility.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import re
import shutil
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ChemStation '130' header offsets (big-endian). Verified against Agilent
# ChemStation A.06.54 RID files.
_OFF_START_MS = 0x11A
_OFF_END_MS = 0x11E
_OFF_SAMPLE = 0x35A
_OFF_DATE = 0x957
_OFF_METHOD = 0xA0E
_DATA_START = 0x1800

#: A run shorter than this fraction of its method's nominal runtime was aborted.
DEFAULT_COMPLETE_FRACTION = 0.95


def _pascal_utf16(blob: bytes, offset: int) -> str:
    """Read ChemStation's length-prefixed UTF-16LE string."""
    try:
        length = blob[offset]
        raw = blob[offset + 1: offset + 1 + 2 * length]
        return raw.decode("utf-16-le", "ignore").strip()
    except (IndexError, ValueError):
        return ""


@dataclass
class RunInfo:
    """What the QC layer knows about one ``.D`` run."""

    path: Path
    name: str
    sample: str = ""
    date: str = ""
    method: str = ""
    start_min: Optional[float] = None
    end_min: Optional[float] = None
    nominal_min: Optional[float] = None
    readable: bool = False
    reason: str = ""

    @property
    def complete(self) -> bool:
        if not self.readable or self.end_min is None or not self.nominal_min:
            return False
        return self.end_min >= self.nominal_min * DEFAULT_COMPLETE_FRACTION

    @property
    def completion_ratio(self) -> Optional[float]:
        if self.end_min is None or not self.nominal_min:
            return None
        return self.end_min / self.nominal_min


class SequenceIntegrityChecker:
    """Detects aborted runs and duplicate labels in a sequence directory.

    ``nominal_runtimes`` maps a method filename to its expected runtime in
    minutes. When a method is unknown, the modal end-time of the runs sharing
    that method is used instead, so the check still works on an unfamiliar
    sequence.
    """

    def __init__(
        self,
        nominal_runtimes: Optional[Dict[str, float]] = None,
        complete_fraction: float = DEFAULT_COMPLETE_FRACTION,
        signal_file: str = "RID1A.ch",
    ):
        self.nominal_runtimes = dict(nominal_runtimes or {})
        self.complete_fraction = complete_fraction
        self.signal_file = signal_file

    # -- reading -----------------------------------------------------------

    def read_run(self, d_folder: Path) -> RunInfo:
        """Read acquisition metadata without decoding the whole signal."""
        d_folder = Path(d_folder)
        info = RunInfo(path=d_folder, name=d_folder.name)

        signal = d_folder / self.signal_file
        if not signal.exists():
            info.reason = f"{self.signal_file} 없음"
            return info
        if signal.stat().st_size <= _DATA_START:
            info.reason = f"데이터 영역 없음 ({signal.stat().st_size} bytes)"
            return info

        blob = signal.read_bytes()
        try:
            start = struct.unpack(">i", blob[_OFF_START_MS:_OFF_START_MS + 4])[0]
            end = struct.unpack(">i", blob[_OFF_END_MS:_OFF_END_MS + 4])[0]
        except struct.error as exc:
            info.reason = f"헤더 파싱 실패: {exc}"
            return info

        info.start_min = start / 60000.0
        info.end_min = end / 60000.0
        info.sample = _pascal_utf16(blob, _OFF_SAMPLE)
        info.date = _pascal_utf16(blob, _OFF_DATE)
        info.method = _pascal_utf16(blob, _OFF_METHOD)
        info.readable = True
        return info

    def scan_sequence(self, seq_dir: Path) -> List[RunInfo]:
        """Read every ``.D`` in one sequence directory and resolve runtimes."""
        seq_dir = Path(seq_dir)
        if not seq_dir.is_dir():
            raise FileNotFoundError(f"Sequence directory not found: {seq_dir}")

        runs = [
            self.read_run(item)
            for item in sorted(seq_dir.iterdir())
            if item.is_dir() and item.suffix.lower() == ".d"
        ]
        self._resolve_nominal(runs)
        return runs

    def _resolve_nominal(self, runs: Iterable[RunInfo]) -> None:
        """Assign each run its method's nominal runtime.

        Falls back to the modal end-time among runs sharing a method, so an
        unknown method still yields a usable completeness test. The mode is used
        rather than the max because a single over-long run would otherwise mark
        every normal run incomplete.
        """
        by_method: Dict[str, List[float]] = {}
        for run in runs:
            if run.readable and run.end_min is not None:
                by_method.setdefault(run.method, []).append(run.end_min)

        modes: Dict[str, float] = {}
        for method, ends in by_method.items():
            rounded = [round(e) for e in ends]
            modes[method] = float(max(set(rounded), key=rounded.count))

        for run in runs:
            self_declared = self.nominal_runtimes.get(run.method)
            run.nominal_min = self_declared or modes.get(run.method)

    # -- reporting ---------------------------------------------------------

    def find_aborted(self, runs: Sequence[RunInfo]) -> List[RunInfo]:
        """Runs that are unreadable or stopped short of their method time."""
        return [r for r in runs if not r.complete]

    def find_duplicate_labels(
        self, runs: Sequence[RunInfo]
    ) -> Dict[str, List[RunInfo]]:
        """Names appearing more than once, e.g. an abort plus its re-run.

        Callers usually want the complete member of each group; the aborted one
        shares the filename and would otherwise be selected by name alone.
        """
        groups: Dict[str, List[RunInfo]] = {}
        for run in runs:
            groups.setdefault(run.name, []).append(run)
        return {name: g for name, g in groups.items() if len(g) > 1}

    def report(self, seq_dir: Path) -> Dict[str, object]:
        runs = self.scan_sequence(seq_dir)
        aborted = self.find_aborted(runs)
        return {
            "sequence": str(seq_dir),
            "n_runs": len(runs),
            "n_complete": sum(1 for r in runs if r.complete),
            "aborted": aborted,
            "duplicates": self.find_duplicate_labels(runs),
            "runs": runs,
        }


_INDEX_RE = re.compile(r"^(?P<stem>.*?)(?P<idx>\d+)$")


def _split_index(name: str) -> Optional[Tuple[str, int]]:
    """Split ``RS_FERM_12.D`` into ``('RS_FERM_', 12)``."""
    base = name[:-2] if name.lower().endswith(".d") else name
    m = _INDEX_RE.match(base)
    if not m:
        return None
    return m.group("stem"), int(m.group("idx"))


@dataclass
class ShiftEvidence:
    """How well a candidate offset aligns a series against a reference."""

    offset: int
    n_compared: int
    median_ratio: float
    within_tolerance: int

    @property
    def score(self) -> Tuple[int, float]:
        """Rank key: agreement count first, then closeness of the median."""
        return self.within_tolerance, -abs(self.median_ratio - 1.0)


def detect_label_shift(
    series: Dict[int, float],
    reference: Dict[int, float],
    candidate_offsets: Iterable[int] = (-2, -1, 0, 1, 2),
    tolerance: float = 0.20,
) -> List[ShiftEvidence]:
    """Find the index offset that best aligns ``series`` onto ``reference``.

    Both maps are ``{index: quantity}`` where the quantity is comparable across
    the two series - typically the integrated area of one analyte. The offset
    scoring ignores indices whose reference value is non-positive, so early
    time points below the quantitation limit cannot drive the alignment.

    Returns every candidate scored, best first, so the caller can see *how much*
    better the winner is rather than trusting a bare answer.
    """
    import statistics

    results: List[ShiftEvidence] = []
    for offset in candidate_offsets:
        ratios: List[float] = []
        for idx, value in series.items():
            ref = reference.get(idx + offset)
            if ref is None or ref <= 0 or value <= 0:
                continue
            ratios.append(value / ref)
        if len(ratios) < 3:
            continue
        median = statistics.median(ratios)
        agree = sum(1 for r in ratios if abs(r - 1.0) <= tolerance)
        results.append(ShiftEvidence(offset, len(ratios), median, agree))

    results.sort(key=lambda e: e.score, reverse=True)
    return results


@dataclass
class RenamePlan:
    """An ordered, collision-free set of directory renames."""

    mapping: Dict[str, str] = field(default_factory=dict)
    steps: List[Tuple[str, str]] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return not self.conflicts


def build_rename_plan(existing: Iterable[str], mapping: Dict[str, str]) -> RenamePlan:
    """Order renames so no step overwrites a directory a later step still needs.

    Renaming ``0->1, 1->2, ...`` in ascending order destroys each target before
    it is read. Sorting by descending destination index avoids that; a cycle
    (``a->b`` and ``b->a``) cannot be ordered at all and is reported as a
    conflict rather than executed halfway.
    """
    present = set(existing)
    plan = RenamePlan(mapping=dict(mapping))

    targets: Dict[str, List[str]] = {}
    for src, dst in mapping.items():
        targets.setdefault(dst, []).append(src)
    for dst, srcs in targets.items():
        if len(srcs) > 1:
            plan.conflicts.append(
                f"여러 원본이 같은 이름으로: {sorted(srcs)} -> {dst}"
            )

    def sort_key(item: Tuple[str, str]) -> Tuple[int, str]:
        parsed = _split_index(item[1])
        return (-parsed[1], item[1]) if parsed else (0, item[1])

    pending = [(s, d) for s, d in mapping.items() if s in present]
    pending.sort(key=sort_key)

    # Simulate to catch orderings that still collide (e.g. a rename cycle).
    state = set(present)
    for src, dst in pending:
        if dst in state and dst not in {s for s, _ in pending}:
            plan.conflicts.append(f"대상이 이미 존재하며 이동 예정도 아님: {dst}")
            continue
        if dst in state:
            plan.conflicts.append(f"순서로 해소되지 않는 충돌(순환 의심): {src} -> {dst}")
            continue
        state.discard(src)
        state.add(dst)
        plan.steps.append((src, dst))

    missing = [s for s in mapping if s not in present]
    for name in missing:
        logger.warning("rename 원본 없음: %s", name)
    return plan


def _md5(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def directory_manifest(root: Path) -> Dict[str, Dict[str, Tuple[str, int]]]:
    """``{subdir: {relative_path: (md5, size)}}`` for every subdirectory."""
    root = Path(root)
    manifest: Dict[str, Dict[str, Tuple[str, int]]] = {}
    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        files: Dict[str, Tuple[str, int]] = {}
        for path in item.rglob("*"):
            if path.is_file():
                rel = path.relative_to(item).as_posix()
                files[rel] = (_md5(path), path.stat().st_size)
        manifest[item.name] = files
    return manifest


def verify_rename(
    src_root: Path,
    dst_root: Path,
    mapping: Dict[str, str],
) -> Dict[str, object]:
    """Confirm a renamed copy is byte-identical to its source.

    ``mapping`` must cover **every** subdirectory, including ones deliberately
    left unrenamed (method ``.M`` folders in particular). An entry missing from
    the mapping is reported under ``unmapped`` instead of being skipped - a
    silently skipped folder is what turns a passing check into a false failure.
    """
    src_manifest = directory_manifest(src_root)
    dst_manifest = directory_manifest(dst_root)

    identical: List[Tuple[str, str, int]] = []
    differing: List[Dict[str, object]] = []

    for src_name, dst_name in sorted(mapping.items()):
        if src_name not in src_manifest:
            differing.append({"src": src_name, "dst": dst_name,
                              "issue": "원본에 없음"})
            continue
        if dst_name not in dst_manifest:
            differing.append({"src": src_name, "dst": dst_name,
                              "issue": "사본에 없음"})
            continue
        left, right = src_manifest[src_name], dst_manifest[dst_name]
        if left == right:
            identical.append((src_name, dst_name, len(left)))
        else:
            differing.append({
                "src": src_name,
                "dst": dst_name,
                "issue": "내용 불일치",
                "only_in_src": sorted(set(left) - set(right))[:5],
                "only_in_dst": sorted(set(right) - set(left))[:5],
                "changed": sorted(k for k in set(left) & set(right)
                                  if left[k] != right[k])[:5],
            })

    unmapped_src = sorted(set(src_manifest) - set(mapping))
    unmapped_dst = sorted(set(dst_manifest) - set(mapping.values()))

    def total(manifest, names):
        return sum(size for name in names
                   for _, size in manifest.get(name, {}).values())

    src_bytes = total(src_manifest, mapping.keys())
    dst_bytes = total(dst_manifest, mapping.values())

    return {
        "identical": identical,
        "differing": differing,
        "unmapped_src": unmapped_src,
        "unmapped_dst": unmapped_dst,
        "src_bytes": src_bytes,
        "dst_bytes": dst_bytes,
        "passed": (not differing and not unmapped_src and not unmapped_dst
                   and src_bytes == dst_bytes),
    }


def apply_rename_to_copy(
    src_dir: Path,
    dst_dir: Path,
    mapping: Dict[str, str],
    log_name: str = "_RELABEL_LOG.csv",
) -> Dict[str, object]:
    """Copy a sequence, rename inside the copy, then verify against the source.

    The source is never modified, so a bad mapping is undone by deleting the
    copy. Verification covers unrenamed subdirectories too, which is why the
    identity entries are added to the mapping before checking.
    """
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    if dst_dir.exists():
        raise FileExistsError(f"대상이 이미 존재합니다: {dst_dir}")

    names = [p.name for p in src_dir.iterdir() if p.is_dir()]
    plan = build_rename_plan(names, mapping)
    if not plan.is_safe:
        raise ValueError("rename 계획이 안전하지 않습니다: " + "; ".join(plan.conflicts))

    shutil.copytree(src_dir, dst_dir)

    applied: List[Tuple[str, str, str]] = []
    for src_name, dst_name in plan.steps:
        source = dst_dir / src_name
        target = dst_dir / dst_name
        if not source.exists():
            applied.append((src_name, dst_name, "SKIP_NO_SRC"))
            continue
        if target.exists():
            applied.append((src_name, dst_name, "FAIL_DST_EXISTS"))
            break
        source.rename(target)
        applied.append((src_name, dst_name, "OK"))

    with open(dst_dir / log_name, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["original", "renamed", "status"])
        writer.writerows(applied)

    full_mapping = dict(mapping)
    for name in names:
        full_mapping.setdefault(name, name)

    verification = verify_rename(src_dir, dst_dir, full_mapping)
    return {"applied": applied, "verification": verification, "plan": plan}
