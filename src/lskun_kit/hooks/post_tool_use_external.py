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

NOTE: ``_detect_company_root`` 는 ``pre_tool_use.py`` 와 동일 로직 복제.
P121 Task 3 (Stop hook) 도 같은 함수를 쓰므로 본 task 에서는 복제하고
Task 3 에서 ``hooks/_common.py`` 로 추출 결정.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 직접 경로 호출 시 self-bootstrap (P48 hook command 형태 대응).
_SRC_DIR = str(Path(__file__).resolve().parents[2])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

TOOL_TASK = "Task"
ENV_SSOT_ROOT = "LSKUN_SSOT_ROOT"
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

    # 3. 활성 회사 root 검출.
    company_root = _detect_company_root()
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

    # 7. system-reminder 주입 (enum 라벨만 노출 — security C1).
    sys.stdout.write(_format_reminder(new_state))
    sys.stdout.write("\n")


def _format_reminder(state: object) -> str:
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


def _detect_company_root() -> Path | None:
    """활성 회사 root 검출 (pre_tool_use.py 와 동일 로직, P121 Task 3 에서 _common 추출).

    1순위: ``LSKUN_SSOT_ROOT`` env var (O(1)).
    2순위: cwd 상위 CLAUDE.md marker 직접 검출 (session_start 재사용).
    """

    env_root = os.environ.get(ENV_SSOT_ROOT, "").strip()
    if env_root:
        path = Path(env_root)
        return path if path.exists() else None

    try:
        from lskun_kit.hooks.session_start import _find_active_company_root  # type: ignore[attr-defined]
    except ImportError:
        return None
    return _find_active_company_root()


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
