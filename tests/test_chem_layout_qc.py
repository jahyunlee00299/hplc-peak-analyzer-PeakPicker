"""Tests for the ChemStation folder layout checker.

Adverse cases first: each one was observed (or is the direct opposite of something observed) on real data.
Fixtures are tiny synthetic .D folders; nothing here touches instrument data.
"""

import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_SRC = Path(__file__).resolve().parents[1] / "src" / "peakpicker" / "infrastructure" / "file_readers"

# Loaded by file path (same reason as test_sequence_qc.py: the package import chain is not reliable here).
_spec = importlib.util.spec_from_file_location("chem_layout_qc", _SRC / "chem_layout_qc.py")
qc = importlib.util.module_from_spec(_spec)
sys.modules["chem_layout_qc"] = qc
_spec.loader.exec_module(qc)

SCRIPT = _SRC / "chem_layout_qc.py"
_DATA_START = 0x1800
METHOD = "STD_25MIN.M"


def _write_ch(path: Path, end_min: float, sample: str, method: str = METHOD, size_extra: int = 512):
    blob = bytearray(_DATA_START + size_extra)
    blob[0:4] = b"\x03130"
    struct.pack_into(">i", blob, 0x11A, 0)
    struct.pack_into(">i", blob, 0x11E, int(end_min * 60000))

    def put(offset, text):
        raw = text.encode("utf-16-le")
        blob[offset] = len(text)
        blob[offset + 1: offset + 1 + len(raw)] = raw

    put(0x35A, sample)
    put(0x957, "29-Sep-26, 10:00:00")
    put(0xA0E, method)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(blob))


def make_run(folder: Path, name: str, sample: str = None, end_min: float = 25.0, method: str = METHOD,
             acqres: bool = True, runlog: bool = True) -> Path:
    d = folder / name
    _write_ch(d / "RID1A.ch", end_min, sample if sample is not None else name.rsplit(".", 1)[0], method)
    if acqres:
        (d / "ACQRES.REG").write_bytes(b"reg")
    if runlog:
        (d / "RUN.LOG").write_bytes(b"log")
    return d


@pytest.fixture(autouse=True)
def _default_spec(monkeypatch):
    """Tests must not pick up a lab overlay spec that happens to exist next to the repo."""
    monkeypatch.setenv("CHEM_LAYOUT_SPEC", str(qc.DEFAULT_SPEC))


@pytest.fixture
def clean(tmp_path):
    folder = tmp_path / "run"
    for i, s in enumerate(("a94", "a95", "a106")):
        label = f"EXP1_0180min_X20_E_R{i + 1}_{s}"
        make_run(folder, label + ".D", sample=label)         # header already rewritten to the label (L9 clean)
    return folder


def rules(report, rid):
    return [f for f in report.findings if f.rule == rid]


def snapshot(root: Path):
    out = {}
    for p in sorted(root.rglob("*")):
        out[str(p.relative_to(root))] = hashlib.md5(p.read_bytes()).hexdigest() if p.is_file() else "<dir>"
    return out


# ------------------------------------------------------------------------------------------------ happy path

class TestCleanFolder:
    def test_clean_folder_passes(self, clean):
        rep = qc.check_folder(clean)
        assert rep.errors == 0 and rep.warnings == 0
        assert rep.runs == 3
        assert {"L1", "L2", "L3", "L4", "L5", "L6"} <= set(rep.rules_run)
        assert rep.exit_code() == 0

    def test_pending_rule_is_skipped_not_run(self, clean):
        spec = qc.load_spec()
        next(r for r in spec["rules"] if r["id"] == "L9")["status"] = "pending_evidence"
        rep = qc.check_folder(clean, spec)
        assert {"id": "L9", "reason": "pending_evidence"} in rep.rules_skipped
        assert "L9" not in rep.rules_run

    def test_l9_runs_by_default_and_clean_folder_has_no_l9_finding(self, clean):
        rep = qc.check_folder(clean)
        assert "L9" in rep.rules_run and rules(rep, "L9") == []

    def test_map_rules_need_their_inputs(self, clean):
        rep = qc.check_folder(clean)
        reasons = {s["id"]: s["reason"] for s in rep.rules_skipped}
        assert "--map" in reasons["L7"]
        assert "--map" in reasons["L10"] and "--raw" in reasons["L10"]


# ------------------------------------------------------------------------------------------------ L1 / L2 (observed)

class TestSequenceFilesHideFolder:
    def test_sequence_files_are_flagged_by_L2_only(self, clean):
        for name in ("240528_PAUSED_HPX87H.S", "240528_PAUSED_HPX87H.LOG", "240528_PAUSED_HPX87H.B", "ACQUIRING.TXT", "METHODS.REG"):
            (clean / name).write_bytes(b"x")
        (clean / "STD_25MIN.M").mkdir()
        rep = qc.check_folder(clean)
        assert len(rules(rep, "L2")) == 6
        assert rules(rep, "L1") == []          # no double reporting
        assert rep.exit_code() == 1

    def test_stray_files_and_subfolders_are_flagged_by_L1(self, clean):
        (clean / "_RELABEL_LOG.csv").write_text("a,b")
        (clean / ".DS_Store").write_bytes(b"x")
        (clean / "desktop.ini").write_text("[x]")
        (clean / "renamed").mkdir()
        rep = qc.check_folder(clean)
        assert len(rules(rep, "L1")) == 4
        assert all(f.severity == "error" for f in rules(rep, "L1"))

    def test_file_named_like_a_run_is_not_a_run(self, clean):
        (clean / "fake.D").write_bytes(b"x")
        rep = qc.check_folder(clean)
        msgs = [f.message for f in rules(rep, "L1")]
        assert any("FILE" in m for m in msgs)
        assert rep.runs == 3

    def test_lowercase_d_extension_is_a_run(self, tmp_path):
        folder = tmp_path / "f"
        make_run(folder, "x.d")
        assert qc.check_folder(folder).runs == 1

    def test_upper_and_lower_case_sequence_names_match(self, clean):
        (clean / "acquiring.txt").write_bytes(b"x")
        assert len(rules(qc.check_folder(clean), "L2")) == 1


class TestNoRunsFolder:
    def test_empty_folder_is_info_not_failure(self, tmp_path):
        (tmp_path / "e").mkdir()
        rep = qc.check_folder(tmp_path / "e")
        assert rep.exit_code() == 0
        assert [f.rule for f in rep.findings] == ["L0"] and rep.findings[0].severity == "info"

    def test_runs_one_level_down_are_not_descended(self, tmp_path):
        make_run(tmp_path / "outer" / "renamed", "a.D")
        rep = qc.check_folder(tmp_path / "outer")
        assert rep.runs == 0 and rep.findings[0].rule == "L0"

    def test_missing_folder_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            qc.check_folder(tmp_path / "nope")


# ------------------------------------------------------------------------------------------------ L3 / L4

class TestRunContents:
    def test_missing_signal_is_an_error(self, clean):
        (clean / "EXP1_0180min_X20_E_R1_a94.D" / "RID1A.ch").unlink()
        rep = qc.check_folder(clean)
        assert len(rules(rep, "L3")) == 1 and rules(rep, "L3")[0].severity == "error"
        assert rules(rep, "L4") == []          # not reported twice

    def test_missing_acqres_is_only_a_warning(self, tmp_path):
        folder = tmp_path / "f"
        make_run(folder, "a.D", acqres=False)
        rep = qc.check_folder(folder)
        assert rep.errors == 0 and rep.warnings == 1
        assert rep.exit_code() == 0 and rep.exit_code(strict=True) == 1

    def test_single_aborted_run_is_caught_by_declared_runtime(self, tmp_path):
        """_incomplete case: one run alone in the folder, 19.49 of 25 min."""
        folder = tmp_path / "_incomplete"
        make_run(folder, "S_0033.D", sample="a122", end_min=19.49)
        spec = qc.load_spec()
        next(r for r in spec["rules"] if r["id"] == "L4")["params"]["nominal_min_by_method"] = {"STD_25MIN.M": 25.0}
        rep = qc.check_folder(folder, spec)
        assert len(rules(rep, "L4")) == 1
        assert "19.49 of 25.00" in rules(rep, "L4")[0].message

    def test_spec_complete_fraction_is_honoured(self, tmp_path):
        folder = tmp_path / "f"
        for i in range(3):
            make_run(folder, f"r{i}.D", end_min=25.0)
        make_run(folder, "partial.D", end_min=15.0)                    # 60 % of the modal 25 min
        strict = qc.load_spec()
        assert [Path(f.path).name for f in rules(qc.check_folder(folder, strict), "L4")] == ["partial.D"]
        loose = qc.load_spec()
        next(r for r in loose["rules"] if r["id"] == "L4")["params"]["complete_fraction"] = 0.5
        assert rules(qc.check_folder(folder, loose), "L4") == []

    def test_single_run_with_unknown_method_cannot_be_judged(self, tmp_path):
        """Documented limitation: without a declared runtime the folder's own runs are the reference."""
        folder = tmp_path / "f"
        make_run(folder, "x.D", end_min=5.0, method="UNKNOWN.M")
        assert rules(qc.check_folder(folder), "L4") == []

    def test_aborted_run_among_complete_runs(self, clean):
        make_run(clean, "EXP1_9999min_X20_E_R9_a1.D", sample="a1", end_min=7.7)
        rep = qc.check_folder(clean)
        assert [f.path.endswith("a1.D") for f in rules(rep, "L4")] == [True]

    def test_truncated_signal_file_is_reported(self, tmp_path):
        folder = tmp_path / "f"
        make_run(folder, "x.D")
        (folder / "x.D" / "RID1A.ch").write_bytes(b"\x03130" + b"\0" * 100)
        rep = qc.check_folder(folder)
        assert any("unreadable" in f.message for f in rules(rep, "L4"))


# ------------------------------------------------------------------------------------------------ L5 / L6

class TestNames:
    def test_bad_readable_name_warns(self, clean):
        make_run(clean, "EXP1_X20_E_R1_180min.D", sample="a1")      # old, unsorted scheme
        rep = qc.check_folder(clean)
        assert len(rules(rep, "L5")) == 1 and rules(rep, "L5")[0].severity == "warning"

    def test_names_outside_the_scheme_prefix_are_ignored(self, tmp_path):
        folder = tmp_path / "f"
        make_run(folder, "250417_PATH_A_RIB25MM_ACP_100_1H.D")
        assert rules(qc.check_folder(folder), "L5") == []

    def test_custom_scheme_pattern_from_spec(self, tmp_path):
        spec = qc.load_spec()
        rule = next(r for r in spec["rules"] if r["id"] == "L5")
        rule["params"]["applies_to_prefix"] = "EXP2_"
        rule["params"]["patterns"] = [r"^EXP2_\d{4}min_(A|B)_(E|NE)_R\d+_n\d+\.D$"]
        folder = tmp_path / "f"
        make_run(folder, "EXP2_0480min_A_E_R1_n95.D")
        make_run(folder, "EXP2_0480min_C_E_R1_n96.D")
        out = rules(qc.check_folder(folder, spec), "L5")
        assert [Path(f.path).name for f in out] == ["EXP2_0480min_C_E_R1_n96.D"]

    def test_case_insensitive_collision(self):
        spec = qc.load_spec()
        ctx = qc.Ctx(Path("a"), [], [Path("a/X.D"), Path("a/x.d")], qc._rule_params(spec, "L6"), "error", spec)
        out = qc.rule_l6(ctx)
        assert len(out) == 1 and "collides" in out[0].message

    def test_long_path_warns(self, tmp_path):
        spec = qc.load_spec()
        for r in spec["rules"]:
            if r["id"] == "L6":
                r["params"]["max_path_chars"] = 20
        folder = tmp_path / "f"
        make_run(folder, "a.D")
        rep = qc.check_folder(folder, spec)
        assert any(f.severity == "warning" and "characters" in f.message for f in rules(rep, "L6"))


# ------------------------------------------------------------------------------------------------ L7 / L10

def write_map(path: Path, rows):
    cols = ["orig_folder", "header_sample", "folder", "complete"]
    path.write_text("\n".join([",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in rows]) + "\n", encoding="utf-8")


class TestSampleMap:
    def rows(self, clean):
        return [{"orig_folder": f"0{i}.D", "header_sample": s, "folder": d.name, "complete": True}
                for i, (s, d) in enumerate(zip(("a94", "a95", "a106"), sorted(clean.iterdir())))]

    def test_matching_map_passes(self, clean, tmp_path):
        rows = self.rows(clean)
        # header names were written from the folder name suffix, so align the map with the real headers
        for r, d in zip(rows, sorted(clean.iterdir())):
            r["header_sample"] = d.name.rsplit("_", 1)[1][:-2]
        write_map(tmp_path / "map.csv", rows)
        assert rules(qc.check_folder(clean, map_path=tmp_path / "map.csv"), "L7") == []

    def test_vial_reuse_header_mismatch_is_an_error(self, clean, tmp_path):
        rows = self.rows(clean)
        for r, d in zip(rows, sorted(clean.iterdir())):
            r["header_sample"] = d.name.rsplit("_", 1)[1][:-2]
        rows[0]["header_sample"] = "a91"          # vial 91 was a91 at line 1, a106 at line 16
        first = sorted(clean.iterdir())[0]
        _write_ch(first / "RID1A.ch", 25.0, "a94")  # header carries a third name: neither the map's 'a91' nor the label
        write_map(tmp_path / "map.csv", rows)
        out = rules(qc.check_folder(clean, map_path=tmp_path / "map.csv"), "L7")
        assert len(out) == 1 and "neither the recorded original" in out[0].message

    def test_run_not_in_map_and_map_row_without_run(self, clean, tmp_path):
        rows = self.rows(clean)
        for r, d in zip(rows, sorted(clean.iterdir())):
            r["header_sample"] = d.name.rsplit("_", 1)[1][:-2]
        rows.pop(0)
        rows.append({"orig_folder": "x", "header_sample": "a1", "folder": "ghost.D", "complete": True})
        rows.append({"orig_folder": "y", "header_sample": "a2", "folder": "aborted.D", "complete": False})
        write_map(tmp_path / "map.csv", rows)
        msgs = [f.message for f in rules(qc.check_folder(clean, map_path=tmp_path / "map.csv"), "L7")]
        assert any("not in the sample map" in m for m in msgs)
        assert any("not in the folder" in m for m in msgs)
        assert not any("aborted.D" in f.path for f in rules(qc.check_folder(clean, map_path=tmp_path / "map.csv"), "L7"))

    def test_map_without_required_column_is_a_usage_error(self, clean, tmp_path):
        (tmp_path / "bad.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")
        with pytest.raises(qc.SpecError):
            qc.check_folder(clean, map_path=tmp_path / "bad.csv")


class TestProvenance:
    def build(self, tmp_path):
        raw, cur = tmp_path / "raw", tmp_path / "cur"
        make_run(raw, "091-0101.D", sample="a91")
        make_run(cur, "EXP1_0180min_X02_E_R1_a91.D", sample="a91")
        # make the two byte-identical
        for f in (raw / "091-0101.D").iterdir():
            (cur / "EXP1_0180min_X02_E_R1_a91.D" / f.name).write_bytes(f.read_bytes())
        write_map(tmp_path / "map.csv", [{"orig_folder": "091-0101.D", "header_sample": "a91", "folder": "EXP1_0180min_X02_E_R1_a91.D", "complete": True},
                                         {"orig_folder": "S_0033.D", "header_sample": "a122", "folder": "x.D", "complete": False}])
        return raw, cur, tmp_path / "map.csv"

    def test_identical_copy_passes(self, tmp_path):
        raw, cur, m = self.build(tmp_path)
        assert rules(qc.check_folder(cur, map_path=m, raw_dir=raw), "L10") == []

    def test_one_flipped_byte_is_caught(self, tmp_path):
        raw, cur, m = self.build(tmp_path)
        ch = cur / "EXP1_0180min_X02_E_R1_a91.D" / "RID1A.ch"
        b = bytearray(ch.read_bytes()); b[_DATA_START + 5] ^= 0xFF; ch.write_bytes(bytes(b))
        out = rules(qc.check_folder(cur, map_path=m, raw_dir=raw), "L10")
        assert len(out) == 1 and "byte-identical" in out[0].message

    def test_missing_provenance_or_run(self, tmp_path):
        raw, cur, m = self.build(tmp_path)
        import shutil
        shutil.rmtree(raw / "091-0101.D")
        assert any("provenance copy" in f.message for f in rules(qc.check_folder(cur, map_path=m, raw_dir=raw), "L10"))


class TestRewrittenHeader:
    """After the rename recipe rewrites the header sample name to the readable label."""

    def spec_with(self, rid, **changes):
        spec = qc.load_spec()
        rule = next(r for r in spec["rules"] if r["id"] == rid)
        for k, v in changes.items():
            if k == "status":
                rule["status"] = v
            else:
                rule["params"][k] = v
        return spec

    def test_l9_flags_header_that_differs_from_label(self, tmp_path):
        folder = tmp_path / "f"
        make_run(folder, "EXP1_0180min_X20_E_R1_a94.D", sample="a94")            # header still the original id
        make_run(folder, "EXP1_0180min_X20_E_R2_a95.D", sample="EXP1_0180min_X20_E_R2_a95")   # rewritten
        rep = qc.check_folder(folder, self.spec_with("L9", status="observed"))
        assert "L9" in rep.rules_run
        assert [Path(f.path).name for f in rules(rep, "L9")] == ["EXP1_0180min_X20_E_R1_a94.D"]

    def test_l7_accepts_a_rewritten_header_but_not_a_third_name(self, tmp_path):
        folder = tmp_path / "f"
        make_run(folder, "EXP1_0180min_X20_E_R1_a94.D", sample="EXP1_0180min_X20_E_R1_a94")   # rewritten = label
        make_run(folder, "EXP1_0180min_X20_E_R2_a95.D", sample="a91")                          # wrong sample entirely
        write_map(tmp_path / "map.csv", [
            {"orig_folder": "0.D", "header_sample": "a94", "folder": "EXP1_0180min_X20_E_R1_a94.D", "complete": True},
            {"orig_folder": "1.D", "header_sample": "a95", "folder": "EXP1_0180min_X20_E_R2_a95.D", "complete": True}])
        out = rules(qc.check_folder(folder, map_path=tmp_path / "map.csv"), "L7")
        assert [Path(f.path).name for f in out] == ["EXP1_0180min_X20_E_R2_a95.D"]


class TestMaskedProvenance:
    NAME = 0x35A, 0x757

    def build(self, tmp_path, rewritten=True):
        raw, cur = tmp_path / "raw", tmp_path / "cur"
        make_run(raw, "091-0101.D", sample="a91")
        label = "EXP1_0180min_X02_E_R1_a91"
        make_run(cur, label + ".D", sample=label if rewritten else "a91")
        for f in (raw / "091-0101.D").iterdir():
            if f.name != "RID1A.ch":
                (cur / (label + ".D") / f.name).write_bytes(f.read_bytes())
        write_map(tmp_path / "map.csv", [{"orig_folder": "091-0101.D", "header_sample": "a91", "folder": label + ".D", "complete": True}])
        return raw, cur, tmp_path / "map.csv", label + ".D"

    def masked_spec(self):
        spec = qc.load_spec()
        next(r for r in spec["rules"] if r["id"] == "L10")["params"]["masked_ranges"] = {"RID1A.ch": [list(self.NAME)]}
        return spec

    def test_strict_comparison_fails_when_the_name_field_was_rewritten(self, tmp_path):
        raw, cur, m, _ = self.build(tmp_path)
        assert len(rules(qc.check_folder(cur, map_path=m, raw_dir=raw), "L10")) == 1

    def test_masked_comparison_accepts_only_the_name_field_change(self, tmp_path):
        raw, cur, m, _ = self.build(tmp_path)
        assert rules(qc.check_folder(cur, self.masked_spec(), m, raw), "L10") == []

    def test_change_outside_the_mask_is_still_caught(self, tmp_path):
        raw, cur, m, name = self.build(tmp_path)
        ch = cur / name / "RID1A.ch"
        b = bytearray(ch.read_bytes()); b[_DATA_START + 7] ^= 0xFF; ch.write_bytes(bytes(b))
        assert len(rules(qc.check_folder(cur, self.masked_spec(), m, raw), "L10")) == 1

    def test_size_change_is_caught_even_with_the_mask(self, tmp_path):
        raw, cur, m, name = self.build(tmp_path)
        ch = cur / name / "RID1A.ch"
        ch.write_bytes(ch.read_bytes() + b"\x00")
        assert len(rules(qc.check_folder(cur, self.masked_spec(), m, raw), "L10")) == 1


# ------------------------------------------------------------------------------------------------ spec discipline

class TestSpec:
    def test_default_spec_loads_and_matches_registry(self):
        spec = qc.load_spec()
        ids = {r["id"] for r in spec["rules"]}
        assert ids == set(qc.RULES)

    def test_every_observed_rule_carries_evidence(self):
        for r in qc.load_spec()["rules"]:
            if r["status"] == "observed":
                assert r.get("evidence"), f"{r['id']} is observed but has no evidence"

    def test_unknown_rule_id_is_rejected(self, tmp_path):
        s = yaml.safe_load(qc.DEFAULT_SPEC.read_text(encoding="utf-8"))
        s["rules"].append({"id": "L99", "severity": "error", "status": "observed"})
        p = tmp_path / "s.yaml"; p.write_text(yaml.safe_dump(s), encoding="utf-8")
        with pytest.raises(qc.SpecError):
            qc.load_spec(p)

    def test_bad_severity_and_malformed_yaml(self, tmp_path):
        s = yaml.safe_load(qc.DEFAULT_SPEC.read_text(encoding="utf-8"))
        s["rules"][0]["severity"] = "fatal"
        p = tmp_path / "s.yaml"; p.write_text(yaml.safe_dump(s), encoding="utf-8")
        with pytest.raises(qc.SpecError):
            qc.load_spec(p)
        q = tmp_path / "broken.yaml"; q.write_text("rules: [unclosed", encoding="utf-8")
        with pytest.raises(qc.SpecError):
            qc.load_spec(q)

    def test_spec_resolution_order(self, tmp_path, monkeypatch):
        explicit = tmp_path / "explicit.yaml"
        explicit.write_text(qc.DEFAULT_SPEC.read_text(encoding="utf-8"), encoding="utf-8")
        env = tmp_path / "env.yaml"
        monkeypatch.setenv("CHEM_LAYOUT_SPEC", str(env))
        assert qc.resolve_spec_path(explicit) == explicit           # explicit wins
        assert qc.resolve_spec_path() == env                         # then the environment
        monkeypatch.delenv("CHEM_LAYOUT_SPEC")
        fake = tmp_path / "a" / "b" / "c" / "d" / "e"                # _HERE.parents[3] == tmp_path / "a"
        fake.mkdir(parents=True)
        (tmp_path / "a" / "methods").mkdir()
        monkeypatch.setattr(qc, "_HERE", fake)
        assert qc.resolve_spec_path() == qc.DEFAULT_SPEC             # no overlay -> packaged default
        overlay = tmp_path / "a" / "methods" / "chem_layout_spec.lab.yaml"
        overlay.write_text("x", encoding="utf-8")
        assert qc.resolve_spec_path() == overlay                     # overlay preferred over the default

    def test_public_spec_carries_no_lab_specific_names(self):
        """The packaged spec must stay generic: no drive paths, experiment-id shapes, date-like ids or lab method names."""
        import re
        text = qc.DEFAULT_SPEC.read_text(encoding="utf-8")
        for pattern in (r"[A-Za-z]:[\/]", r"M\d{3}_", r"\d{6}", r"HPX87H_\d"):
            assert re.search(pattern, text) is None, f"lab-specific shape {pattern!r} in the public spec"

    def test_bad_status_is_rejected(self, tmp_path):
        s = yaml.safe_load(qc.DEFAULT_SPEC.read_text(encoding="utf-8"))
        s["rules"][0]["status"] = "maybe"
        p = tmp_path / "s.yaml"; p.write_text(yaml.safe_dump(s), encoding="utf-8")
        with pytest.raises(qc.SpecError):
            qc.load_spec(p)

    def test_disabled_rule_does_not_run(self, clean):
        spec = qc.load_spec()
        for r in spec["rules"]:
            if r["id"] == "L4":
                r["status"] = "disabled"
        rep = qc.check_folder(clean, spec)
        assert "L4" not in rep.rules_run and {"id": "L4", "reason": "disabled"} in rep.rules_skipped


# ------------------------------------------------------------------------------------------------ L8 tree

class TestTree:
    def test_analysis_outputs_flagged_and_chemstation_files_not(self, tmp_path):
        root = tmp_path / "DATA"
        make_run(root / "proj", "a.D")
        (root / "proj" / "a.D" / "notes.xlsx").write_bytes(b"x")        # inside a .D: never inspected
        for name in ("seq.S", "seq.LOG", "m.xml", "m.mth", "x.reg", "rpthead.txt", "sample_map.csv"):
            (root / "proj" / name).write_bytes(b"x")
        (root / "proj" / "figure.png").write_bytes(b"x")
        (root / "proj" / "table.xlsx").write_bytes(b"x")
        (root / "proj" / "peaks.csv").write_bytes(b"x")
        (root / "proj" / "quantification_results").mkdir()
        (root / "proj" / "quantification_results" / "inner.xlsx").write_bytes(b"x")
        rep = qc.check_tree(root)
        paths = sorted(Path(f.path).name for f in rep.findings)
        assert paths == ["figure.png", "peaks.csv", "quantification_results", "table.xlsx"]
        assert rep.runs == 1 and rep.exit_code() == 0 and rep.exit_code(strict=True) == 1

    def test_flagged_directory_is_not_expanded(self, tmp_path):
        root = tmp_path / "DATA"
        (root / "results" / "deep").mkdir(parents=True)
        (root / "results" / "deep" / "a.xlsx").write_bytes(b"x")
        assert len(qc.check_tree(root).findings) == 1

    def test_tree_ignores_dotD_directories(self, tmp_path):
        root = tmp_path / "DATA"
        (root / "x.D" / "results").mkdir(parents=True)
        assert qc.check_tree(root).findings == []


# ------------------------------------------------------------------------------------------------ read-only + CLI

class TestReadOnlyAndCli:
    def test_check_and_tree_do_not_modify_anything(self, clean, tmp_path):
        (clean / "x.S").write_bytes(b"x")
        before = snapshot(clean)
        qc.check_folder(clean)
        qc.check_tree(clean)
        assert snapshot(clean) == before

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_exit_codes_and_json(self, clean, tmp_path):
        ok = self.run_cli("check", clean, "--json", tmp_path / "r.json")
        assert ok.returncode == 0
        data = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
        assert data["summary"]["errors"] == 0 and data["runs"] == 3
        (clean / "a.S").write_bytes(b"x")
        bad = self.run_cli("check", clean)
        assert bad.returncode == 1 and "L2" in bad.stdout

    def test_usage_errors_exit_2(self, tmp_path):
        assert self.run_cli("check", tmp_path / "missing").returncode == 2
        assert self.run_cli("check").returncode == 2
        assert self.run_cli("check", tmp_path, "--spec", tmp_path / "nope.yaml").returncode == 2

    def test_json_report_can_live_outside_the_checked_folder(self, clean, tmp_path):
        before = snapshot(clean)
        self.run_cli("check", clean, "--json", tmp_path / "out.json")
        assert snapshot(clean) == before
