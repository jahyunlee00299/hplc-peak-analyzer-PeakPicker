"""MethodSelector reads its rules from each method YAML's `match:` block.

Uses the public synthetic example method (methods/example_hpx87h.yaml,
invented CompoundA/CompoundB, no lab-specific data) to exercise the
selection path without depending on any private YAML.
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from peakpicker.method_selector import MethodSelector  # noqa: E402

_METHODS_DIR = Path(__file__).resolve().parents[1] / "methods"


def test_selects_example_method_by_keyword(tmp_path):
    data_dir = tmp_path / "260101_EXAMPLE_COMPOUND_run"
    d_folder = data_dir / "sample_1.D"
    d_folder.mkdir(parents=True)
    (d_folder / "RID1A.ch").touch()

    result = MethodSelector.suggest(str(data_dir), str(_METHODS_DIR))

    assert result is not None
    assert Path(result).name == "example_hpx87h.yaml"


def test_no_match_and_no_fallback_signal_returns_none(tmp_path):
    data_dir = tmp_path / "unrelated_run"
    d_folder = data_dir / "sample_1.D"
    d_folder.mkdir(parents=True)
    (d_folder / "FID1A.ch").touch()  # a signal no rule in methods/ declares

    result = MethodSelector.suggest(str(data_dir), str(_METHODS_DIR))

    assert result is None
