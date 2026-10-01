"""Tests for the PyPI update notice (src/peakpicker/update_check.py).

The network is never touched: _fetch_latest_version is monkeypatched.
"""
import json
import time

import pytest


from peakpicker import update_check as uc  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    uc.reset_for_testing()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    # pytest re-sets PYTEST_CURRENT_TEST during the call phase, so drop it
    # from the skip list here; test_pytest_is_a_skip_env guards the real list.
    monkeypatch.setattr(uc, "SKIP_ENVS", (uc.DISABLE_ENV, "CI"))
    for k in uc.SKIP_ENVS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(uc, "_current_version", lambda: "2.0.1")
    yield
    uc.reset_for_testing()


def _fake_fetch(monkeypatch, version):
    calls = []
    def fetch(timeout=uc.TIMEOUT_SEC):
        calls.append(1)
        return version
    monkeypatch.setattr(uc, "_fetch_latest_version", fetch)
    return calls


@pytest.mark.parametrize("latest,current,expected", [
    ("2.0.2", "2.0.1", True),
    ("2.1", "2.0.9", True),
    ("10.0.0", "9.9.9", True),
    ("2.0.1", "2.0.1", False),
    ("2.0.0", "2.0.1", False),
    ("2.1.0rc1", "2.0.1", False),
])
def test_is_newer(latest, current, expected):
    assert uc._is_newer(latest, current) is expected


def test_notifies_when_newer(monkeypatch, capsys):
    _fake_fetch(monkeypatch, "2.0.2")
    uc.maybe_notify_update()
    err = capsys.readouterr().err
    assert "2.0.2 is available" in err and "pip install -U hplc-peakpicker" in err


def test_silent_when_current(monkeypatch, capsys):
    _fake_fetch(monkeypatch, "2.0.1")
    uc.maybe_notify_update()
    assert capsys.readouterr().err == ""


def test_once_per_process(monkeypatch, capsys):
    calls = _fake_fetch(monkeypatch, "2.0.2")
    uc.maybe_notify_update()
    uc.maybe_notify_update()
    assert len(calls) == 1
    assert capsys.readouterr().err.count("is available") == 1


def test_fresh_cache_skips_network(monkeypatch, capsys):
    uc._write_cache("2.0.3")
    calls = _fake_fetch(monkeypatch, "9.9.9")
    uc.maybe_notify_update()
    assert calls == []
    assert "2.0.3 is available" in capsys.readouterr().err


def test_stale_cache_refetches(monkeypatch):
    path = uc._cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"checked_at": time.time() - 2 * uc.CHECK_INTERVAL_SEC,
                                "latest": "2.0.1"}), encoding="utf-8")
    calls = _fake_fetch(monkeypatch, "2.0.1")
    uc.maybe_notify_update()
    assert len(calls) == 1


def test_pytest_is_a_skip_env():
    import importlib
    assert "PYTEST_CURRENT_TEST" in importlib.reload(uc).SKIP_ENVS


@pytest.mark.parametrize("env", [uc.DISABLE_ENV, "CI"])
def test_disabled_by_env(monkeypatch, capsys, env):
    monkeypatch.setenv(env, "1")
    calls = _fake_fetch(monkeypatch, "9.9.9")
    uc.maybe_notify_update()
    assert calls == [] and capsys.readouterr().err == ""


def test_offline_is_silent_and_not_cached(monkeypatch, capsys):
    _fake_fetch(monkeypatch, None)
    uc.maybe_notify_update()
    assert capsys.readouterr().err == ""
    assert not uc._cache_file().exists()


def test_check_for_update_explicit(monkeypatch):
    _fake_fetch(monkeypatch, "2.0.2")
    assert uc.check_for_update() == "2.0.2"
    _fake_fetch(monkeypatch, "2.0.1")
    assert uc.check_for_update() is None
