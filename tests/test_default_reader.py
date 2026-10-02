"""WorkflowBuilder().build() / create_default_workflow must read format-130 .ch files correctly."""
import os

import numpy as np
import pytest

from chemstation_parser import ChemstationParser
from peakpicker.application import workflow as wf_mod
from peakpicker.application.workflow import WorkflowBuilder, create_default_workflow
from peakpicker.infrastructure import AutoReader, ChemstationReader, LegacyParserReader, RainbowReader
from peakpicker.infrastructure.file_readers import rainbow_reader
from test_chemstation_readers_characterization import SCALE, write_format_130


@pytest.fixture()
def fixture_file(tmp_path):
    t = np.linspace(0.0, 10.0, 1001)
    counts = np.round(100 + 5000 * np.exp(-0.5 * ((t - 5.0) / 0.2) ** 2) + np.random.default_rng(0).normal(0, 3, t.size)).astype(int)
    counts[500] = 200000
    d = tmp_path / "S1.D"
    d.mkdir()
    path = d / "RID1A.ch"
    write_format_130(path, counts)
    return path, counts


def test_default_builder_uses_the_auto_reader_not_the_package_decoder():
    reader = WorkflowBuilder().build().reader
    assert isinstance(reader, AutoReader)
    kinds = [type(r) for r in reader.readers]
    assert kinds[0] is RainbowReader and LegacyParserReader in kinds and ChemstationReader not in kinds
    assert not any(isinstance(r, ChemstationReader) for r in create_default_workflow().reader.readers)


def test_default_reader_decodes_format_130_like_the_legacy_parser(fixture_file):
    path, counts = fixture_file
    data = WorkflowBuilder().build().reader.read(path)
    t, y = ChemstationParser(str(path)).read()
    np.testing.assert_array_equal(data.intensity, y)
    np.testing.assert_array_equal(data.intensity, SCALE * counts)
    np.testing.assert_array_equal(data.time, t)
    assert data.sample_name == "S1"


def test_without_rainbow_the_legacy_parser_is_used_explicitly(fixture_file, monkeypatch):
    path, counts = fixture_file
    monkeypatch.setattr(rainbow_reader, "rainbow_available", lambda: False)
    reader = WorkflowBuilder().with_auto_reader().build().reader
    assert not reader.readers[0].can_read(path)
    data = reader.read(path)
    assert data.metadata["reader"] == "LegacyParserReader"
    np.testing.assert_array_equal(data.intensity, SCALE * counts)


def test_explicit_package_decoder_is_still_wrong_and_documented():
    assert "WARNING" in WorkflowBuilder.with_chemstation_reader.__doc__
    assert "WARNING" in ChemstationReader.__doc__


def test_auto_reader_reraises_the_first_error_when_every_reader_fails(tmp_path):
    bad = tmp_path / "x.ch"
    bad.write_bytes(b"\x03130" + bytes(10))
    with pytest.raises(Exception):
        WorkflowBuilder().build().reader.read(bad)


@pytest.mark.skipif(not os.environ.get("PEAKPICKER_REAL_CH"), reason="set PEAKPICKER_REAL_CH to a real format-130 .ch file")
def test_default_reader_equals_rainbow_on_a_real_file():
    rainbow = pytest.importorskip("rainbow.agilent.chemstation")
    f = os.environ["PEAKPICKER_REAL_CH"]
    ref = np.asarray(rainbow.parse_ch(f).data, dtype=float).ravel()
    data = WorkflowBuilder().build().reader.read(f)
    np.testing.assert_array_equal(data.intensity, ref)
