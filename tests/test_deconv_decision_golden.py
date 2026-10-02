"""Decision golden for ``deconvolve_peak``: selected model, n_components and component areas on
synthetic chromatograms, frozen from commit c53f76e (before the speed work).

A performance change must not move any of these. Regenerate (only for a deliberate behaviour change)
with ``python tests/golden/deconv_decision_golden.py synthetic --write``.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'golden'))
import deconv_decision_golden as golden  # noqa: E402

GOLDEN = json.loads(golden.SYNTH_GOLDEN.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def current():
    return golden.run_synthetic()


@pytest.mark.parametrize('name', sorted(GOLDEN))
def test_decision_matches_golden(name, current):
    g, n = GOLDEN[name], current[name]
    assert (n['success'], n['n'], n['method']) == (g['success'], g['n'], g['method'])
    total = abs(g['total'])
    for a, b in zip(g['comps'], n['comps']):
        assert abs(a['area'] - b['area']) <= golden.AREA_TOL_TOTAL * total
        assert a['model'] == b['model']
    assert abs(g['total'] - n['total']) <= golden.AREA_TOL_TOTAL * total


def test_required_adversarial_cases_are_in_the_golden():
    assert GOLDEN['single_gauss_hi_snr_s1']['n'] == 1
    assert GOLDEN['pair_2.15sigma_equal_s1']['n'] == 2
    assert GOLDEN['tailing_emg_s1']['method'] == '1-EMG'
    assert GOLDEN['shoulder_20']['n'] == 2
