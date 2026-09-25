"""Tests for the plugin loader (src/peakpicker/plugins.py).

Covers: idempotent loading, missing-dir no-op, malformed-plugin warning
(never a crash), and picking up PEAKPICKER_PLUGIN_PATH.
"""
import sys
import textwrap
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from peakpicker import plugins as plugins_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_plugin_loader_state():
    """Every test gets a fresh load_plugins() idempotency guard."""
    plugins_mod.reset_for_testing()
    yield
    plugins_mod.reset_for_testing()


def test_missing_plugin_dir_is_noop(monkeypatch, tmp_path):
    missing = tmp_path / "does_not_exist"
    monkeypatch.setenv("PEAKPICKER_PLUGIN_PATH", str(missing))
    # Must not raise.
    plugins_mod.load_plugins()


def test_load_plugins_imports_py_files_and_skips_underscore(monkeypatch, tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    marker_file = tmp_path / "marker.txt"
    (plugin_dir / "good_plugin.py").write_text(
        textwrap.dedent(f"""
            from pathlib import Path
            Path(r"{marker_file}").write_text("loaded")
        """),
        encoding="utf-8",
    )
    (plugin_dir / "_private_helper.py").write_text(
        "raise RuntimeError('must not be imported: starts with _')",
        encoding="utf-8",
    )
    monkeypatch.setenv("PEAKPICKER_PLUGIN_PATH", str(plugin_dir))

    plugins_mod.load_plugins()

    assert marker_file.exists()
    assert marker_file.read_text(encoding="utf-8") == "loaded"


def test_load_plugins_is_idempotent(monkeypatch, tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    counter_file = tmp_path / "count.txt"
    counter_file.write_text("0", encoding="utf-8")
    (plugin_dir / "counting_plugin.py").write_text(
        textwrap.dedent(f"""
            from pathlib import Path
            p = Path(r"{counter_file}")
            p.write_text(str(int(p.read_text()) + 1))
        """),
        encoding="utf-8",
    )
    monkeypatch.setenv("PEAKPICKER_PLUGIN_PATH", str(plugin_dir))

    plugins_mod.load_plugins()
    plugins_mod.load_plugins()
    plugins_mod.load_plugins()

    assert counter_file.read_text(encoding="utf-8") == "1"


def test_malformed_plugin_warns_but_does_not_crash(monkeypatch, tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "broken_plugin.py").write_text(
        "raise ValueError('boom')", encoding="utf-8",
    )
    (plugin_dir / "z_ok_plugin.py").write_text(
        "OK = True", encoding="utf-8",
    )
    monkeypatch.setenv("PEAKPICKER_PLUGIN_PATH", str(plugin_dir))

    with pytest.warns(UserWarning, match="broken_plugin"):
        plugins_mod.load_plugins()
    # The failure of one plugin must not stop the rest from loading.
    assert "z_ok_plugin" in sys.modules or any(
        "z_ok_plugin" in name for name in sys.modules
    )
