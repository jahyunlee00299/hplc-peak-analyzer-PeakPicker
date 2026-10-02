"""Characterization of the two Chemstation .ch readers (they are NOT interchangeable, so they are not merged).

* ``src/chemstation_parser.ChemstationParser`` decodes Agilent format 130 (Pascal "130" header, time at 0x11A,
  scale at 0x127C, int16-delta segments at 0x1800). On real lab files it equals the independent ``rainbow``
  decoder bit for bit (3472/3472 points, max abs difference 0.0, two files).
* ``peakpicker.infrastructure.file_readers.ChemstationReader`` accepts the same "130" magic but reads time at
  0x282, scale at 0x127A + an offset at 0x1282 and a different (variable-length byte delta) body decoder, so on a
  format-130 file it returns a different number of points and different intensities.

The synthetic file below follows the format-130 layout the legacy parser (and rainbow) implement.
Set PEAKPICKER_REAL_CH to a real format-130 ``.ch`` file to also compare against rainbow.
"""
import os
import struct
from pathlib import Path

import numpy as np
import pytest

from chemstation_parser import ChemstationParser, read_chemstation_file
from peakpicker.infrastructure.file_readers.chemstation_reader import ChemstationReader

SCALE = 0.5


def write_format_130(path: Path, counts: np.ndarray, scale: float = SCALE, end_ms: int = 600000) -> None:
    raw = bytearray(0x1800)
    raw[0] = 3
    raw[1:4] = b"130"
    raw[0x11A:0x11E] = struct.pack(">I", 0)
    raw[0x11E:0x122] = struct.pack(">I", end_ms)
    raw[0x127C:0x1284] = struct.pack(">d", scale)
    body = bytearray()
    cur = 0
    vals = [int(v) for v in counts]
    for i in range(0, len(vals), 200):
        chunk = vals[i:i + 200]
        body += bytes([1, len(chunk)])
        for v in chunk:
            d = v - cur
            body += struct.pack(">h", -32768) + struct.pack(">i", v) if abs(d) >= 32767 else struct.pack(">h", d)
            cur = v
    body += bytes([0, 0])
    path.write_bytes(bytes(raw) + bytes(body))


@pytest.fixture()
def synthetic(tmp_path):
    t = np.linspace(0.0, 10.0, 1001)
    counts = np.round(100 + 5000 * np.exp(-0.5 * ((t - 5.0) / 0.2) ** 2)
                      + np.random.default_rng(0).normal(0, 3, t.size)).astype(int)
    counts[500] = 200000                                  # forces the absolute (-32768 escape) branch
    path = tmp_path / "RID1A.ch"
    write_format_130(path, counts)
    return path, counts


def test_legacy_parser_roundtrips_format_130_exactly(synthetic):
    path, counts = synthetic
    time, y = ChemstationParser(str(path)).read()
    np.testing.assert_array_equal(y, SCALE * counts)
    assert time[0] == 0.0 and time[-1] == pytest.approx(10.0)
    t2, y2 = read_chemstation_file(str(path))
    np.testing.assert_array_equal(y2, y)


def test_legacy_parser_rejects_other_versions(tmp_path):
    p = tmp_path / "x.ch"
    p.write_bytes(b"\x02" + b"31" + bytes(0x2000))
    with pytest.raises(ValueError):
        ChemstationParser(str(p)).read()


@pytest.mark.xfail(strict=True, reason="package ChemstationReader decodes format-130 bodies with a different (wrong) layout; "
                                       "readers are deliberately not merged - flip this when the package reader is fixed")
def test_package_reader_recovers_format_130(synthetic):
    path, counts = synthetic
    d = ChemstationReader().read(path)
    np.testing.assert_array_equal(d.intensity, SCALE * counts)


def test_package_reader_differs_from_legacy_on_format_130(synthetic):
    """The measured difference that blocks a merge (documented, not endorsed)."""
    path, counts = synthetic
    legacy_t, legacy_y = ChemstationParser(str(path)).read()
    d = ChemstationReader().read(path)
    assert len(legacy_y) == len(counts)
    assert len(d.intensity) != len(legacy_y)


@pytest.mark.skipif(not os.environ.get("PEAKPICKER_REAL_CH"), reason="set PEAKPICKER_REAL_CH to a real format-130 .ch file")
def test_legacy_parser_equals_rainbow_on_a_real_file():
    rainbow = pytest.importorskip("rainbow.agilent.chemstation")
    f = os.environ["PEAKPICKER_REAL_CH"]
    ref = np.asarray(rainbow.parse_ch(f).data, dtype=float).ravel()
    _, y = ChemstationParser(f).read()
    np.testing.assert_array_equal(y[:len(ref)], ref[:len(y)])
    assert len(y) == len(ref)
