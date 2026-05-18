"""PreToolUse hook — 워커 → 워커 chain 금지 enforcement.

ADR-0001 §6 + ADR-0002 §6 + ADR-0004 §8 — 워커가 다른 워커를 호출하면 sub-leader
가 출현해 결재 라인이 무너진다. ADR-0004 §1 이 정의한 "메인 세션 = CPO 단독 라우터"
원칙을 코드 레벨에서 강제한다.

동작:
    - tool_name 이 "Task" 가 아니면 무조건 allow.
    - tool_name 이 "Task" 일 때:
        - 활성 워커 세션이 없으면 → allow (메인 세션 = CPO 가 dispatch 중).
        - 활성 워커 세션이 있으면 → **deny** (워커가 sub-Task 호출 시도).
    - escape hatch: ``LSKUN_ALLOW_WORKER_CHAIN=1`` 환경변수 설정 시 무조건 allow
      (디버깅 / 향후 ADR 변경 시 우회용).

입력 (stdin):
    Claude Code 가 PreToolUse hook payload 를 JSON 으로 주입:
    ``{"tool_name": "Task", "tool_input": {...}}``

출력 (stdout):
    Claude Code PreToolUse hook 사양:
    ``{"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                "permissionDecision": "allow|deny",
                                "permissionDecisionReason": "..."}}``

종료 코드: 항상 0 — hook 실패는 세션을 막지 않는다 (decision 만 'allow' 로 fallback).

활성 워커 감지: ``LSKUN_SSOT_ROOT`` 환경변수 → session.read.
``LSKUN_SSOT_ROOT`` 가 비어있으면 plugin 비활성 환경으로 보고 allow.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TOOL_TASK = "Task"
ENV_SSOT_ROOT = "LSKUN_SSOT_ROOT"
ENV_ALLOW_CHAIN = "LSKUN_ALLOW_WORKER_CHAIN"


def main(argv: list[str] | None = None) -> int:
    try:
        decision, reason = _decide(sys.stdin.read())
    except Exception as e:  # noqa: BLE001 — hook 은 세션을 막지 않는다.
        print(f"lskun-kit pre_tool_use: error {e!r}", file=sys.stderr)
        decision, reason = "allow", "hook error — fallback to allow"

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


def _decide(stdin_text: str) -> tuple[str, str]:
    """payload 와 환경을 보고 (decision, reason) 반환.

    decision ∈ {"allow", "deny"}.
    """

    tool_name = _extract_tool_name(stdin_text)
    if tool_name != TOOL_TASK:
        return "allow", ""

    if os.environ.get(ENV_ALLOW_CHAIN, "").strip() == "1":
        return "allow", "LSKUN_ALLOW_WORKER_CHAIN=1 — chain enforcement bypass"

    root = os.environ.get(ENV_SSOT_ROOT, "").strip()
    if not root:
        # plugin 비활성 환경 — chain 검사 skip.
        return "allow", ""

    from lskun_kit import session  # 지연 import — hooks 의존성 격리

    sess = session.read(Path(root))
    if sess is None:
        # 메인 세션 = CPO 가 Task 로 워커 dispatch 하는 정상 경로.
        return "allow", ""

    # 워커 세션 도중 Task tool 호출 시도 — sub-leader 출현 차단.
    return (
        "deny",
        (
            f"LSKunCompanyKit: 워커 '{sess.active_worker}' 세션 중 Task tool 호출 차단 "
            f"(ADR-0004 §8 — 워커 → 워커 chain 금지). 결재 / 추가 dispatch 가 필요하면 "
            f"세션을 종료하고 메인 세션 = CPO 에게 요청하라. 디버깅 시 "
            f"LSKUN_ALLOW_WORKER_CHAIN=1 로 bypass 가능."
        ),
    )


def _extract_tool_name(stdin_text: str) -> str:
    """payload 에서 tool_name 만 안전하게 꺼낸다. 실패 시 빈 문자열."""

    if not stdin_text.strip():
        return ""
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    name = data.get("tool_name")
    return name if isinstance(name, str) else ""


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
