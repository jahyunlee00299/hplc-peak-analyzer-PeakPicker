"""
Quantification Method Config
==============================

YAML-based method definition for HPLC quantification:
  - Column / instrument metadata
  - Compound RT windows
  - Standard curves (linear regression)

YAML format example
-------------------

method:
  name: HPX87H_sugars
  column: Bio-Rad Aminex HPX-87H
  temperature_c: 65
  flow_rate_ml_min: 0.5
  mobile_phase: 5 mM H2SO4
  detector: RID

compounds:
  - name: D-Glucose
    rt_min: 6.75
    rt_max: 7.05
    mw: 180.16
    unit: mM

  - name: D-Xylose
    rt_min: 7.05
    rt_max: 7.50
    mw: 150.13
    unit: mM

  - name: Xylitol
    rt_min: 9.10
    rt_max: 9.80
    mw: 152.15
    unit: mM

  - name: Xylulose-5P
    rt_min: 10.80
    rt_max: 11.50
    mw: 232.12
    unit: mM

  - name: IS
    rt_min: 17.00
    rt_max: 17.70
    note: internal standard

standard_curves:
  D-Glucose:
    concentrations: [0.1, 0.5, 1.0, 2.0, 5.0]   # mM
    areas:          [8000, 40000, 80000, 160000, 400000]
    unit: mM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompoundDef:
    """Defines one compound: name + expected RT window."""
    name: str
    rt_min: float
    rt_max: float
    mw: Optional[float] = None          # g/mol
    unit: str = "mM"
    note: str = ""
    area_mode: str = "full"             # "full" | "left_half" | "right_half"

    def contains(self, rt: float) -> bool:
        return self.rt_min <= rt <= self.rt_max


@dataclass
class StandardCurve:
    """
    Linear calibration curve: area = slope * concentration + intercept.

    Fit is performed by fit() which must be called before predict().
    """
    compound_name: str
    concentrations: List[float]         # e.g. mM
    areas: List[float]
    unit: str = "mM"

    # Fitted parameters (populated by fit())
    slope: float = field(default=0.0, init=False)
    intercept: float = field(default=0.0, init=False)
    r2: float = field(default=0.0, init=False)
    _fitted: bool = field(default=False, init=False, repr=False)

    def fit(self) -> None:
        """Perform linear regression (area ~ concentration)."""
        self._fitted = True  # mark as attempted even if data insufficient
        x = np.array(self.concentrations, dtype=float)
        y = np.array(self.areas, dtype=float)
        if len(x) < 2:
            logger.warning("StandardCurve '%s': need ≥2 points for fit — fill in standard_curves in YAML", self.compound_name)
            return
        coeffs = np.polyfit(x, y, 1)
        self.slope = float(coeffs[0])
        self.intercept = float(coeffs[1])
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        self.r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        self._fitted = True
        logger.debug(
            "StandardCurve '%s': slope=%.2f intercept=%.2f R²=%.4f",
            self.compound_name, self.slope, self.intercept, self.r2
        )

    def predict(self, area: float) -> Optional[float]:
        """Convert peak area → concentration. Returns None if not fitted or slope~0."""
        if not self._fitted:
            self.fit()
        if abs(self.slope) < 1e-12:
            return None
        conc = (area - self.intercept) / self.slope
        return float(conc)

    def is_fitted(self) -> bool:
        return self._fitted


@dataclass
class MethodInfo:
    """Instrument / column metadata (informational only)."""
    name: str = ""
    column: str = ""
    temperature_c: Optional[float] = None
    flow_rate_ml_min: Optional[float] = None
    mobile_phase: str = ""
    detector: str = "RID"


@dataclass
class QuantMethod:
    """
    Complete quantification method: column info + compound definitions + standard curves.

    Usage
    -----
    Load from YAML::

        method = QuantMethod.from_yaml("hpx87h_sugars.yaml")

    Create programmatically::

        method = QuantMethod(
            info=MethodInfo(name="HPX87H", column="Bio-Rad HPX-87H"),
            compounds=[
                CompoundDef("D-Glucose",    6.75, 7.05),
                CompoundDef("D-Xylose",     7.05, 7.50),
                CompoundDef("Xylulose-5P", 10.80, 11.50),
            ],
        )
    """
    info: MethodInfo = field(default_factory=MethodInfo)
    compounds: List[CompoundDef] = field(default_factory=list)
    standard_curves: Dict[str, StandardCurve] = field(default_factory=dict)

    # ── YAML I/O ─────────────────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: str | Path) -> "QuantMethod":
        """Load method from YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required: pip install pyyaml")

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        # Method info
        info_raw = raw.get("method", {})
        info = MethodInfo(
            name=info_raw.get("name", ""),
            column=info_raw.get("column", ""),
            temperature_c=info_raw.get("temperature_c"),
            flow_rate_ml_min=info_raw.get("flow_rate_ml_min"),
            mobile_phase=info_raw.get("mobile_phase", ""),
            detector=info_raw.get("detector", "RID"),
        )

        # Compounds
        compounds = []
        for c in raw.get("compounds", []):
            compounds.append(CompoundDef(
                name=c["name"],
                rt_min=float(c["rt_min"]),
                rt_max=float(c["rt_max"]),
                mw=c.get("mw"),
                unit=c.get("unit", "mM"),
                note=c.get("note", ""),
                area_mode=c.get("area_mode", "full"),
            ))

        # Standard curves
        std_curves = {}
        for cname, sc_raw in raw.get("standard_curves", {}).items():
            sc = StandardCurve(
                compound_name=cname,
                concentrations=list(sc_raw.get("concentrations", [])),
                areas=list(sc_raw.get("areas", [])),
                unit=sc_raw.get("unit", "mM"),
            )
            # Support pre-fitted slope/intercept directly in YAML
            if "slope" in sc_raw and "intercept" in sc_raw:
                sc.slope = float(sc_raw["slope"])
                sc.intercept = float(sc_raw["intercept"])
                sc.r2 = float(sc_raw.get("r2", 1.0))
                sc._fitted = True
                logger.debug(
                    "StandardCurve '%s': pre-fitted slope=%.2f intercept=%.2f",
                    cname, sc.slope, sc.intercept,
                )
            else:
                sc.fit()
            std_curves[cname] = sc

        return cls(info=info, compounds=compounds, standard_curves=std_curves)

    def to_yaml(self, path: str | Path) -> None:
        """Save method to YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required: pip install pyyaml")

        data: dict = {}
        if self.info.name or self.info.column:
            data["method"] = {
                k: v for k, v in {
                    "name": self.info.name,
                    "column": self.info.column,
                    "temperature_c": self.info.temperature_c,
                    "flow_rate_ml_min": self.info.flow_rate_ml_min,
                    "mobile_phase": self.info.mobile_phase,
                    "detector": self.info.detector,
                }.items() if v is not None and v != ""
            }

        if self.compounds:
            data["compounds"] = []
            for c in self.compounds:
                entry: dict = {"name": c.name, "rt_min": c.rt_min, "rt_max": c.rt_max}
                if c.mw is not None:
                    entry["mw"] = c.mw
                if c.unit != "mM":
                    entry["unit"] = c.unit
                if c.note:
                    entry["note"] = c.note
                data["compounds"].append(entry)

        if self.standard_curves:
            data["standard_curves"] = {}
            for name, sc in self.standard_curves.items():
                data["standard_curves"][name] = {
                    "concentrations": sc.concentrations,
                    "areas": sc.areas,
                    "unit": sc.unit,
                }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        logger.info("QuantMethod saved to %s", path)

    # ── Lookups ───────────────────────────────────────────────────────────────

    def find_compound(self, rt: float) -> Optional[CompoundDef]:
        """Return the first compound whose RT window contains `rt`."""
        for c in self.compounds:
            if c.contains(rt):
                return c
        return None

    def get_standard_curve(self, compound_name: str) -> Optional[StandardCurve]:
        return self.standard_curves.get(compound_name)
