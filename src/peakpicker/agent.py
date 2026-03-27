"""
agent.py — Thin facade orchestrating the LC quantification pipeline.

DIP: LCQuantAgent depends on Protocol/Config, not concrete classes.
SRP: Orchestration only — all real work delegated to components.
"""
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .method_config_lc import MethodConfig
from .chromatogram_io import SignalFileResolver, ChromatogramParser
from .peak_quantifier import PeakQuantifier
from .qc_checker import QcChecker
from .result_writer import ExcelWriter, OverlayPlotter
from .models import QuantResult, SampleMeta
from .sample_parser import SampleParser, get_parser


class LCQuantAgent:
    """
    LC quantification agent — method understanding + automatic sample
    separation + accurate peak integration.

    DIP: accepts any SampleParser via dependency injection.
    SRP: orchestrates components; contains no algorithm details.
    """

    def __init__(
        self,
        method_yaml: str,
        parser: Optional[SampleParser] = None,
    ):
        self._config     = MethodConfig(method_yaml)
        self._compounds  = self._config.compounds()
        self._resolver   = SignalFileResolver(self._config.signal_file)
        self._loader     = ChromatogramParser()
        self._quantifier = PeakQuantifier(
            self._config.peak_detection,
            self._config.smoothing,
        )
        self._qc         = QcChecker(self._config.qc)
        self._writer     = ExcelWriter()
        self._plotter    = OverlayPlotter(
            compounds=self._compounds,
            resolver=self._resolver,
            loader=self._loader,
            quantifier=self._quantifier,
        )
        # Parser resolved lazily if data_dir not known yet
        self._parser_override = parser

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        data_dir: str,
        output_dir: str,
        experiment_id: str = "experiment",
        plot: bool = True,
    ) -> pd.DataFrame:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  LC Quant Agent - {experiment_id}")
        print(f"{'='*60}")

        samples = self._scan(data_dir)
        results = self._quantify_all(samples)
        df = self._build_dataframe(results, samples)

        self._writer.write(df, output_path, experiment_id)

        if plot:
            self._plotter.plot(samples, output_path, experiment_id)

        print(f"\n{'='*60}")
        print(f"  Done. {len(df)} result rows.")
        print(f"{'='*60}")

        return df

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_parser(self, data_dir: str) -> SampleParser:
        if self._parser_override is not None:
            return self._parser_override
        return get_parser(data_dir)

    def _scan(self, data_dir: str) -> List[SampleMeta]:
        """Discover .D folders, parse metadata, post-classify."""
        data_path = Path(data_dir)
        parser = self._get_parser(data_dir)

        folders = sorted(data_path.glob("*.D"))
        if not folders:
            for sub in sorted(data_path.iterdir()):
                if sub.is_dir() and not sub.name.endswith(".D"):
                    folders.extend(sorted(sub.glob("*.D")))

        samples = []
        for f in folders:
            ch = self._resolver.resolve(f)
            if ch.exists():
                samples.append(parser.parse(f))

        samples = parser.post_classify(samples)

        ne  = sum(1 for s in samples if s.is_ne)
        fed = sum(1 for s in samples if s.is_fed)
        rxn = len(samples) - ne - fed
        print(f"  Samples found: {len(samples)}  (rxn={rxn}, NE={ne}, fed={fed})")
        return samples

    def _quantify_all(self, samples: List[SampleMeta]) -> List[QuantResult]:
        """Run peak quantification for every sample × compound."""
        all_results: List[QuantResult] = []

        for sample in samples:
            ch_path = self._resolver.resolve(sample.folder)
            try:
                time, raw_sig = self._loader.load(ch_path)
            except Exception as e:
                print(f"  [ERROR] {sample.sample_id}: {e}")
                continue

            sig = self._quantifier.smooth(raw_sig)
            sig = self._quantifier.apply_trim(time, sig)

            print(f"\n  [{sample.condition.upper()}] {sample.sample_id}")

            for cmpd in self._compounds:
                area, rt = self._quantifier.quantify_compound(time, sig, cmpd)
                conc = (
                    self._quantifier.area_to_conc(area, cmpd)
                    if area is not None else None
                )

                result = QuantResult(
                    sample_id=sample.sample_id,
                    compound=cmpd.name,
                    rt_detected=round(rt, 3) if rt is not None else None,
                    area=round(area, 1) if area is not None else None,
                    conc_mM=round(conc, 2) if conc is not None else None,
                    qc_flag="",
                )
                result.qc_flag = self._qc.check(result, sample)
                all_results.append(result)

                area_str = f"{area:.0f}" if area is not None else "--"
                conc_str = f"{conc:.1f} mM" if conc is not None else "--"
                rt_str   = f"{rt:.3f}" if rt is not None else "--"
                flag_str = f" [{result.qc_flag}]" if result.qc_flag else ""
                print(
                    f"    {cmpd.name:15s}: RT={rt_str:6s}  "
                    f"area={area_str:10s}  {conc_str}{flag_str}"
                )

        return all_results

    def _build_dataframe(
        self,
        results: List[QuantResult],
        samples: List[SampleMeta],
    ) -> pd.DataFrame:
        """Merge quantification results with sample metadata."""
        df = pd.DataFrame([{
            "sample_id":  r.sample_id,
            "compound":   r.compound,
            "rt_min":     r.rt_detected,
            "area_nRIU_s": r.area,
            "conc_mM":    r.conc_mM,
            "qc_flag":    r.qc_flag,
        } for r in results])

        meta_df = pd.DataFrame([{
            "sample_id": s.sample_id,
            "condition": s.condition,
            "xyla":      s.xyla,
            "xylb":      s.xylb,
            "xyl_mM":    s.xyl_mM,
            "acp_mM":    s.acp_mM,
            "atp_mM":    s.atp_mM,
            "time_h":    s.time_h,
            "is_ne":     s.is_ne,
            "is_fed":    s.is_fed,
        } for s in samples])

        return df.merge(meta_df, on="sample_id", how="left")
