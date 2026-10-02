"""Legacy modules must import under both sys.path layouts: `src` on the path, or only the repo root."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SNIPPET = "import numpy as np; m = __import__('{mod}', fromlist=['x']); print(callable(m.{attr}))"


@pytest.mark.parametrize("layout,mod", [("src", "peak_integrator"), ("root", "src.peak_integrator"),
                                         ("src", "peak_models"), ("root", "src.peak_models"),
                                         ("src", "hybrid_baseline"), ("root", "src.hybrid_baseline")])
def test_legacy_module_imports_under_layout(layout, mod, tmp_path):
    path = str(ROOT / "src") if layout == "src" else str(ROOT)
    attr = {"peak_integrator": "integrate_peak_detailed", "peak_models": "gaussian", "hybrid_baseline": "HybridBaselineCorrector"}[mod.split(".")[-1]]
    env = dict(os.environ, PYTHONPATH=path)
    r = subprocess.run([sys.executable, "-c", SNIPPET.format(mod=mod, attr=attr)], cwd=tmp_path, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-500:]
    assert r.stdout.strip().endswith("True")
