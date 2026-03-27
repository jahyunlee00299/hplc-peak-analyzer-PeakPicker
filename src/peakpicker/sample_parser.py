"""
sample_parser.py — Sample metadata parsing from folder names.

OCP: SampleParser Protocol defines the interface.
     New experiment formats add a new class — existing code untouched.
LSP: XulSampleParser and GenericSampleParser are fully interchangeable.
"""
import re
from pathlib import Path
from typing import List, Optional, Protocol, runtime_checkable

from .models import SampleMeta


@runtime_checkable
class SampleParser(Protocol):
    """OCP: implement this Protocol to support new experiment naming schemes."""

    def parse(self, folder: Path) -> SampleMeta:
        """Parse a .D folder into SampleMeta."""
        ...

    def post_classify(self, samples: List[SampleMeta]) -> List[SampleMeta]:
        """Post-process the full sample list to refine conditions."""
        ...


class XulSampleParser:
    """
    Parser for XUL5P experiment naming convention.

    Parses tokens like _NE_, _FED_, _3X3X_, _50XYL, _100ACP, _1ATP, _3H.
    """

    def parse(self, folder: Path) -> SampleMeta:
        name = folder.stem.upper()
        meta = SampleMeta(sample_id=folder.stem, folder=folder)

        if "_NE_" in name:
            meta.is_ne = True
            meta.condition = "NE"
        elif "_FED_" in name:
            meta.is_fed = True
            meta.condition = "fed_batch"

        m = re.search(r"_(\d+)XYL", name)
        if m:
            meta.xyl_mM = float(m.group(1))

        m = re.search(r"_(\d+)ACP", name)
        if m:
            meta.acp_mM = float(m.group(1))

        m = re.search(r"_(\d+(?:_\d+)?)ATP", name)
        if m:
            meta.atp_mM = float(m.group(1).replace("_", "."))

        m = re.search(r"_(\d+(?:_\d+)?)H(?:\.D)?$", name)
        if m:
            meta.time_h = float(m.group(1).replace("_", "."))

        m = re.search(r"_(\d+)X(\d+)X_", name)
        if m and not meta.is_ne and not meta.is_fed:
            meta.xyla = int(m.group(1))
            meta.xylb = int(m.group(2))
            meta.condition = "enzyme_ratio"
            if meta.acp_mM and meta.xyl_mM and meta.xyl_mM > 0:
                ratio = meta.acp_mM / meta.xyl_mM
                if abs(ratio - 1.0) > 0.05:
                    meta.condition = "substrate_conc"

        return meta

    def post_classify(self, samples: List[SampleMeta]) -> List[SampleMeta]:
        """Refine ATP-optimisation and substrate-concentration conditions."""
        atp_variants: set = set()
        for s in samples:
            if not s.is_ne and not s.is_fed and s.xyla == 3 and s.xylb == 3:
                if s.atp_mM is not None:
                    atp_variants.add(s.atp_mM)

        for s in samples:
            if s.condition == "enzyme_ratio" and s.xyla == 3 and s.xylb == 3:
                if len(atp_variants) > 2 and s.atp_mM in atp_variants - {1.0}:
                    s.condition = "atp_conc"
                elif s.acp_mM is not None and s.xyl_mM is not None:
                    ratio = s.acp_mM / s.xyl_mM if s.xyl_mM > 0 else 1.0
                    if abs(ratio - 1.0) > 0.05:
                        s.condition = "substrate_conc"
        return samples


class GenericSampleParser:
    """
    Fallback parser: extracts date_description from folder name only.
    Assigns condition = "unknown" and leaves all numeric fields as None.
    """

    def parse(self, folder: Path) -> SampleMeta:
        return SampleMeta(sample_id=folder.stem, folder=folder)

    def post_classify(self, samples: List[SampleMeta]) -> List[SampleMeta]:
        return samples


def get_parser(data_dir: str) -> SampleParser:
    """
    Factory: inspect folder names in *data_dir* and return the most
    appropriate SampleParser.

    Heuristic: if any .D folder contains XUL5P / XYL / ACP tokens,
    use XulSampleParser; otherwise use GenericSampleParser.
    """
    data_path = Path(data_dir)
    d_folders = list(data_path.glob("*.D"))
    if not d_folders:
        for sub in data_path.iterdir():
            if sub.is_dir() and not sub.name.endswith(".D"):
                d_folders.extend(sub.glob("*.D"))

    xul_keywords = {"XUL5P", "XYL5P", "XYL", "ACP", "ATP", "XYLA", "XYLB"}
    for folder in d_folders[:20]:  # sample first 20
        upper = folder.stem.upper()
        for kw in xul_keywords:
            if kw in upper:
                return XulSampleParser()

    return GenericSampleParser()
