"""PostToolUse:Task hook — 외주 setup 다음 step push (ADR-0022, P121 Task 2).

CPO 가 ``/lskun-kit:external`` 명령으로 외주 setup 시퀀스를 진행하는 동안,
Task tool 실행이 끝날 때마다 본 hook 가 marker 를 읽어 "다음 판단 step" 을
``<system-reminder>`` 로 stdout 주입하여 CPO 가 같은 turn 안에서 시퀀스를
이어가도록 push 한다.

평가 순서 (spec §5.1):
    1. ``tool_name != "Task"`` → exit 0 (출력 없음)
    2. ``LSKUN_ALLOW_EXTERNAL_HALT=1`` → exit 0 + stderr 경고 (사용자 escape)
    3. 활성 회사 root 검출 실패 → exit 0
    4. marker 부재 → exit 0
    5. malformed / stale / exhausted → ``read()`` 가 auto-unlink 후 ``None``
       → exit 0
    6. ``advance()`` 호출로 ``step_count_so_far += 1`` (current_step /
       next_action 은 동일 유지 — push 는 시점 동기화이지 step 전진이
       아니라서 CPO 가 명시 호출하지 않은 한 step 라벨 자체는 안 바꾼다.
       다만 P121 Task 2 범위는 spec 의 명세대로 ``advance()`` 를 호출하여
       step 폭주 가드와 일관성 유지)
    7. ``<system-reminder>`` 주입 + exit 0

본 hook 는 **세션을 절대 막지 않는다**. 예외 발생 시 stderr 1줄 + exit 0.
stdout 에는 예외 시 어떤 출력도 박지 않는다 (LLM context 오염 방지).

Security (spec C1):
    marker 에 박힌 ``current_step`` / ``next_action`` 은 ``external_setup_state``
    의 ``STEP_ENUM`` allowlist 를 통과한 값만 LLM context 에 노출된다. raw
    문자열 박제 시도는 ``read()`` 단계에서 차단되어 ``None`` 반환.

NOTE: 활성 회사 root 검출은 ``hooks/_common.detect_company_root`` 로 추출
(P121 Task 3) — ``stop_external`` 과 공유.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lskun_kit.external_setup_state import ExternalSetupState

# 직접 경로 호출 시 self-bootstrap (P48 hook command 형태 대응).
_SRC_DIR = str(Path(__file__).resolve().parents[2])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

TOOL_TASK = "Task"
ENV_ALLOW_HALT = "LSKUN_ALLOW_EXTERNAL_HALT"


def main(argv: list[str] | None = None) -> int:
    stdin_text = sys.stdin.read()

    try:
        _run(stdin_text)
    except Exception as e:  # noqa: BLE001 — hook 은 세션을 막지 않는다.
        # stdout 은 절대 건드리지 않는다 (LLM context 오염 방지).
        print(
            f"lskun-kit post_tool_use_external: error {e!r}",
            file=sys.stderr,
        )
    return 0


def _run(stdin_text: str) -> None:
    """본체 — 예외는 caller(main)가 잡아 stderr 만 출력."""

    data = _parse_payload(stdin_text)
    tool_name = data.get("tool_name") if isinstance(data, dict) else ""

    # 1. Task tool 외는 무조건 종료.
    if tool_name != TOOL_TASK:
        return

    # 2. escape hatch — 사용자가 명시적으로 push 차단 요청.
    if os.environ.get(ENV_ALLOW_HALT, "").strip() == "1":
        print(
            "lskun-kit: WARNING — LSKUN_ALLOW_EXTERNAL_HALT=1 활성. "
            "외주 setup 다음 step push 가 우회되고 있다 (ADR-0022). "
            "세션 단위로만 사용하라.",
            file=sys.stderr,
        )
        return

    # 3. 활성 회사 root 검출 (hooks/_common 공유 헬퍼).
    from lskun_kit.hooks._common import detect_company_root

    company_root = detect_company_root()
    if company_root is None:
        return

    company_name = company_root.name

    # 4/5. marker 읽기. 부재 / malformed / stale / exhausted 면 None.
    from lskun_kit import external_setup_state  # 지연 import — hooks 의존성 격리

    state = external_setup_state.read(company_name)
    if state is None:
        return

    # 6. advance — step_count 폭주 가드와 일관성 유지.
    #    current_step / next_action 은 그대로 유지 (push 는 시점 동기화이지
    #    step 라벨 전진이 아님; CPO 가 step 라벨 갱신은 직접 advance() 호출).
    new_state = external_setup_state.advance(
        company_name,
        state.current_step,
        state.next_action,
    )

    # 6-b. advance 결과가 exhausted (step_count > max) 면 push 하지 않고 정리.
    #    advance 는 read→+1→write 라 max 도달 marker 가 1회 더 전진하므로, 그
    #    전진분이 exhausted 면 reminder 주입을 생략하고 read() 로 auto-unlink
    #    트리거 (spec §3.3 "max 에서 멈춤" invariant — off-by-one push 누수 차단).
    if new_state.is_exhausted():
        external_setup_state.read(company_name)  # exhausted → auto-unlink
        return

    # 7. system-reminder 주입 (enum 라벨만 노출 — security C1).
    sys.stdout.write(_format_reminder(new_state))
    sys.stdout.write("\n")


def _format_reminder(state: "ExternalSetupState") -> str:
    """``<system-reminder>`` 본문. enum 라벨 (current_step / next_action) 만 노출."""

    return (
        "<system-reminder>\n"
        f"LSKun external setup 진행 중 (project={state.project}, "
        f"step={state.current_step}).\n"
        f"다음 판단 step: {state.next_action}.\n"
        "CPO 는 같은 turn 안에 이 step 을 이어서 수행하라. "
        "사용자 응답을 기다리지 말 것.\n"
        "완료 시 external_setup_state.finalize() 로 marker 정리. ADR-0022.\n"
        "</system-reminder>"
    )


def _parse_payload(stdin_text: str) -> dict:
    """stdin payload 파싱. 실패 시 빈 dict."""

    if not stdin_text.strip():
        return {}
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
