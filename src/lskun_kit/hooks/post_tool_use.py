"""PostToolUse:Task reminder hook — P76 박제 (ADR-0014 후보).

CPO 가 Task tool 호출 후 reflection 박제 §4/§5 를 skip 하는 P0~P71 dead code 화
패턴이 P75 까지 반복 실측됐다. ADR-0013 §"폐기/금지" 가 *자동 박제* hook 을 금지
했지만, 본 hook 은 **자동 박제가 아닌 reminder injection** 이다 — `reflection.record_*()`
를 호출하지 않고 CPO 의 context 에 `[REFLECTION 박제 필수]` 알림 1줄만 주입한다.

CPO 가 알림을 보고 본인이 결재 절차 §4 (record_from_report) + §6 (audit.record) 를
직접 호출해야 한다. 박제 자체는 여전히 CPO 의 책임 (LLM judgement 보존).

ADR-0013 vs 본 hook:
    - ADR-0013 금지: hook 이 `reflection.record()` 를 자동 호출 — silent failure 누적 위험
    - 본 hook 허용: stdout 으로 nudge 1줄만, 박제 행위는 CPO 가 수행

비활성화: `LSKUN_SKIP_REFLECTION_REMINDER=1` 환경변수 설정 시 무음 처리.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if os.environ.get("LSKUN_SKIP_REFLECTION_REMINDER", "").strip() == "1":
        return 0

    # PostToolUse hook 은 stdin 으로 tool_name + tool_input + tool_response 를 받는다.
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # parse 실패 시 silent — hook 이 사용자 작업을 차단해선 안 됨
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name != "Task":
        return 0

    tool_input = payload.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type", "general-purpose")
    description = (tool_input.get("description") or "").strip()[:60]

    # CPO 가 자기 자신 (cpo / hr-lead) 을 호출한 경우는 메타 작업이라 reminder skip.
    # subagent_type 으로는 워커 이름을 추론 못 하므로 description 으로 휴리스틱.
    reminder = (
        f"[REFLECTION 박제 필수 — P76/ADR-0014] Task dispatch 직후입니다 "
        f"(subagent={subagent_type}, desc={description!r}). "
        f"CPO 결재 절차 §4 (reflection.record_from_report) + §6 (audit.record) 를 "
        f"지금 즉시 호출하세요. 사용자에게 결과 전달 *전*에 박제 완료. "
        f"비활성화: LSKUN_SKIP_REFLECTION_REMINDER=1."
    )

    # Claude Code hook 의 stdout 은 system-reminder 로 다음 turn context 에 주입됨.
    sys.stdout.write(reminder + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
