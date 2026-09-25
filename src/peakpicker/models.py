"""
models.py — Core dataclasses for LC quantification.

SRP: Pure data containers only — no logic.
"""
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Tuple


@dataclass(frozen=True)
class CompoundMethod:
    name: str
    rt_expected: float
    rt_window: Tuple[float, float]
    slope: Optional[float]   # mM / (nRIU*s)
    intercept: float
    color: str

    # Calibration provenance. The method YAMLs already carry `source:` and `r2:`
    # under each compound's `calibration:` block, but the loader used to drop both
    # on the floor, so qc.min_r2_calibration could never be evaluated and a
    # calibration constant of unknown origin was indistinguishable from a
    # traceable one. Keep them Optional: absent means "not recorded", which is a
    # finding, not a default to paper over.
    r2: Optional[float] = None
    source: Optional[str] = None


@dataclass
class QuantResult:
    sample_id: str
    compound: str
    rt_detected: Optional[float]
    area: Optional[float]         # nRIU*s
    conc_mM: Optional[float]
    qc_flag: str = ""             # "" | "NO_PEAK" | "LOW_AREA" | "NE_WARN"


@dataclass
class SampleMeta:
    """Generic per-sample metadata.

    Public/generic fields only. Experiment-specific factors (per-compound
    doses, feed rates, and similar per-experiment fields that used to be
    declared directly on this class) are no longer part of the public
    schema; they are carried in ``factors`` instead, populated by private
    plugin parsers.

    Backward compatibility: reading or writing an attribute name that is not
    one of the declared dataclass fields transparently routes through
    ``factors`` (e.g. private scripts doing ``meta.atp_mM`` or
    ``s.acp_mM = 5`` keep working unchanged).
    """
    sample_id: str
    folder: Path
    time_h: Optional[float] = None
    condition: str = "unknown"
    is_ne: bool = False  # negative / no-enzyme control
    correct_sample_name: Optional[str] = None  # resolved name after folder-shift correction
    factors: Dict[str, Any] = field(default_factory=dict)

    # Defaults for plugin-declared factors, so a factor a parser did not set
    # reads as its declared default (the old dataclass behaviour) instead of
    # raising AttributeError. Shared by all instances; plugins register them.
    _factor_defaults: ClassVar[Dict[str, Any]] = {}

    @classmethod
    def register_factor_defaults(cls, **defaults: Any) -> None:
        """Declare experiment factors and their default values (plugin API)."""
        cls._factor_defaults.update(defaults)

    def all_factors(self) -> Dict[str, Any]:
        """Declared defaults overlaid with this sample's factors."""
        return {**self._factor_defaults, **self.factors}

    def __getattr__(self, name: str) -> Any:
        # __getattr__ only fires when normal attribute lookup (instance
        # __dict__, class, dataclass fields) has already failed.
        try:
            factors = object.__getattribute__(self, "factors")
        except AttributeError:
            raise AttributeError(name)
        if name in factors:
            return factors[name]
        defaults = type(self)._factor_defaults
        if name in defaults:
            return defaults[name]
        else:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}"
            )

    def __setattr__(self, name: str, value: Any) -> None:
        field_names = {f.name for f in fields(self)}
        if name in field_names or name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        # Unknown attribute (e.g. legacy meta.acp_mM = 5) -> factors dict.
        factors = self.__dict__.get("factors")
        if factors is None:
            object.__setattr__(self, "factors", {})
            factors = self.__dict__["factors"]
        factors[name] = value
