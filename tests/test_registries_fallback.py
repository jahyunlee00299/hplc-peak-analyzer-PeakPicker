"""Registry-fallback tests: with no experiment-specific plugin registered,
the public registries must fall back cleanly (GenericSampleParser, KeyError
listing available preset names) rather than assuming lab-specific code exists.

Isolated from whatever is in the real plugins/ directory by pointing
PEAKPICKER_PLUGIN_PATH at an empty temp dir and resetting/restoring the
in-process registries around the test.
"""
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from peakpicker import plugins as plugins_mod  # noqa: E402
from peakpicker import sample_parser  # noqa: E402
from peakpicker.config import quantification_config as qcfg  # noqa: E402


@pytest.fixture()
def isolated_registries(monkeypatch, tmp_path):
    """Point plugin loading at an empty dir and snapshot/restore registries."""
    empty_dir = tmp_path / "empty_plugins"
    empty_dir.mkdir()
    monkeypatch.setenv("PEAKPICKER_PLUGIN_PATH", str(empty_dir))

    parser_registry_snapshot = list(sample_parser._REGISTRY)
    preset_registry_snapshot = dict(qcfg._PRESET_REGISTRY)
    sample_parser._REGISTRY.clear()
    qcfg._PRESET_REGISTRY.clear()
    qcfg.register_preset("default", qcfg._default_preset)
    qcfg.register_preset("time_course_analysis", qcfg._time_course_analysis_preset)
    plugins_mod.reset_for_testing()

    yield

    plugins_mod.reset_for_testing()
    sample_parser._REGISTRY[:] = parser_registry_snapshot
    qcfg._PRESET_REGISTRY.clear()
    qcfg._PRESET_REGISTRY.update(preset_registry_snapshot)


def test_get_parser_falls_back_to_generic_with_no_plugins(isolated_registries, tmp_path):
    data_dir = tmp_path / "some_run"
    (data_dir / "sample_1.D").mkdir(parents=True)

    parser = sample_parser.get_parser(str(data_dir))

    assert type(parser).__name__ == "GenericSampleParser"


def test_get_preset_unknown_name_raises_keyerror_listing_available(isolated_registries):
    with pytest.raises(KeyError) as excinfo:
        qcfg.get_preset("not_a_real_preset")

    message = str(excinfo.value)
    assert "not_a_real_preset" in message
    assert "default" in message
    assert "time_course_analysis" in message
