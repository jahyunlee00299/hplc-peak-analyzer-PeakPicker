"""
sample_parser.py — Sample metadata parsing from folder names.

OCP: SampleParser Protocol defines the interface.
     New experiment formats add a new class — existing code untouched.
LSP: XulSampleParser and GenericSampleParser are fully interchangeable.
"""
import re
from pathlib import Path
from typing import List, Protocol, runtime_checkable

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


class XylAcPSampleParser:
    """
    Parser for XylAcP (Xylulose-5P production) experiment naming convention.

    Folder naming: 260506_XYLACP_{acp_mM}_{rep}_{time}H.D
    NC folders (Negative Control): suffix _NC_

    Issue: Chemstation sequence table had NC vials appended at the end of the
    run rather than after each ACP group. As a result, the folder names are
    shifted by one position relative to the actual sample identity.
    The correct_sample_name field on SampleMeta stores the resolved name.

    Shift rule (confirmed 2026-05-11):
      - Folders 1–6   (50_1..5, 50_NC)  → actual samples 50_1..5, 100_1
      - Folders 7–12  (100_1..5, 100_NC) → actual samples 100_2..5, 150_1..2
      - etc.  (i.e. every _NC_ folder becomes the first rep of the next group)
      - Last 4 _NC_ folders → NC_50 / NC_100 / NC_150 / NC_200

    post_classify() applies the shift correction to the full sample list.
    """

    # Ordered list of (folder_stem_upper_prefix, correct_sample_name)
    # Built dynamically from the sorted run order; see post_classify().

    def parse(self, folder: Path) -> SampleMeta:
        name = folder.stem.upper()
        meta = SampleMeta(sample_id=folder.stem, folder=folder)

        m = re.search(r"XYLACP_(\d+)_", name)
        if m:
            meta.acp_mM = float(m.group(1))

        m = re.search(r"_(\d+(?:_\d+)?)H(?:\.D)?$", name)
        if m:
            meta.time_h = float(m.group(1).replace("_", "."))

        if "_NC_" in name:
            meta.is_ne = True          # reuse is_ne flag for NC
            meta.condition = "NC_raw"  # will be corrected in post_classify
        else:
            meta.condition = "xylacp"

        return meta

    def post_classify(self, samples: List[SampleMeta]) -> List[SampleMeta]:
        """Apply the folder-name → correct-sample-name shift correction.

        The sequence table ran samples in order:
          50×5, NC(→100_1), 100×4, NC(→150_1), 150×4, NC(→200_1), 200×5, NC_50..NC_200
        correct_sample_name is stored in SampleMeta.correct_sample_name.
        """
        # Correct names in run order (index 0 = first non-blank sample)
        correct_names = [
            "XylAcP_50_1",  "XylAcP_50_2",  "XylAcP_50_3",  "XylAcP_50_4",  "XylAcP_50_5",
            "XylAcP_100_1", "XylAcP_100_2", "XylAcP_100_3", "XylAcP_100_4", "XylAcP_100_5",
            "XylAcP_150_1", "XylAcP_150_2", "XylAcP_150_3", "XylAcP_150_4", "XylAcP_150_5",
            "XylAcP_200_1", "XylAcP_200_2", "XylAcP_200_3", "XylAcP_200_4", "XylAcP_200_5",
            "NC_50", "NC_100", "NC_150", "NC_200",
        ]

        # Filter out blank/needle-wash (NV--) entries, keep run order
        run_samples = [s for s in samples if not s.sample_id.upper().startswith("NV")]

        for i, s in enumerate(run_samples):
            if i < len(correct_names):
                s.correct_sample_name = correct_names[i]
                # derive acp_mM from correct name
                m = re.search(r"XylAcP_(\d+)_", s.correct_sample_name)
                if m:
                    s.acp_mM = float(m.group(1))
                    s.condition = "xylacp"
                elif s.correct_sample_name.startswith("NC_"):
                    s.is_ne = True
                    s.condition = "NC"
                    m2 = re.search(r"NC_(\d+)", s.correct_sample_name)
                    if m2:
                        s.acp_mM = float(m2.group(1))

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

    # XylAcP production experiment: folder names contain "XYLACP"
    for folder in d_folders[:20]:
        if "XYLACP" in folder.stem.upper():
            return XylAcPSampleParser()

    xul_keywords = {"XUL5P", "XYL5P", "XYL", "ACP", "ATP", "XYLA", "XYLB"}
    for folder in d_folders[:20]:  # sample first 20
        upper = folder.stem.upper()
        for kw in xul_keywords:
            if kw in upper:
                return XulSampleParser()

    return GenericSampleParser()
