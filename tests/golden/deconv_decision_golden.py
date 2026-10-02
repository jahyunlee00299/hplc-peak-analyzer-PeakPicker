"""Decision golden for ``PeakDeconvolution.deconvolve_peak`` (selected model, n_components, areas).

Freezes WHAT the deconvolution decides so that speed work can be proven behaviour-preserving.

  python tests/golden/deconv_decision_golden.py synthetic --write      # regenerate synthetic golden
  python tests/golden/deconv_decision_golden.py synthetic --check
  python tests/golden/deconv_decision_golden.py real --data <dir of CSV> --golden <json outside repo> --write|--check

``real`` captures every ``deconvolve_peak`` input the enhanced analyzer would make (production peaks plus
forced deconvolution of the 5 largest peaks, 40-file sample = stride 5, offsets 0-3) and stores the decisions
in a JSON that must live OUTSIDE the repository (real data is never committed). It prints which
``peak_deconvolution`` file was loaded. Set ``PP_TREE`` to a source tree to load the code from there
(used to freeze a golden from an older commit); default is the tree this file sits in.
"""
import argparse
import contextlib
import glob
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get('PP_TREE') or Path(__file__).resolve().parents[2]).resolve()
for _p in (str(ROOT / 'src'), str(ROOT)):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

import peak_deconvolution as pdv  # noqa: E402

SYNTH_GOLDEN = Path(__file__).with_name('deconv_synthetic_golden.json')
AREA_TOL_TOTAL = 1e-3   # component/total area agreement, fraction of the total area


def _g(x, a, c, s):
    return a * np.exp(-0.5 * ((x - c) / s) ** 2)


def _emg(x, a, c, s, tau):
    from peak_models import exponentially_modified_gaussian
    return exponentially_modified_gaussian(x, a, c, s, tau)


def synthetic_cases():
    """Deterministic (seeded) chromatogram windows covering the decisions that must not move."""
    out = {}
    x = np.linspace(3.0, 7.0, 400)

    def noisy(y, seed, sd):
        return y + np.random.default_rng(seed).normal(0.0, sd, y.size)

    s = 0.12
    for seed in (1, 2, 3):
        out['single_gauss_hi_snr_s%d' % seed] = (x, noisy(_g(x, 100, 5.0, s), seed, 0.05))
    out['single_gauss_noisy'] = (x, noisy(_g(x, 100, 5.0, s), 4, 2.0))
    out['single_gauss_noise_free'] = (x, _g(x, 100, 5.0, s))
    for seed in (1, 2):
        out['pair_2.15sigma_equal_s%d' % seed] = (x, noisy(_g(x, 100, 5.0, s) + _g(x, 100, 5.0 + 2.15 * s, s), seed, 0.5))
    out['pair_2.15sigma_unequal'] = (x, noisy(_g(x, 100, 5.0, s) + _g(x, 60, 5.0 + 2.15 * s, s), 3, 0.5))
    out['pair_resolved_6sigma'] = (x, noisy(_g(x, 100, 4.5, s) + _g(x, 70, 4.5 + 6 * s, s), 4, 0.5))
    out['pair_1.2sigma_unresolvable'] = (x, noisy(_g(x, 100, 5.0, s) + _g(x, 100, 5.0 + 1.2 * s, s), 5, 0.5))
    for seed in (1, 2):
        out['tailing_emg_s%d' % seed] = (x, noisy(_emg(x, 100, 4.8, 0.08, 0.25), seed, 0.3))
    out['tailing_emg_strong'] = (x, noisy(_emg(x, 100, 4.6, 0.07, 0.45), 3, 0.3))
    for frac in (0.10, 0.15, 0.20):
        out['shoulder_%d' % round(frac * 100)] = (x, noisy(_g(x, 100, 5.0, s) + _g(x, 100 * frac, 5.0 + 2.6 * s, s), 6, 0.2))
    out['three_peaks'] = (x, noisy(_g(x, 100, 4.4, s) + _g(x, 80, 5.0, s) + _g(x, 60, 5.7, s), 7, 0.5))
    xs = np.linspace(4.7, 5.3, 12)
    out['short_window_12pts'] = (xs, noisy(_g(xs, 100, 5.0, s), 8, 0.3))
    xs = np.linspace(4.8, 5.2, 6)
    out['short_window_6pts'] = (xs, _g(xs, 100, 5.0, s))
    xs = np.linspace(4.0, 6.0, 40)
    out['coarse_grid_pair'] = (xs, noisy(_g(xs, 100, 4.8, 0.15) + _g(xs, 80, 5.3, 0.15), 9, 0.5))
    return out


def decision(res):
    return dict(success=bool(res.success), n=int(res.n_components), method=res.method,
                total=float(res.total_area), r2=float(res.fit_quality),
                comps=[dict(rt=float(c.retention_time), area=float(c.area), sigma=float(c.sigma),
                            tau=float(c.tau), model=c.model) for c in res.components])


def run_synthetic():
    dec = pdv.PeakDeconvolution()
    return {name: decision(dec.deconvolve_peak(rt, y, 0, len(rt) - 1))
            for name, (rt, y) in synthetic_cases().items()}


def compare(golden, new):
    """Return (n identical decisions, n golden, max |dA|/total over identical ones, problems)."""
    problems, same, max_dev = [], 0, 0.0
    for k, g in golden.items():
        n = new.get(k)
        if n is None:
            problems.append('%s missing' % k)
            continue
        if (g['success'], g['n'], g['method']) != (n['success'], n['n'], n['method']):
            problems.append('%s decision %s -> %s' % (k, (g['n'], g['method']), (n['n'], n['method'])))
            continue
        same += 1
        tot = max(abs(g['total']), 1e-300)
        devs = [abs(a['area'] - b['area']) / tot for a, b in zip(g['comps'], n['comps'])]
        devs.append(abs(g['total'] - n['total']) / tot)
        max_dev = max(max_dev, max(devs))
        if max(devs) > AREA_TOL_TOTAL:
            problems.append('%s area deviation %.3g of total' % (k, max(devs)))
    return same, len(golden), max_dev, problems


def capture_real(data_dir, stride=5, offsets=(0, 1, 2, 3)):
    """Capture deconvolve_peak inputs of the enhanced analyzer (fits stubbed out, so this is fast)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('hea', str(ROOT / 'scripts' / 'hplc_analyzer_enhanced.py'))
    hea = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hea)
    cases, cur = [], {}

    def stub(self, rt, signal, s, e, initial_centers=None):
        cases.append(dict(tag='%s:%s:%s' % (cur['kind'], cur['file'], cur['pk']),
                          rt=np.array(rt[s:e + 1]), y=np.array(signal[s:e + 1])))
        return self._create_failed_result(float(rt[s]), 'capture')

    real = pdv.PeakDeconvolution.deconvolve_peak
    pdv.PeakDeconvolution.deconvolve_peak = stub
    try:
        an = hea.EnhancedHPLCAnalyzer(str(data_dir), str(Path(os.environ.get('TMPDIR', '.')) / 'deconv_golden_out'))
        an._export_results = lambda *a, **k: None
        files = sorted(glob.glob(os.path.join(str(data_dir), '*.csv')))
        sel = [f for off in offsets for f in files[off::stride]]
        sink = io.StringIO()
        for csv in sel:
            cur.update(file=os.path.basename(csv), kind='prod', pk=-1)
            with contextlib.redirect_stdout(sink):
                r = an.analyze_csv_file(Path(csv))
            if not r or 'peak_data' not in r:
                continue
            t, y, peaks = r['time'], r['corrected'], r['peak_data']
            for i in sorted(range(len(peaks)), key=lambda i: -peaks[i]['area'])[:5]:
                s = int(np.argmin(abs(t - peaks[i]['start_time'])))
                e = int(np.argmin(abs(t - peaks[i]['end_time'])))
                cur.update(kind='forced', pk=i)
                with contextlib.redirect_stdout(sink):
                    an.deconvolution.analyze_peak(t, y, s, e, force_deconvolution=True)
    finally:
        pdv.PeakDeconvolution.deconvolve_peak = real
    return cases


def run_real(data_dir):
    cases = capture_real(data_dir)
    dec = pdv.PeakDeconvolution()
    out, timing = {}, {}
    for c in cases:
        key = hashlib.md5(c['rt'].tobytes() + c['y'].tobytes()).hexdigest()
        if key in out:
            continue
        t0 = time.perf_counter()
        out[key] = decision(dec.deconvolve_peak(c['rt'], c['y'], 0, len(c['rt']) - 1))
        timing[key] = time.perf_counter() - t0
    return out, timing


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=['synthetic', 'real'])
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--data')
    ap.add_argument('--golden')
    a = ap.parse_args(argv)
    print('peak_deconvolution loaded from', pdv.__file__)
    if a.mode == 'synthetic':
        res, path = run_synthetic(), SYNTH_GOLDEN
    else:
        if not a.data or not a.golden:
            ap.error('real mode needs --data and --golden')
        if ROOT in Path(a.golden).resolve().parents:
            ap.error('real-data golden must be stored outside the repository')
        t0 = time.time()
        res, timing = run_real(a.data)
        print('real cases %d, wall %.0fs, sum fit time %.0fs' % (len(res), time.time() - t0, sum(timing.values())))
        path = Path(a.golden)
    if a.write:
        path.write_text(json.dumps(res, indent=1, sort_keys=True), encoding='utf-8')
        print('wrote', path, len(res), 'cases')
    if a.check:
        same, n, dev, problems = compare(json.loads(path.read_text(encoding='utf-8')), res)
        print('decisions identical %d/%d, max |dA|/total %.3g' % (same, n, dev))
        for p in problems:
            print('  PROBLEM', p)
        return 1 if problems else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
