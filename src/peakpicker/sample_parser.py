"""
sample_parser.py — Sample metadata parsing from folder names.

OCP: SampleParser Protocol defines the interface.
     New experiment formats register a parser via ``register_parser`` from a
     plugin — the public module (this file) never hard-codes an experiment's
     naming convention.
LSP: every registered parser is fully interchangeable with GenericSampleParser.
"""
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional, Protocol, runtime_checkable

from .models import SampleMeta
from .plugins import load_plugins


@runtime_checkable
class SampleParser(Protocol):
    """OCP: implement this Protocol to support new experiment naming schemes."""

    def parse(self, folder: Path) -> SampleMeta:
        """Parse a .D folder into SampleMeta."""
        ...

    def post_classify(self, samples: List[SampleMeta]) -> List[SampleMeta]:
        """Post-process the full sample list to refine conditions."""
        ...


class GenericSampleParser:
    """
    Fallback parser: extracts date_description from folder name only.
    Assigns condition = "unknown" and leaves all numeric fields as None.
    """

    def parse(self, folder: Path) -> SampleMeta:
        return SampleMeta(sample_id=folder.stem, folder=folder)

    def post_classify(self, samples: List[SampleMeta]) -> List[SampleMeta]:
        return samples


class _RegisteredParser(NamedTuple):
    name: str
    detect: Callable[[List[Path]], bool]
    factory: Callable[[], "SampleParser"]
    priority: int


_REGISTRY: List[_RegisteredParser] = []


def register_parser(
    name: str,
    detect: Callable[[List[Path]], bool],
    factory: Callable[[], "SampleParser"],
    priority: int = 0,
) -> None:
    """Register an experiment-specific SampleParser.

    Parameters
    ----------
    name:     identifier, used only for diagnostics/repr.
    detect:   callable(d_folder_paths) -> bool. Given the .D folders found in
              a data directory (or a subset of them), return True if this
              parser should handle that directory.
    factory:  callable() -> SampleParser instance.
    priority: higher runs first. Ties broken by registration order.
    """
    _REGISTRY.append(_RegisteredParser(name=name, detect=detect, factory=factory, priority=priority))


def _clear_registry_for_testing() -> None:
    """Test-only hook to reset registry state between tests."""
    _REGISTRY.clear()


def _collect_d_folders(data_dir: str) -> List[Path]:
    data_path = Path(data_dir)
    d_folders = list(data_path.glob("*.D"))
    if not d_folders:
        for sub in data_path.iterdir():
            if sub.is_dir() and not sub.name.endswith(".D"):
                d_folders.extend(sub.glob("*.D"))
    return d_folders


def get_parser(data_dir: str) -> SampleParser:
    """
    Factory: inspect folder names in *data_dir* and return the most
    appropriate SampleParser.

    Loads plugins first (lazily, idempotent), then tries every registered
    parser in descending priority order, falling back to GenericSampleParser
    if none of them detect a match.
    """
    load_plugins()

    d_folders = _collect_d_folders(data_dir)
    candidates = sorted(_REGISTRY, key=lambda r: r.priority, reverse=True)
    for reg in candidates:
        try:
            if reg.detect(d_folders[:20]):
                return reg.factory()
        except Exception:
            continue

    return GenericSampleParser()
