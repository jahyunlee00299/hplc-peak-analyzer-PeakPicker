"""
method_selector.py — Auto-selection of method YAML from data directory.

SRP: Only responsible for recommending a method YAML path.
OCP: Extend RULES list to support new methods — no existing logic changes.
"""
from pathlib import Path
from typing import List, Optional, Tuple

from .chromatogram_io import SignalFileResolver


class MethodSelector:
    """
    Inspect data_dir to recommend the appropriate method YAML file.

    Rules are checked in order; the first matching rule wins.
    """

    # (signal_file_pattern, folder_keyword_upper | None, yaml_name)
    RULES: List[Tuple[str, Optional[str], str]] = [
        ("RID1A.ch", "XUL5P",   "xyl5p_hpx87h.yaml"),
        ("RID1A.ch", "XYLB",    "xyl5p_hpx87h.yaml"),
        ("RID1A.ch", "XYLA",    "xyl5p_hpx87h.yaml"),
        ("RID1A.ch", "XYL5P",   "xyl5p_hpx87h.yaml"),
        ("RID1A.ch", "FUFROM",  "deoxynucleoside_hpx87h.yaml"),
        ("RID1A.ch", "DRRIB",   "deoxynucleoside_hpx87h.yaml"),
        ("RID1A.ch", "DEOXYNU", "deoxynucleoside_hpx87h.yaml"),
        ("RID1A.ch", "L-RIB",   "lrib_hpx87h.yaml"),
        ("RID1A.ch", "LRIB",    "lrib_hpx87h.yaml"),
        ("RID1A.ch", "AGAROB",  "lrib_hpx87h.yaml"),
        ("vwd1A.ch", None,      "nucleoside_c18_uv.yaml"),
        ("DAD1A.ch", None,      "nucleoside_c18_uv.yaml"),
    ]

    _SIGNAL_CANDIDATES = SignalFileResolver._SIGNAL_CANDIDATES

    @classmethod
    def suggest(cls, data_dir: str, methods_dir: str) -> Optional[str]:
        """
        Return the full path of the recommended YAML, or None if no match.

        Parameters
        ----------
        data_dir   : directory containing .D sample folders
        methods_dir: directory containing YAML method files
        """
        data_path = Path(data_dir)
        methods_path = Path(methods_dir)
        dir_upper = data_path.name.upper()

        # Collect .D folders (direct + one level of subdirectories)
        d_folders: List[Path] = list(data_path.glob("*.D"))
        for sub in data_path.iterdir():
            if sub.is_dir() and not sub.name.endswith(".D"):
                d_folders.extend(sub.glob("*.D"))

        detected_signals: set = set()
        for d_folder in d_folders:
            for cand in cls._SIGNAL_CANDIDATES:
                if (d_folder / cand).exists():
                    detected_signals.add(cand)

        print(f"[MethodSelector] folder: {data_path.name}")
        print(f"  detected signal files: {detected_signals or 'none'}")

        for sig_pattern, folder_kw, yaml_name in cls.RULES:
            if sig_pattern not in detected_signals:
                continue
            if folder_kw is not None and folder_kw not in dir_upper:
                parent_upper = str(data_path).upper()
                if folder_kw not in parent_upper:
                    continue
            yaml_path = methods_path / yaml_name
            if yaml_path.exists():
                print(f"  => recommended method: {yaml_name}")
                return str(yaml_path)
            else:
                print(f"  [WARN] rule matched but YAML missing: {yaml_name}")

        # Fallback
        if "RID1A.ch" in detected_signals:
            fallback = methods_path / "xyl5p_hpx87h.yaml"
            if fallback.exists():
                print(f"  => fallback method: xyl5p_hpx87h.yaml")
                return str(fallback)

        print(f"  [SKIP] no suitable method found.")
        return None
