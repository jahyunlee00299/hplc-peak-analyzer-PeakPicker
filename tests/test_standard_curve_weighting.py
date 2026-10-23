"""Weighted least squares for StandardCurve (opt-in; the default stays ordinary least squares)."""
import numpy as np
import pytest

from peakpicker.quant.method_config import QuantMethod, StandardCurve

# Synthetic standards: area scatter grows with concentration (constant relative error pattern).
X = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
Y = [105.0, 480.0, 1040.0, 4800.0, 10600.0, 49000.0]


def _wls(x, y, k):
    x, y = np.asarray(x, float), np.asarray(y, float)
    sw = x ** (-k / 2.0)
    A = np.column_stack([x, np.ones_like(x)]) * sw[:, None]
    slope, intercept = np.linalg.lstsq(A, y * sw, rcond=None)[0]
    return slope, intercept


def test_default_is_ordinary_least_squares():
    sc = StandardCurve(compound_name="t", concentrations=X, areas=Y)
    sc.fit()
    slope, intercept = np.polyfit(X, Y, 1)
    assert sc.weighting == "none"
    assert sc.slope == pytest.approx(slope) and sc.intercept == pytest.approx(intercept)


@pytest.mark.parametrize("weighting,k", [("1/x", 1), ("1/x2", 2)])
def test_weighted_fit_matches_normal_equations(weighting, k):
    sc = StandardCurve(compound_name="t", concentrations=X, areas=Y, weighting=weighting)
    sc.fit()
    slope, intercept = _wls(X, Y, k)
    assert sc.slope == pytest.approx(slope, rel=1e-9)
    assert sc.intercept == pytest.approx(intercept, rel=1e-9, abs=1e-9)


def test_weighting_moves_the_low_end():
    ols = StandardCurve(compound_name="t", concentrations=X, areas=Y)
    wls = StandardCurve(compound_name="t", concentrations=X, areas=Y, weighting="1/x2")
    ols.fit(), wls.fit()
    # back-calculated lowest standard: the weighted curve is closer to the truth (0.1)
    assert abs(wls.predict(Y[0]) - X[0]) < abs(ols.predict(Y[0]) - X[0])


def test_zero_concentration_with_weighting_is_rejected():
    sc = StandardCurve(compound_name="t", concentrations=[0.0, 1.0, 2.0], areas=[1.0, 100.0, 200.0], weighting="1/x")
    with pytest.raises(ValueError, match="> 0"):
        sc.fit()


def test_unknown_weighting_is_rejected():
    sc = StandardCurve(compound_name="t", concentrations=X, areas=Y, weighting="1/sqrt(x)")
    with pytest.raises(ValueError, match="weighting must be one of"):
        sc.fit()


def test_yaml_round_trip_keeps_weighting(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(
        "standard_curves:\n  X:\n    concentrations: [0.1, 1.0, 10.0]\n    areas: [10.0, 101.0, 1005.0]\n"
        "    weighting: 1/x2\n", encoding="utf-8")
    m = QuantMethod.from_yaml(str(p))
    assert m.standard_curves["X"].weighting == "1/x2"
    out = tmp_path / "out.yaml"
    m.to_yaml(out)
    assert QuantMethod.from_yaml(str(out)).standard_curves["X"].weighting == "1/x2"


# ── ICH detection limits from the calibration residuals ─────────────────────

def test_detection_limits_follow_ich_formula():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [10.1, 19.8, 30.3, 39.7, 50.1]
    sc = StandardCurve(compound_name="t", concentrations=x, areas=y)
    lod, loq = sc.detection_limits()
    slope, intercept = np.polyfit(x, y, 1)
    s_res = np.sqrt(np.sum((np.array(y) - (slope * np.array(x) + intercept)) ** 2) / 3)
    assert lod == pytest.approx(3.3 * s_res / slope)
    assert loq == pytest.approx(10 * s_res / slope)
    assert loq / lod == pytest.approx(10 / 3.3)


def test_detection_limits_undefined_cases():
    assert StandardCurve(compound_name="t", concentrations=[1.0, 2.0], areas=[10.0, 20.0]).detection_limits() is None
    weighted = StandardCurve(compound_name="t", concentrations=X, areas=Y, weighting="1/x")
    assert weighted.detection_limits() is None
    prefit = StandardCurve(compound_name="t", concentrations=[], areas=[])
    prefit.slope, prefit.intercept, prefit._fitted = 1000.0, 0.0, True
    assert prefit.detection_limits() is None


def test_detection_limits_do_not_touch_loq_fields():
    sc = StandardCurve(compound_name="t", concentrations=X, areas=Y)
    sc.detection_limits()
    assert sc.llod is None and sc.ulod is None
