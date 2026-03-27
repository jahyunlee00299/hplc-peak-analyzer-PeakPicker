"""
models.py — Core dataclasses for LC quantification.

SRP: Pure data containers only — no logic.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class CompoundMethod:
    name: str
    rt_expected: float
    rt_window: Tuple[float, float]
    slope: Optional[float]   # mM / (nRIU*s)
    intercept: float
    color: str


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
    sample_id: str
    folder: Path
    xyla: Optional[int] = None
    xylb: Optional[int] = None
    xyl_mM: Optional[float] = None
    acp_mM: Optional[float] = None
    atp_mM: Optional[float] = None
    time_h: Optional[float] = None
    condition: str = "unknown"
    is_ne: bool = False
    is_fed: bool = False
