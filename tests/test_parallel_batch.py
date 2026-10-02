"""--jobs N must give results identical to the serial path (file-level process pool)."""
import multiprocessing
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import hplc_analyzer_enhanced as hae  # noqa: E402


def _have_mp():
    try:
        multiprocessing.get_context('spawn')
        return True
    except Exception:  # pragma: no cover
        return False


pytestmark = pytest.mark.skipif(not _have_mp(), reason='multiprocessing unavailable')


def _write_csv(path, seed):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 10, 1200)
    y = (50 * np.exp(-0.5 * ((t - 3.0) / 0.08) ** 2) + 80 * np.exp(-0.5 * ((t - 6.0) / 0.1) ** 2)
         + 30 * np.exp(-0.5 * ((t - 6.25) / 0.1) ** 2) + rng.normal(0, 0.2, t.size) + 5)
    text = ''.join(f'{a:.4f}\t{b:.5f}\r\n' for a, b in zip(t, y))
    path.write_bytes(b'\xff\xfe' + text.encode('utf-16-le'))


def _run(data, out, jobs):
    analyzer = hae.EnhancedHPLCAnalyzer(str(data), str(out))
    return analyzer.batch_analyze('*.CSV', jobs=jobs)


def _sheets(path):
    book = pd.read_excel(path, sheet_name=None)
    book['Summary'] = book['Summary'].drop(columns=['Analysis Date'])  # timestamp differs per run
    return book


def test_parallel_equals_serial(tmp_path, capsys):
    data = tmp_path / 'data'
    data.mkdir()
    for i in range(3):
        _write_csv(data / f's{i}.CSV', i)
    (data / 'bad.CSV').write_bytes(b'not a chromatogram')  # must fail alone, not kill the batch

    ser = _run(data, tmp_path / 'ser', 1)
    capsys.readouterr()
    par = _run(data, tmp_path / 'par', 2)
    out = capsys.readouterr().out

    assert [r['file'] for r in ser] == [r['file'] for r in par]
    assert [('error' in r) for r in ser] == [('error' in r) for r in par] == [True, False, False, False]
    assert out.index('Analyzing: bad.CSV') < out.index('Analyzing: s0.CSV') < out.index('Analyzing: s2.CSV')
    for a, b in zip(ser, par):
        if 'error' in a:
            assert a['error'] == b['error']
            continue
        for key in ('time', 'intensity', 'baseline', 'corrected'):
            assert np.array_equal(a[key], b[key])
        assert a['peak_data'] == b['peak_data']
    for f in sorted((tmp_path / 'ser').glob('*.xlsx')):
        s, p = _sheets(f), _sheets(tmp_path / 'par' / f.name)
        assert s.keys() == p.keys()
        for name in s:
            pd.testing.assert_frame_equal(s[name], p[name], check_exact=True)
    assert len(list((tmp_path / 'par').glob('*.xlsx'))) == 3
