"""
method_selector.py — Auto-selection of method YAML from data directory.

SRP: Only responsible for recommending a method YAML path.
OCP: Rules are read from each method YAML's own ``match:`` block — adding a
     new method (with its own match block) requires no change to this file.

A method YAML may declare, at the top level::

    match:
      signal: RID1A.ch          # required — signal file this rule applies to
      keywords: [COMPOUND_A, COMPOUND_B] # optional — folder-name keywords
                                 # (upper-cased); omitted/empty = signal-only
                                 # rule (always matches when the signal is
                                 # detected)
      priority: 10               # optional, default 0 — higher checked first
      fallback_for_signal: true  # optional — this YAML is the fallback when
                                  # the signal is detected but no keyword rule
                                  # (for that signal) matched

``match:`` may also be a list of such blocks, for a YAML that should be
selectable under more than one signal file (e.g. a UV method served from
either a VWD or a DAD channel).
"""
from pathlib import Path
from typing import List, NamedTuple, Optional

import yaml

from .chromatogram_io import SignalFileResolver


class _MatchRule(NamedTuple):
    yaml_name: str
    signal: str
    keywords: List[str]        # already upper-cased
    priority: int
    fallback_for_signal: bool


def _load_match_rules(methods_path: Path) -> List[_MatchRule]:
    rules: List[_MatchRule] = []
    for yaml_path in sorted(methods_path.glob("*.yaml")):
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            continue

        match_cfg = cfg.get("match")
        if not match_cfg:
            continue
        blocks = match_cfg if isinstance(match_cfg, list) else [match_cfg]

        for block in blocks:
            signal = block.get("signal")
            if not signal:
                continue
            keywords = [str(k).upper() for k in (block.get("keywords") or [])]
            rules.append(_MatchRule(
                yaml_name=yaml_path.name,
                signal=signal,
                keywords=keywords,
                priority=int(block.get("priority", 0)),
                fallback_for_signal=bool(block.get("fallback_for_signal", False)),
            ))

    # Stable sort: higher priority first, ties keep glob (alphabetical) order.
    rules.sort(key=lambda r: r.priority, reverse=True)
    return rules


class MethodSelector:
    """
    Inspect data_dir to recommend the appropriate method YAML file.

    Rules are loaded from the `match:` block of every YAML in methods_dir and
    checked in priority order; the first matching rule wins.
    """

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
        parent_upper = str(data_path).upper()

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

        rules = _load_match_rules(methods_path)

        fallback_yaml: Optional[str] = None
        for rule in rules:
            if rule.signal not in detected_signals:
                continue
            if rule.fallback_for_signal and fallback_yaml is None:
                fallback_yaml = rule.yaml_name
            if not rule.keywords:
                # Signal-only rule: always matches when the signal is present,
                # unless it exists purely to declare a fallback.
                if rule.fallback_for_signal:
                    continue
                yaml_path = methods_path / rule.yaml_name
                if yaml_path.exists():
                    print(f"  => recommended method: {rule.yaml_name}")
                    return str(yaml_path)
                continue
            if any(kw in dir_upper or kw in parent_upper for kw in rule.keywords):
                yaml_path = methods_path / rule.yaml_name
                if yaml_path.exists():
                    print(f"  => recommended method: {rule.yaml_name}")
                    return str(yaml_path)
                else:
                    print(f"  [WARN] rule matched but YAML missing: {rule.yaml_name}")

        # Fallback: the YAML(s) marked fallback_for_signal for a detected signal.
        if fallback_yaml is not None:
            yaml_path = methods_path / fallback_yaml
            if yaml_path.exists():
                print(f"  => fallback method: {fallback_yaml}")
                return str(yaml_path)

        print("  [SKIP] no suitable method found.")
        return None
