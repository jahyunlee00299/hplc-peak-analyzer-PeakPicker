"""Tests for sequence-level integrity QC.

The adverse cases matter more than the happy path here: every one of these
failures was observed on real acquisition data before the module existed.
"""

import importlib.util
import struct
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

# Loaded by file path rather than by package import: `peakpicker.infrastructure`
# eagerly imports the plot exporter, which needs `peakpicker.utils` - a module
# that does not exist in this tree. That breakage predates this file and is
# unrelated to sequence QC, so the tests reach the module directly instead of
# depending on (or silently "fixing") an unrelated package's import chain.
_spec = importlib.util.spec_from_file_location(
    "sequence_qc",
    _SRC / "peakpicker/infrastructure/file_readers/sequence_qc.py",
)
sequence_qc = importlib.util.module_from_spec(_spec)
# Register before executing: @dataclass resolves its own module via sys.modules
# and raises if the module is not there yet.
sys.modules["sequence_qc"] = sequence_qc
_spec.loader.exec_module(sequence_qc)

SequenceIntegrityChecker = sequence_qc.SequenceIntegrityChecker
build_rename_plan = sequence_qc.build_rename_plan
detect_label_shift = sequence_qc.detect_label_shift
verify_rename = sequence_qc.verify_rename
apply_rename_to_copy = sequence_qc.apply_rename_to_copy

_DATA_START = 0x1800


def _write_ch(path: Path, end_min: float, sample: str = "s", method: str = "M.M"):
    """Write a minimal ChemStation-'130'-shaped file the QC reader can parse."""
    blob = bytearray(_DATA_START + 512)
    blob[0:4] = b"\x03130"
    struct.pack_into(">i", blob, 0x11A, 0)
    struct.pack_into(">i", blob, 0x11E, int(end_min * 60000))

    def put(offset, text):
        raw = text.encode("utf-16-le")
        blob[offset] = len(text)
        blob[offset + 1: offset + 1 + len(raw)] = raw

    put(0x35A, sample)
    put(0x957, "24-Jul-26, 10:00:00")
    put(0xA0E, method)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(blob))


def _make_run(seq: Path, name: str, end_min: float, method: str = "M46.M"):
    _write_ch(seq / f"{name}.D" / "RID1A.ch", end_min, sample=name, method=method)


class TestAbortedDetection:
    def test_detects_truncated_run(self, tmp_path):
        seq = tmp_path / "seq"
        for i in range(1, 5):
            _make_run(seq, f"S_{i}", 46.0)
        _make_run(seq, "S_5", 7.7)  # aborted

        checker = SequenceIntegrityChecker()
        runs = checker.scan_sequence(seq)
        aborted = checker.find_aborted(runs)

        assert [r.name for r in aborted] == ["S_5.D"]
        assert all(r.complete for r in runs if r.name != "S_5.D")

    def test_nominal_inferred_when_method_unknown(self, tmp_path):
        """An unfamiliar method must still yield a completeness verdict."""
        seq = tmp_path / "seq"
        for i in range(1, 5):
            _make_run(seq, f"S_{i}", 30.0, method="UNKNOWN.M")
        _make_run(seq, "S_9", 3.0, method="UNKNOWN.M")

        runs = SequenceIntegrityChecker().scan_sequence(seq)
        by_name = {r.name: r for r in runs}
        assert by_name["S_9.D"].complete is False
        assert by_name["S_1.D"].complete is True

    def test_single_long_run_does_not_fail_the_rest(self, tmp_path):
        """Mode, not max: one over-long run must not mark everything aborted."""
        seq = tmp_path / "seq"
        for i in range(1, 6):
            _make_run(seq, f"S_{i}", 46.0)
        _make_run(seq, "S_LONG", 92.0)

        runs = SequenceIntegrityChecker().scan_sequence(seq)
        normal = [r for r in runs if r.name != "S_LONG.D"]
        assert all(r.complete for r in normal)

    def test_empty_and_missing_signal(self, tmp_path):
        seq = tmp_path / "seq"
        _make_run(seq, "GOOD", 46.0)
        (seq / "NOSIG.D").mkdir(parents=True)
        stub = seq / "TINY.D" / "RID1A.ch"
        stub.parent.mkdir(parents=True)
        stub.write_bytes(b"\x03130" + b"\x00" * 64)

        checker = SequenceIntegrityChecker()
        runs = checker.scan_sequence(seq)
        bad = {r.name: r for r in checker.find_aborted(runs)}

        assert "NOSIG.D" in bad and "TINY.D" in bad
        assert not bad["NOSIG.D"].readable
        assert bad["TINY.D"].reason


class TestDuplicateLabels:
    def test_abort_and_rerun_share_a_name(self, tmp_path):
        """Two folders may carry one name across sequences; both must surface."""
        seq_a, seq_b = tmp_path / "a", tmp_path / "b"
        _make_run(seq_a, "RUN_4", 0.5)
        _make_run(seq_b, "RUN_4", 46.0)

        checker = SequenceIntegrityChecker()
        runs = checker.scan_sequence(seq_a) + checker.scan_sequence(seq_b)
        dupes = checker.find_duplicate_labels(runs)

        assert set(dupes) == {"RUN_4.D"}
        assert sum(1 for r in dupes["RUN_4.D"] if r.complete) == 1


class TestLabelShift:
    def test_finds_off_by_one(self):
        reference = {i: 100.0 * i for i in range(1, 16)}
        series = {i - 1: reference[i] for i in range(2, 16)}

        best = detect_label_shift(series, reference)[0]
        assert best.offset == 1
        assert best.within_tolerance >= 10

    def test_prefers_zero_when_aligned(self):
        reference = {i: 100.0 * i for i in range(1, 16)}
        best = detect_label_shift(dict(reference), reference)[0]
        assert best.offset == 0

    def test_ignores_nonpositive_reference(self):
        """Early points below the quantitation limit must not drive alignment."""
        reference = {1: 0.0, 2: 0.0, 3: 300.0, 4: 400.0, 5: 500.0, 6: 600.0}
        series = {3: 300.0, 4: 400.0, 5: 500.0, 6: 600.0}
        best = detect_label_shift(series, reference)[0]
        assert best.offset == 0
        assert best.n_compared == 4

    def test_returns_empty_when_too_little_overlap(self):
        assert detect_label_shift({1: 5.0}, {1: 5.0}) == []


class TestRenamePlan:
    def test_ascending_shift_is_ordered_descending(self):
        """0->1,1->2,... must run from the highest index down, or data is lost."""
        names = [f"S_{i}.D" for i in range(0, 5)]
        mapping = {f"S_{i}.D": f"S_{i + 1}.D" for i in range(0, 5)}

        plan = build_rename_plan(names, mapping)

        assert plan.is_safe
        assert plan.steps[0] == ("S_4.D", "S_5.D")
        assert [s for s, _ in plan.steps] == [f"S_{i}.D" for i in (4, 3, 2, 1, 0)]

    def test_naive_ascending_order_would_have_collided(self):
        """Guard the property the ordering exists for."""
        names = [f"S_{i}.D" for i in range(0, 3)]
        mapping = {f"S_{i}.D": f"S_{i + 1}.D" for i in range(0, 3)}
        plan = build_rename_plan(names, mapping)

        state = set(names)
        for src, dst in plan.steps:
            assert dst not in state, f"{dst} would be overwritten"
            state.discard(src)
            state.add(dst)

    def test_detects_collision_with_untouched_folder(self):
        names = ["A.D", "B.D"]
        plan = build_rename_plan(names, {"A.D": "B.D"})
        assert not plan.is_safe

    def test_detects_two_sources_one_target(self):
        plan = build_rename_plan(["A.D", "B.D"], {"A.D": "C.D", "B.D": "C.D"})
        assert not plan.is_safe

    def test_missing_source_is_skipped_not_fatal(self):
        plan = build_rename_plan(["A.D"], {"A.D": "B.D", "GHOST.D": "X.D"})
        assert plan.is_safe
        assert plan.steps == [("A.D", "B.D")]


class TestVerifyRename:
    def _seed(self, tmp_path):
        src = tmp_path / "src"
        for i in (1, 2):
            _make_run(src, f"S_{i}", 46.0)
        (src / "METHOD.M").mkdir()
        (src / "METHOD.M" / "m.txt").write_text("method", encoding="utf-8")
        return src

    def test_pass_on_faithful_copy(self, tmp_path):
        src = self._seed(tmp_path)
        result = apply_rename_to_copy(
            src, tmp_path / "dst", {"S_1.D": "S_2.D", "S_2.D": "S_3.D"}
        )
        assert result["verification"]["passed"] is True

    def test_unmapped_directory_is_reported_not_ignored(self, tmp_path):
        """A folder left out of the mapping must fail loudly, not vanish."""
        src = self._seed(tmp_path)
        dst = tmp_path / "dst2"
        apply_rename_to_copy(src, dst, {"S_1.D": "S_2.D", "S_2.D": "S_3.D"})

        partial = {"S_1.D": "S_2.D", "S_2.D": "S_3.D"}  # METHOD.M omitted
        report = verify_rename(src, dst, partial)

        assert report["passed"] is False
        assert "METHOD.M" in report["unmapped_src"]

    def test_detects_corrupted_payload(self, tmp_path):
        src = self._seed(tmp_path)
        dst = tmp_path / "dst3"
        apply_rename_to_copy(src, dst, {"S_1.D": "S_2.D", "S_2.D": "S_3.D"})

        victim = dst / "S_3.D" / "RID1A.ch"
        victim.write_bytes(victim.read_bytes()[:-100])

        report = verify_rename(
            src, dst,
            {"S_1.D": "S_2.D", "S_2.D": "S_3.D", "METHOD.M": "METHOD.M"},
        )
        assert report["passed"] is False
        assert any(d["issue"] == "내용 불일치" for d in report["differing"])

    def test_source_is_left_untouched(self, tmp_path):
        src = self._seed(tmp_path)
        before = sorted(p.name for p in src.iterdir())
        apply_rename_to_copy(src, tmp_path / "dst4", {"S_1.D": "S_2.D",
                                                      "S_2.D": "S_3.D"})
        assert sorted(p.name for p in src.iterdir()) == before

    def test_refuses_existing_destination(self, tmp_path):
        src = self._seed(tmp_path)
        dst = tmp_path / "dst5"
        dst.mkdir()
        with pytest.raises(FileExistsError):
            apply_rename_to_copy(src, dst, {"S_1.D": "S_2.D"})

    def test_refuses_unsafe_plan_before_copying(self, tmp_path):
        src = self._seed(tmp_path)
        dst = tmp_path / "dst6"
        with pytest.raises(ValueError):
            apply_rename_to_copy(src, dst, {"S_1.D": "S_2.D", "S_2.D": "S_2.D"})
        assert not dst.exists()
