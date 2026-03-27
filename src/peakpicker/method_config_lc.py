"""
method_config_lc.py — Typed YAML method configuration for LC quantification.

ISP: Config split into SmoothingConfig, PeakDetectionConfig, QcConfig.
SRP: Parsing and exposing YAML config only — no quantification logic.

Note: Named method_config_lc.py to avoid collision with existing quant/method_config.py.
"""
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from .models import CompoundMethod


@dataclass(frozen=True)
class SmoothingConfig:
    window: int = 11
    poly: int = 3


@dataclass(frozen=True)
class PeakDetectionConfig:
    min_prominence_factor: float = 3.0
    min_height_fraction: float = 0.01
    distance_pts: int = 10
    trim_rt_start: Optional[float] = None
    trim_rt_end: Optional[float] = None


@dataclass(frozen=True)
class QcConfig:
    ne_control_keyword: str = "_NE_"
    max_product_area_ne: float = 5000.0
    min_r2_calibration: float = 0.99


class MethodConfig:
    """YAML → typed config. Read-only after construction."""

    def __init__(self, yaml_path: str):
        with open(yaml_path, "r", encoding="utf-8") as f:
            self._cfg = yaml.safe_load(f)
        self._yaml_path = yaml_path

    @property
    def signal_file(self) -> str:
        return self._cfg.get("signal_file", "RID1A.ch")

    @property
    def baseline_method(self) -> str:
        return self._cfg.get("baseline", {}).get("method", "valley_dropline")

    @property
    def smoothing(self) -> SmoothingConfig:
        bl = self._cfg.get("baseline", {})
        return SmoothingConfig(
            window=bl.get("smoothing_window", 11),
            poly=bl.get("smoothing_poly", 3),
        )

    @property
    def peak_detection(self) -> PeakDetectionConfig:
        pd_cfg = self._cfg.get("peak_detection", {})
        return PeakDetectionConfig(
            min_prominence_factor=pd_cfg.get("min_prominence_factor", 3.0),
            min_height_fraction=pd_cfg.get("min_height_fraction", 0.01),
            distance_pts=pd_cfg.get("distance_pts", 10),
            trim_rt_start=pd_cfg.get("trim_rt_start", None),
            trim_rt_end=pd_cfg.get("trim_rt_end", None),
        )

    @property
    def qc(self) -> QcConfig:
        qc = self._cfg.get("qc", {})
        return QcConfig(
            ne_control_keyword=qc.get("ne_control_keyword", "_NE_"),
            max_product_area_ne=qc.get("max_product_area_ne", 5000.0),
            min_r2_calibration=qc.get("min_r2_calibration", 0.99),
        )

    def compounds(self) -> List[CompoundMethod]:
        result = []
        for name, d in self._cfg.get("compounds", {}).items():
            cal = d.get("calibration", {})
            result.append(CompoundMethod(
                name=name,
                rt_expected=d["rt_expected"],
                rt_window=tuple(d["rt_window"]),
                slope=cal.get("slope"),
                intercept=cal.get("intercept", 0.0),
                color=d.get("color", "#333333"),
            ))
        return result
