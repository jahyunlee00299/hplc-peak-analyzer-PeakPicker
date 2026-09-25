"""SampleMeta backward-compatibility tests.

Private scripts do things like `meta.atp_mM`, `meta.time_h`, `s.acp_mM = 5`.
Those names are no longer declared dataclass fields (only generic fields
are), so reads/writes of unknown attribute names must transparently route
through `factors`.
"""
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from peakpicker.models import SampleMeta  # noqa: E402


def test_declared_fields_behave_normally():
    m = SampleMeta(sample_id="s1", folder=Path("."), time_h=3.0, is_ne=True)
    assert m.sample_id == "s1"
    assert m.time_h == 3.0
    assert m.is_ne is True
    assert m.factors == {}


def test_unknown_attribute_write_routes_to_factors():
    m = SampleMeta(sample_id="s1", folder=Path("."))
    m.acp_mM = 5
    m.atp_mM = 1.5
    assert m.factors == {"acp_mM": 5, "atp_mM": 1.5}


def test_unknown_attribute_read_routes_to_factors():
    m = SampleMeta(sample_id="s1", folder=Path("."), factors={"xyl_mM": 50.0})
    assert m.xyl_mM == 50.0


def test_unknown_attribute_read_missing_raises_attribute_error():
    m = SampleMeta(sample_id="s1", folder=Path("."))
    with pytest.raises(AttributeError):
        _ = m.does_not_exist_anywhere


def test_round_trip_write_then_read():
    m = SampleMeta(sample_id="s1", folder=Path("."))
    m.is_fed = True
    assert m.is_fed is True
    assert m.factors["is_fed"] is True


def test_unset_declared_factor_reads_its_default():
    """A plugin-declared factor the parser never set must read as its default.

    Measured 260925: before factor defaults existed, a lab plugin parser crashed on
    `meta.is_fed` for every real folder (the old dataclass field defaulted to
    False), while every other test still passed.
    """
    saved = dict(SampleMeta._factor_defaults)
    try:
        SampleMeta.register_factor_defaults(flag_x=False, dose_x=None)
        meta = SampleMeta(sample_id="s", folder=Path("s.D"))
        assert meta.flag_x is False
        assert meta.dose_x is None
        assert meta.all_factors() == {**saved, "flag_x": False, "dose_x": None}
        meta.dose_x = 3.0
        assert meta.dose_x == 3.0 and meta.all_factors()["dose_x"] == 3.0
        try:
            meta.never_declared
        except AttributeError:
            pass
        else:
            raise AssertionError("undeclared factor must still raise AttributeError")
    finally:
        SampleMeta._factor_defaults.clear()
        SampleMeta._factor_defaults.update(saved)
