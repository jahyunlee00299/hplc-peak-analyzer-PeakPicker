"""
HPLC 정량 서브에이전트 호출 헬퍼
================================
Claude Agent SDK를 통해 HPLC 분석 서브에이전트를 실행합니다.

사용 예:
    from run_hplc_agent import build_hplc_prompt

    prompt = build_hplc_prompt(
        data_dir=r"C:/Chem32/1/DATA/2. D-Xyl cascade HPLC/Xul 5P production/AckA Pre",
        compounds=["ADP"],
        task_name="AckA_Pre_260304",
        groups={
            "NEW": ["NEW_D1", "NEW_D2", "NEW_D3", "NEW_D4"],
            "OLD": ["OLD_D1", "OLD_D2", "OLD_D3", "OLD_D4"],
        }
    )
    # Claude Code CEO 세션에서:
    # Agent(subagent_type="general-purpose", prompt=prompt)
"""

from pathlib import Path


PROMPT_TEMPLATE = Path(__file__).parent / "hplc_quant_agent_prompt.md"


def build_hplc_prompt(
    data_dir: str,
    compounds: list[str],
    task_name: str,
    groups: dict[str, list[str]] | None = None,
) -> str:
    """
    Parameters
    ----------
    data_dir   : .D 파일이 있는 폴더 경로
    compounds  : 정량할 화합물 목록 (hpx87h_sugars.yaml 키 이름과 일치해야 함)
                 예: ["ADP", "D-Xylose"]
    task_name  : 출력 파일 prefix (예: "AckA_Pre_260304")
    groups     : {"그룹명": ["샘플명1", "샘플명2", ...], ...}
                 None이면 전체 overlay
    """
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")

    # GROUPS 포맷: "NEW:NEW_D1,NEW_D2;OLD:OLD_D1,OLD_D2"
    if groups:
        groups_str = ";".join(
            f"{gname}:{','.join(members)}"
            for gname, members in groups.items()
        )
    else:
        groups_str = ""

    prompt = (
        template
        .replace("{{DATA_DIR}}", data_dir)
        .replace("{{COMPOUNDS}}", ",".join(compounds))
        .replace("{{GROUPS}}", groups_str)
        .replace("{{TASK_NAME}}", task_name)
    )
    return prompt


if __name__ == "__main__":
    # 테스트 출력
    prompt = build_hplc_prompt(
        data_dir=r"C:/Chem32/1/DATA/2. D-Xyl cascade HPLC/Xul 5P production/AckA Pre",
        compounds=["ADP"],
        task_name="AckA_Pre_260304",
        groups={
            "NEW": ["NEW_D1", "NEW_D2", "NEW_D3", "NEW_D4"],
            "OLD": ["OLD_D1", "OLD_D2", "OLD_D3", "OLD_D4"],
        },
    )
    print(prompt[:500], "...")
