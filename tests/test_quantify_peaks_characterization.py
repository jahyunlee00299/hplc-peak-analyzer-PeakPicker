"""Characterization of scripts/quantify_peaks.PeakQuantifier: results tables and figure artist data.

Synthetic input: three replicate samples (``REP_1_/_2_/_3_`` -> one overlay group) and one singleton, each a few
Gaussians on a drifting baseline with fixed-seed noise, written as the UTF-16-LE tab-separated CSVs the script reads.
Figures are compared through a canonical fingerprint of their artist data (titles, labels, scales, limits, line
xy data, texts, table cells, scatter offsets) taken at ``savefig`` time, so the plotting code can move without a
pixel comparison. GOLDEN was recorded from the pre-refactor script (commit 9790964 + batch 3 units 1-2).
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quantify_peaks.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("quantify_peaks_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plt.rcParams["font.family"] = "DejaVu Sans"        # the script asks for a Windows-only font
    return mod


def _gauss(t, a, c, s):
    return a * np.exp(-0.5 * ((t - c) / s) ** 2)


SAMPLES = {
    "REP_1_": (1, [(900.0, 5.0, 0.12), (400.0, 8.0, 0.15)]),
    "REP_2_": (2, [(950.0, 5.01, 0.12), (420.0, 8.0, 0.16)]),
    "REP_3_": (3, [(880.0, 4.99, 0.12), (390.0, 8.02, 0.15)]),
    "LONE": (4, [(600.0, 6.0, 0.2)]),
}


def write_inputs(folder: Path) -> None:
    t = np.linspace(0.0, 12.0, 1201)
    for name, (seed, peaks) in SAMPLES.items():
        y = 50.0 + 3.0 * t + sum(_gauss(t, *p) for p in peaks) + np.random.default_rng(seed).normal(0.0, 0.8, t.size)
        pd.DataFrame({0: t, 1: y}).to_csv(folder / f"{name}.csv", header=False, index=False, sep="\t", encoding="utf-16-le")


def _r(a, nd=6):
    return np.round(np.asarray(a, dtype=float), nd).tolist()


def fingerprint(fig) -> str:
    rec = {"size": _r(fig.get_size_inches()), "suptitle": fig._suptitle.get_text() if fig._suptitle else None, "axes": []}
    for ax in fig.axes:
        a = {
            "title": ax.get_title(), "xlabel": ax.get_xlabel(), "ylabel": ax.get_ylabel(),
            "xscale": ax.get_xscale(), "yscale": ax.get_yscale(), "xlim": _r(ax.get_xlim(), 4),
            "axis_on": ax.axison,
            "lines": [[l.get_label(), l.get_color() if isinstance(l.get_color(), str) else _r(l.get_color()),
                       l.get_linestyle(), l.get_linewidth(), _r(l.get_xdata()), _r(l.get_ydata(), 4)] for l in ax.lines],
            "texts": [[t.get_text(), _r(t.get_position(), 4)] for t in ax.texts],
            "annotations": [t.get_text() for t in ax.get_children() if t.__class__.__name__ == "Annotation"],
            "tables": [[sorted((k, c.get_text().get_text()) for k, c in tb.get_celld().items())] for tb in ax.tables],
            "collections": [[c.__class__.__name__, _r(c.get_offsets(), 4) if hasattr(c, "get_offsets") and len(c.get_offsets()) else None]
                            for c in ax.collections],
            "patch_count": len(ax.patches),
            "legend": [t.get_text() for t in ax.get_legend().get_texts()] if ax.get_legend() else None,
        }
        rec["axes"].append(a)
    return hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    mod = _load_script()
    src = tmp_path_factory.mktemp("in")
    write_inputs(src)
    out = tmp_path_factory.mktemp("out")

    fingerprints, real_savefig = {}, plt.savefig

    def spy(path, *a, **k):
        fingerprints[Path(path).name] = fingerprint(plt.gcf())
        return real_savefig(path, *a, **k)

    plt.savefig = spy
    try:
        q = mod.PeakQuantifier()
        df = q.analyze_folder(src)
        q.create_summary_report(df, out)
    finally:
        plt.savefig = real_savefig
    return {"df": df, "out": out, "fingerprints": fingerprints, "quantifier": q}


GOLDEN_TABLE_SHA = "36077fcb75e579c4a8955f12af06ae54ac5b3e978dbf5a041615f79002122350"
GOLDEN_CSV_SHA = GOLDEN_TABLE_SHA
GOLDEN_FIGURES = {
    "peak_information_summary.png": "efcd7d90970c812bfc85243ff11ac4e2acf5c5ea5ee7308e5816835a02068290",
    "LONE_chromatogram.png": "f07a043af4bcd609acb364d891f03ca182fc7b7e0efa6fcfe84ccfd17e803695",
    "REP_1__chromatogram.png": "8faec701cef021ac454aff399971916c0316e38532bf0c1cc3faa2b5e69c1ea3",
    "REP_2__chromatogram.png": "0b6bb1f2b228ac66d93aa7582a9e6c722c704df1978b022c4b38985ffadbbbff",
    "REP_3__chromatogram.png": "1b7d32d268bf82092a02722c7ee131e9310aa76d9c535c2f90be4f2897ae98ce",
    "REP_overlay.png": "de93850e5823c78b844f4cc7641bfc7420305b1743403b0695cde4c761795e07",
}


def _table_sha(df):
    d = df.copy()
    for c in d.select_dtypes("float").columns:
        d[c] = d[c].round(4)
    return hashlib.sha256(d.to_csv(index=False).encode()).hexdigest()


def test_results_table_is_unchanged(run):
    df = run["df"]
    assert len(df) > 0 and set(df["sample"]) == {f"{n}" for n in SAMPLES}
    assert _table_sha(df) == GOLDEN_TABLE_SHA


def test_results_csv_values_are_unchanged(run):
    csv = pd.read_csv(run["out"] / "all_peaks_detailed.csv", encoding="utf-8-sig")
    assert _table_sha(csv) == GOLDEN_CSV_SHA


def test_figure_artist_data_is_unchanged(run):
    assert run["fingerprints"] == GOLDEN_FIGURES


def test_expected_files_exist(run):
    out = run["out"]
    assert (out / "peak_information_summary.png").exists() or (out / "overlays").exists()
    assert len(list((out / "chromatograms").glob("*.png"))) == len(SAMPLES)
    assert [p.name for p in (out / "overlays").glob("*.png")] == ["REP_overlay.png"]


def test_fingerprint_detects_a_changed_line_and_a_changed_label():
    """Refutation of the harness itself: it must not be blind to artist-data changes."""
    def fig_with(y_last=2.0, title="t"):
        fig, ax = plt.subplots()
        ax.plot([0, 1, 2], [0, 1, y_last], label="a")
        ax.set_title(title)
        return fig
    base, moved, retitled = fig_with(), fig_with(y_last=2.001), fig_with(title="u")
    fps = [fingerprint(f) for f in (base, moved, retitled)]
    for f in (base, moved, retitled):
        plt.close(f)
    assert len(set(fps)) == 3
