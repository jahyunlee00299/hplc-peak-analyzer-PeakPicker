"""End-to-end: a plugin dropped in PEAKPICKER_PLUGIN_PATH registers a
SampleParser and a quantification preset, and the public registries pick
them up via get_parser()/get_preset() with no src/ code change.

Uses a synthetic parser/preset (no lab-specific data) to keep this test
generic and independent of whatever real plugins live in plugins/.
"""
import sys
import textwrap
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from peakpicker import plugins as plugins_mod  # noqa: E402
from peakpicker import sample_parser  # noqa: E402
from peakpicker.config import quantification_config as qcfg  # noqa: E402

_SYNTHETIC_PLUGIN = textwrap.dedent("""
    from pathlib import Path
    from peakpicker.models import SampleMeta
    from peakpicker.sample_parser import register_parser
    from peakpicker.config.quantification_config import (
        QuantificationConfig, register_preset,
    )


    class SyntheticParser:
        def parse(self, folder):
            meta = SampleMeta(sample_id=folder.stem, folder=folder)
            meta.synthetic_marker = True
            return meta

        def post_classify(self, samples):
            return samples


    def _detect(d_folders):
        return any("SYNTHETIC_TAG" in f.stem.upper() for f in d_folders)


    register_parser("synthetic", _detect, SyntheticParser, priority=100)


    def synthetic_preset(scale: float = 1.0) -> QuantificationConfig:
        cfg = QuantificationConfig()
        cfg.calibration.dilution_factor = scale
        return cfg


    register_preset("synthetic_preset", synthetic_preset)
""")


@pytest.fixture()
def synthetic_plugin_env(monkeypatch, tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "synthetic_plugin.py").write_text(_SYNTHETIC_PLUGIN, encoding="utf-8")
    monkeypatch.setenv("PEAKPICKER_PLUGIN_PATH", str(plugin_dir))

    parser_registry_snapshot = list(sample_parser._REGISTRY)
    preset_registry_snapshot = dict(qcfg._PRESET_REGISTRY)
    plugins_mod.reset_for_testing()

    yield

    plugins_mod.reset_for_testing()
    sample_parser._REGISTRY[:] = parser_registry_snapshot
    qcfg._PRESET_REGISTRY.clear()
    qcfg._PRESET_REGISTRY.update(preset_registry_snapshot)


def test_plugin_registered_parser_is_picked_up(synthetic_plugin_env, tmp_path):
    data_dir = tmp_path / "run"
    (data_dir / "260101_SYNTHETIC_TAG_1.D").mkdir(parents=True)

    parser = sample_parser.get_parser(str(data_dir))

    assert type(parser).__name__ == "SyntheticParser"
    meta = parser.parse(next((data_dir).glob("*.D")))
    assert meta.synthetic_marker is True


def test_plugin_registered_preset_is_picked_up(synthetic_plugin_env):
    fn = qcfg.get_preset("synthetic_preset")
    cfg = fn(scale=2.5)
    assert cfg.calibration.dilution_factor == 2.5
