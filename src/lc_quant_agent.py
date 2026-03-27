# lc_quant_agent.py — backward compatibility shim
# All logic now lives in src/peakpicker/
from peakpicker.agent import LCQuantAgent
from peakpicker.method_selector import MethodSelector
from peakpicker.chromatogram_io import ChromatogramParser as ChromatogramLoader

__all__ = ["LCQuantAgent", "MethodSelector", "ChromatogramLoader"]
