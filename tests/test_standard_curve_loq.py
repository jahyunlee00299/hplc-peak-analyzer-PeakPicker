"""
test_standard_curve_loq.py — regression tests for the LLOQ/ULOQ port (260924, SSOT-8).

Ports OpenMS AbsoluteQuantitationMethod's llod_/ulod_/lloq_/uloq_ into
StandardCurve (src/peakpicker/quant/method_config.py) to stop calibration-range
extrapolation from being silent. 260924 search of methods/*.yaml, analyses/,
archive/backup_scripts/ and git history found NO raw standard-curve
concentration points for any curve currently loaded by QuantMethod.from_yaml
(the lab's method YAMLs, which live in the private overlay) —
so every production curve must keep predict()'s exact pre-port behaviour
(lloq/uloq stay None, no warning, no change to the returned value). These
tests pin that degrade-gracefully requirement alongside the new mechanism.
"""
import logging
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from peakpicker.quant.method_config import QuantMethod, StandardCurve  # noqa: E402

def _std_curve_methods():
    """Every method YAML present that defines standard curves.

    Discovered rather than listed: the production methods are private and a
    hard-coded list would publish their names. On a public clone only the
    synthetic example is found; with the private overlay all lab curves are.
    """
    found = []
    for path in sorted((REPO / "methods").glob("*.yaml")):
        try:
            if QuantMethod.from_yaml(str(path)).standard_curves:
                found.append(path.name)
        except Exception:
            continue  # not a QuantMethod-schema file; other loader's concern
    return found


STD_CURVE_METHODS = _std_curve_methods()


# ── Degrade gracefully when concentrations/lloq/uloq are absent ────────────

@pytest.mark.parametrize("fname", STD_CURVE_METHODS)
def test_production_curves_have_no_loq_today(fname):
    """260924 finding: no raw concentration source exists for these curves yet.

    lloq/uloq must default to None, not be guessed from anything.
    """
    path = REPO / "methods" / fname
    method = QuantMethod.from_yaml(str(path))
    assert method.standard_curves, f"{fname}: no standard curves loaded"
    for name, sc in method.standard_curves.items():
        assert sc.lloq is None, f"{fname}:{name}: lloq should be None, got {sc.lloq!r}"
        assert sc.uloq is None, f"{fname}:{name}: uloq should be None, got {sc.uloq!r}"


def test_predict_unchanged_when_loq_unknown(caplog):
    """No lloq/uloq set → predict() returns the same value and logs nothing new."""
    sc = StandardCurve(compound_name="t", concentrations=[], areas=[])
    sc.slope, sc.intercept, sc._fitted = 1000.0, 0.0, True

    with caplog.at_level(logging.WARNING):
        # A wildly out-of-any-plausible-range area: if lloq/uloq were being
        # invented from nowhere, this would trip a warning. It must not.
        conc = sc.predict(1_000_000.0)
    assert conc == pytest.approx(1000.0)
    assert not any("LLOQ" in r.message or "ULOQ" in r.message for r in caplog.records)


# ── New behaviour when lloq/uloq ARE known ──────────────────────────────────

def test_explicit_yaml_lloq_uloq_survive_prefitted_load(tmp_path):
    yaml_text = """
standard_curves:
  X:
    slope: 1000.0
    intercept: 0.0
    lloq: 0.1
    uloq: 5.0
"""
    p = tmp_path / "m.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    method = QuantMethod.from_yaml(str(p))
    sc = method.standard_curves["X"]
    assert sc.lloq == pytest.approx(0.1)
    assert sc.uloq == pytest.approx(5.0)


def test_fit_defaults_loq_to_fitted_range_when_not_given():
    """A raw-points curve with no explicit lloq/uloq gets them from min/max(concentrations)."""
    sc = StandardCurve(
        compound_name="t", concentrations=[0.5, 1.0, 2.0, 5.0], areas=[500, 1000, 2000, 5000]
    )
    sc.fit()
    assert sc.lloq == pytest.approx(0.5)
    assert sc.uloq == pytest.approx(5.0)


def test_fit_does_not_override_explicit_loq():
    sc = StandardCurve(
        compound_name="t", concentrations=[0.5, 1.0, 2.0, 5.0], areas=[500, 1000, 2000, 5000]
    )
    sc.lloq, sc.uloq = 0.2, 10.0
    sc.fit()
    assert sc.lloq == pytest.approx(0.2)
    assert sc.uloq == pytest.approx(10.0)


def test_predict_warns_below_lloq(caplog):
    sc = StandardCurve(compound_name="t", concentrations=[], areas=[])
    sc.slope, sc.intercept, sc._fitted = 1000.0, 0.0, True
    sc.lloq, sc.uloq = 1.0, 10.0

    with caplog.at_level(logging.WARNING):
        conc = sc.predict(500.0)  # conc = 0.5, below lloq=1.0
    assert conc == pytest.approx(0.5)
    assert any("BELOW LLOQ" in r.message for r in caplog.records)


def test_predict_warns_above_uloq(caplog):
    """The card's motivating case: a 50 mM sample silently 10x-extrapolated past
    a 0.1-5.0 mM calibration must now be flagged, not silent."""
    sc = StandardCurve(compound_name="t", concentrations=[], areas=[])
    sc.slope, sc.intercept, sc._fitted = 1000.0, 0.0, True
    sc.lloq, sc.uloq = 0.1, 5.0

    with caplog.at_level(logging.WARNING):
        conc = sc.predict(50_000.0)  # conc = 50, above uloq=5.0
    assert conc == pytest.approx(50.0)
    assert any("ABOVE ULOQ" in r.message for r in caplog.records)


def test_predict_silent_when_in_range(caplog):
    sc = StandardCurve(compound_name="t", concentrations=[], areas=[])
    sc.slope, sc.intercept, sc._fitted = 1000.0, 0.0, True
    sc.lloq, sc.uloq = 0.1, 5.0

    with caplog.at_level(logging.WARNING):
        conc = sc.predict(2000.0)  # conc = 2.0, within range
    assert conc == pytest.approx(2.0)
    assert not any("LLOQ" in r.message or "ULOQ" in r.message for r in caplog.records)


def test_in_quantifiable_range():
    sc = StandardCurve(compound_name="t", concentrations=[], areas=[])
    assert sc.in_quantifiable_range(1.0) is None  # unknown when lloq/uloq unset
    sc.lloq, sc.uloq = 0.1, 5.0
    assert sc.in_quantifiable_range(1.0) is True
    assert sc.in_quantifiable_range(50.0) is False
    assert sc.in_quantifiable_range(0.01) is False


def test_to_yaml_round_trips_loq(tmp_path):
    method = QuantMethod()
    sc = StandardCurve(compound_name="X", concentrations=[0.1, 5.0], areas=[100, 5000])
    sc.fit()
    method.standard_curves["X"] = sc

    out = tmp_path / "out.yaml"
    method.to_yaml(str(out))
    reloaded = QuantMethod.from_yaml(str(out))
    rsc = reloaded.standard_curves["X"]
    assert rsc.lloq == pytest.approx(0.1)
    assert rsc.uloq == pytest.approx(5.0)
