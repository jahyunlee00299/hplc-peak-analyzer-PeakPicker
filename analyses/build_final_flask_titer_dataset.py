"""
260810 Flask Titer — final consolidated dataset (SP0810 + HPX87H)
====================================================================
Merges original triplicate (0/12/24/72H, low CV) with re-measured
triplicate (_RE, 36/48/60H — original triplicate was unstable, CV 20-52%,
user re-ran these timepoints and CV dropped to 0.3-5%). No _RE exists for
0/12/24/72H, so those stay on the original run.

_F samples (Formate-spiked titration condition) are a separate experimental
condition, not a replicate of the unspiked run — excluded from this
no-Formate-spike timecourse.

Sources:
  SP0810 original : E:\\t\\260701_JW 2026-08-10 18-02-04\\quantification_results\\quant_by_replicate.csv
  SP0810 RE        : E:\\t\\260701_JW 2026-08-12 17-10-44\\quantification_results\\quant_by_replicate.csv
  HPX87H original  : E:\\t\\2026-08-12 240528_PAUSED_HPX87H 17-03-25\\quantification_results\\quant_by_replicate.csv
  HPX87H RE        : E:\\t\\2026-08-13 240528_PAUSED_HPX87H 18-29-16\\quantification_results\\quant_by_replicate.csv

Output: PeakPicker/analyses/result/260810_flask_titer_final/
  final_quant_by_replicate_sp0810.csv
  final_quant_by_replicate_hpx87h.csv
  final_summary_by_timepoint_sp0810.csv
  final_summary_by_timepoint_hpx87h.csv
"""
import sys
import io

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "result" / "260810_flask_titer_final"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RE_TIMEPOINTS = {36, 48, 60}

#: 🔴 The drive letter changed E: -> F: on 260831. Every path here still said E:,
#: so this merge could not see the 260831 formate re-quantification and the
#: shipped CSV kept the superseded values (t=0 formate 119.86 mM instead of
#: 181.54). Resolve the drive at run time instead of hard-coding it.
def _run(*parts: str) -> Path:
    tail = Path(*parts)
    for drive in ("F:", "E:"):
        p = Path(drive + "\\t") / tail
        if p.exists():
            return p
    return Path("F:\\t") / tail          # report the expected path when missing


DATASETS = [
    {
        "label": "sp0810",
        "compounds": ["Gal", "Tag", "Galol"],
        "original": _run("260701_JW 2026-08-10 18-02-04",
                         "quantification_results", "quant_by_replicate.csv"),
        "re": _run("260701_JW 2026-08-12 17-10-44",
                   "quantification_results", "quant_by_replicate.csv"),
    },
    {
        "label": "hpx87h",
        "compounds": ["Gal_Tag", "Galol", "Formate"],
        "original": _run("2026-08-12 240528_PAUSED_HPX87H 17-03-25",
                         "quantification_results", "quant_by_replicate.csv"),
        "re": _run("2026-08-13 240528_PAUSED_HPX87H 18-29-16",
                   "quantification_results", "quant_by_replicate.csv"),
    },
]


def build(ds):
    orig = pd.read_csv(ds["original"])
    orig["source"] = "original"
    if "variant" not in orig.columns:
        orig["variant"] = "plain"

    re_df = pd.read_csv(ds["re"])
    re_df = re_df[re_df["variant"] == "RE"].copy()
    re_df["source"] = "RE"

    # keep original rows only for timepoints NOT covered by RE
    orig_keep = orig[~orig["time_h"].isin(RE_TIMEPOINTS)]
    combined = pd.concat([orig_keep, re_df], ignore_index=True)
    combined = combined.sort_values(["time_h", "replicate"]).reset_index(drop=True)

    keep_cols = ["sample", "time_h", "replicate", "source"]
    for c in ds["compounds"]:
        keep_cols += [f"{c}_rt_min", f"{c}_area", f"{c}_mM"]
    combined = combined[[c for c in keep_cols if c in combined.columns]]

    summary_cols = [f"{c}_mM" for c in ds["compounds"]]
    summary = (
        combined.groupby("time_h")[summary_cols]
        .agg(["mean", "std", "count"])
        .reset_index()
        .sort_values("time_h")
    )
    summary.columns = ["time_h"] + [f"{m}_{s}" for m, s in summary.columns.tolist()[1:]]
    summary["CV%_" + ds["compounds"][0]] = (
        summary[f"{ds['compounds'][0]}_mM_std"] / summary[f"{ds['compounds'][0]}_mM_mean"] * 100
    ).round(1)

    combined_path = OUT_DIR / f"final_quant_by_replicate_{ds['label']}.csv"
    summary_path = OUT_DIR / f"final_summary_by_timepoint_{ds['label']}.csv"
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print(f"=== {ds['label']} ===")
    print(f"  timepoints from original: {sorted(orig_keep['time_h'].unique())}")
    print(f"  timepoints from RE:       {sorted(re_df['time_h'].unique())}")
    print(summary.round(2).to_string(index=False))
    print(f"  saved: {combined_path.name}, {summary_path.name}\n")
    return combined, summary


def main():
    for ds in DATASETS:
        build(ds)
    print(f"Output dir: {OUT_DIR}")


if __name__ == "__main__":
    main()
