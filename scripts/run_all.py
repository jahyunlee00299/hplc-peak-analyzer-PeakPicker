"""
전체 Chem32 데이터셋 일괄 정량 처리
- MethodSelector로 자동 메소드 선택
- 각 실험 폴더별 output 생성
"""
from pathlib import Path
import sys

# PeakPicker 루트를 sys.path에 추가 (어디서든 실행 가능하도록)
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.lc_quant_agent import LCQuantAgent, MethodSelector

METHODS_DIR = _ROOT / "methods"
OUTPUT_BASE = _ROOT / "analyses" / "batch_output"

# ── 처리할 데이터셋 목록 ───────────────────────────────────────────────────
# (data_dir, experiment_id)
DATASETS = [
    # A. HPX-87H + RID — Xul-5P 생산 실험
    (
        r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260324_Xul5P_Test",
        "260324_Xul5P",
    ),
    (
        r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260317_Xul5P_AcP_Pre",
        "260317_Xul5P_AcP",
    ),
    # B. HPX-87H + RID — DeoxyNucleoside (5-FU from Glycolaldehyde)
    # (r"C:\Chem32\1\DATA\1. DeoxyNucleoside HPLC raw data\HPX-87H\<폴더명>", "241022_FU_Main"),
    # C. C18 + UV (vwd1A.ch) — 뉴클레오시드/타이드
    # (r"C:\Chem32\1\DATA\1. DeoxyNucleoside HPLC raw data\C18\<폴더명>", "C18_UV_Run1"),
    # D. HPX-87H + RID — L-Ribose 계열
    # (r"C:\Chem32\1\DATA\6. L-Rib\<폴더명>", "LRib_Run1"),
]

# ── 일괄 처리 ──────────────────────────────────────────────────────────────

def main():
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*65}")
    print(f"  PeakPicker — 전체 데이터셋 일괄 처리")
    print(f"  methods  : {METHODS_DIR}")
    print(f"  output   : {OUTPUT_BASE}")
    print(f"  데이터셋 수: {len(DATASETS)}")
    print(f"{'='*65}\n")

    skipped = []
    processed = []

    for data_dir, exp_id in DATASETS:
        data_path = Path(data_dir)
        print(f"\n[{exp_id}] {data_path.name}")

        if not data_path.exists():
            print(f"  [SKIP] 경로 없음: {data_dir}")
            skipped.append((exp_id, "경로 없음"))
            continue

        method_yaml = MethodSelector.suggest(str(data_path), str(METHODS_DIR))

        if method_yaml is None:
            print(f"  [SKIP] 적합한 메소드 없음.")
            skipped.append((exp_id, "메소드 미매칭"))
            continue

        try:
            agent = LCQuantAgent(method_yaml)
            out_dir = str(OUTPUT_BASE / exp_id)
            df = agent.run(
                data_dir=str(data_path),
                output_dir=out_dir,
                experiment_id=exp_id,
                plot=True,
            )
            processed.append((exp_id, method_yaml, len(df)))
        except Exception as e:
            print(f"  [ERROR] {exp_id}: {e}")
            skipped.append((exp_id, str(e)))

    # ── 최종 요약 ──────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  처리 완료: {len(processed)}개 | 스킵: {len(skipped)}개")
    if processed:
        print("\n  [처리됨]")
        for exp_id, yaml_path, n in processed:
            yaml_name = Path(yaml_path).name
            print(f"    {exp_id:30s}  method={yaml_name}  rows={n}")
    if skipped:
        print("\n  [스킵됨]")
        for exp_id, reason in skipped:
            print(f"    {exp_id:30s}  이유: {reason}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
