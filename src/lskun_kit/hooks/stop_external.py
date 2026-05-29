"""Stop hook — 외주 setup turn 종료 차단 (ADR-0022, P121 Task 3).

marker 파일 살아있고 ``stop_hook_active != true`` 인 경우에만
``decision="block"`` 을 반환하여 turn 종료를 막는다. PostToolUse hook 의
soft push (같은 turn 연속) 가 LLM 자율 종료로 깨질 때의 hard guard.

평가 순서 (spec §5.2):
    1. ``stop_hook_active=true`` → exit 0 + auto-unlink
       (무한 lockup 방지의 단일 invariant — architect MAJOR 해소)
    2. ``LSKUN_ALLOW_EXTERNAL_HALT=1`` → exit 0 + stderr warn (escape hatch)
    3. 활성 회사 root 부재 → exit 0
    4. marker 부재 / malformed / stale / exhausted → exit 0
       (``external_setup_state.read()`` 가 auto-unlink 처리)
    5. ``decision="block"`` + reason

본 hook 는 **block 외에는 세션을 절대 막지 않는다**. 예외 발생 시 stderr 1줄
+ exit 0 (block 안 함). reason 문구는 "강제" 가 아니라 "다음 판단 step 을
이어서 수행" — CPO 결재권 보존 (ADR-0004 §8).

ADR-0009 정합: stdlib only (json / os / sys / pathlib).
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

ENV_ALLOW_HALT = "LSKUN_ALLOW_EXTERNAL_HALT"


def main(argv: list[str] | None = None) -> int:
    try:
        out = _decide()
    except Exception as e:  # noqa: BLE001 — hook 은 block 외에 세션을 막지 않는다.
        print(f"lskun-kit stop_external: error {e!r}", file=sys.stderr)
        return 0
    if out is not None:
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stdout.write("\n")
    return 0


def _decide() -> "dict | None":
    stdin_text = sys.stdin.read()
    try:
        data = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    # 1. stop_hook_active=true → 무조건 통과 + marker 정리 (단일 invariant).
    #    Claude Code 가 본 hook 의 block 으로 재가동한 turn 의 종료 시도이므로
    #    여기서 다시 block 하면 무한 lockup. 무조건 allow + marker auto-unlink.
    if data.get("stop_hook_active") is True:
        _try_unlink_active_marker()
        return None

    # 2. escape hatch — 사용자가 명시적으로 turn 차단 우회 요청.
    if os.environ.get(ENV_ALLOW_HALT, "").strip() == "1":
        print(
            f"lskun-kit: WARNING — {ENV_ALLOW_HALT}=1 활성. "
            "외주 setup turn 차단이 우회되고 있다 (ADR-0022). "
            "세션 단위로만 사용하라.",
            file=sys.stderr,
        )
        return None

    # 3-4. 활성 회사 + marker.
    from lskun_kit.hooks._common import detect_company_root
    from lskun_kit import external_setup_state as state

    company_root = detect_company_root()
    if company_root is None:
        return None

    s = state.read(company_root.name)
    if s is None:
        return None  # read() 가 부재/malformed/stale/exhausted 자동 처리.

    # 5. block + reason ("CPO 다음 판단 이어서 수행" — 결재권 보존 문구).
    return {
        "decision": "block",
        "reason": (
            f"LSKun external setup 진행 중 (project={s.project}, "
            f"step={s.current_step}). 다음 판단 step {s.next_action} 을 "
            f"이어서 수행하라. CPO 의 결재 판단 break 가 필요하면 같은 turn "
            f"안에 결재 후 다음 step 으로. 사용자 입력 대기로 turn 종료 금지. "
            f"종료하려면: /lskun-kit:external cancel {s.project} 또는 "
            f"{ENV_ALLOW_HALT}=1."
        ),
    }


def _try_unlink_active_marker() -> None:
    """``stop_hook_active=true`` 경로에서 marker 자동 정리. 실패 무시."""
    try:
        from lskun_kit.hooks._common import detect_company_root
        from lskun_kit import external_setup_state as state
        cr = detect_company_root()
        if cr is not None:
            state.marker_path(cr.name).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
