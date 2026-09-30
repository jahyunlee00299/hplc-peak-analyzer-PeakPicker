"""Data-root precedence: explicit > $CHEM32_DATA > <OneDrive>/HPLC_DATA > platform default."""
from pathlib import Path

from peakpicker.config import paths


def _fake_home(monkeypatch, tmp_path, with_synced=True):
    home = tmp_path / "home"
    od = home / "OneDrive - Example"
    od.mkdir(parents=True)
    if with_synced:
        (od / paths.SYNCED_DATA_DIRNAME).mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv(paths.CHEM32_DATA_ENV, raising=False)
    return od / paths.SYNCED_DATA_DIRNAME


def test_synced_folder_found(monkeypatch, tmp_path):
    synced = _fake_home(monkeypatch, tmp_path)
    assert paths.get_data_root() == synced


def test_env_beats_synced(monkeypatch, tmp_path):
    _fake_home(monkeypatch, tmp_path)
    monkeypatch.setenv(paths.CHEM32_DATA_ENV, str(tmp_path / "env_root"))
    assert paths.get_data_root() == tmp_path / "env_root"


def test_explicit_beats_everything(monkeypatch, tmp_path):
    _fake_home(monkeypatch, tmp_path)
    monkeypatch.setenv(paths.CHEM32_DATA_ENV, str(tmp_path / "env_root"))
    assert paths.get_data_root(tmp_path / "x") == tmp_path / "x"


def test_default_when_no_synced_folder(monkeypatch, tmp_path):
    _fake_home(monkeypatch, tmp_path, with_synced=False)
    monkeypatch.setattr(paths, "_onedrive_roots", lambda: sorted(Path.home().glob("OneDrive*")))
    assert paths.get_data_root() == paths.DEFAULT_CHEM32_DATA_ROOT
