"""PreToolUse hook — 워커 → 워커 chain 금지 + OMC fallback 차단 enforcement.

ADR-0001 §6 + ADR-0002 §6 + ADR-0004 §8 + ADR-0016.

두 축 enforcement:
    (1) 활성 워커 세션 도중 Task tool 호출 → deny (chain 차단, ADR-0004 §8)
    (2) 활성 회사 marker 박힌 프로젝트에서 ``subagent_type`` 이 차단 목록에
        속하는 Task 호출 → deny (OMC fallback 차단, ADR-0016).

평가 순서 (ADR-0016 결정 7):
    1. ``tool_name != "Task"`` → allow
    2. ``LSKUN_ALLOW_WORKER_CHAIN=1`` → allow + stderr (chain bypass)
    3. ``LSKUN_ALLOW_OMC_FALLBACK=1`` → allow + stderr (OMC bypass)
    4. 활성 회사 marker 부재 → allow (plugin 비활성)
    5. 활성 워커 세션 존재 → **chain deny** (ADR-0004 §8)
    6. ``subagent_type`` 차단 목록 매칭 → **OMC deny** (ADR-0016)
    7. fallthrough → allow

차단 목록 (ADR-0016 결정 1):
    - ``oh-my-claudecode:*`` (prefix 매칭, 모든 OMC 변형)
    - ``general-purpose`` (정확 매칭)

허용 (whitelist):
    - ``Explore``, ``Plan``, 외부 plugin agent, 미지정 → 통과
    - 단 Explore/Plan 의 persona 흉내 우회는 cpo.md text instruction 으로만 가드 (ADR-0016 §"인지된 잔존 위험")

입력 (stdin):
    Claude Code PreToolUse hook payload (JSON)::

        {"tool_name": "Task", "tool_input": {"subagent_type": "...", ...}}

    ``subagent_type`` 의 정확한 키 이름 / 위치는 ADR-0016 결정 3 — 실측 확정.
    실측 모드: ``LSKUN_HOOK_DEBUG_DUMP=1`` 설정 시 payload 전체를 stderr 로
    dump (구현 phase 의 첫 작업, 실측 후 제거 예정).

출력 (stdout):
    Claude Code PreToolUse hook 사양::

        {"hookSpecificOutput":
            {"hookEventName": "PreToolUse",
             "permissionDecision": "allow|deny",
             "permissionDecisionReason": "..."}}

종료 코드: 항상 0 — hook 실패는 세션을 막지 않는다 (decision 만 'allow' fallback).

활성 회사 marker 검출 (ADR-0016 결정 2):
    1. ``LSKUN_SSOT_ROOT`` env var set → 회사 root 로 사용 (O(1), 정상 경로)
    2. env var 부재 시 ``session_start._find_active_company_root()`` 로 fallback —
       cwd 상위 CLAUDE.md marker 직접 검출 (파일 I/O 동반). marker 미박제
       프로젝트는 영향 0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# P48 — 직접 경로 호출 시 self-bootstrap (P48 hook command 형태 대응).
_SRC_DIR = str(Path(__file__).resolve().parents[2])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

TOOL_TASK = "Task"
ENV_SSOT_ROOT = "LSKUN_SSOT_ROOT"
ENV_ALLOW_CHAIN = "LSKUN_ALLOW_WORKER_CHAIN"
ENV_ALLOW_OMC = "LSKUN_ALLOW_OMC_FALLBACK"  # ADR-0016 결정 5
ENV_DEBUG_DUMP = "LSKUN_HOOK_DEBUG_DUMP"    # ADR-0016 결정 3 — 임시 실측 모드

# ADR-0016 결정 1 — 차단 패턴.
# prefix 매칭은 OMC 의 모든 변형 차단 (executor / analyst / planner / architect ...).
_OMC_BLOCK_PREFIXES = ("oh-my-claudecode:",)
_OMC_BLOCK_EXACT = frozenset({"general-purpose"})


def main(argv: list[str] | None = None) -> int:
    stdin_text = sys.stdin.read()

    # ADR-0016 결정 3 — 실측 모드. 임시 dump 후 정상 평가 계속.
    if os.environ.get(ENV_DEBUG_DUMP, "").strip() == "1":
        _dump_payload(stdin_text)

    try:
        decision, reason = _decide(stdin_text)
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
    """payload + 환경을 보고 (decision, reason) 반환.

    decision ∈ {"allow", "deny"}.
    평가 순서는 모듈 docstring 의 7단계.
    """

    data = _parse_payload(stdin_text)
    tool_name = data.get("tool_name") if isinstance(data, dict) else ""

    # 1. Task tool 외는 무조건 allow.
    if tool_name != TOOL_TASK:
        return "allow", ""

    # 2. chain bypass.
    if os.environ.get(ENV_ALLOW_CHAIN, "").strip() == "1":
        print(
            "lskun-kit: WARNING — LSKUN_ALLOW_WORKER_CHAIN=1 활성. "
            "워커 → 워커 chain 차단이 우회되고 있다 (ADR-0004 §8). "
            "디버깅이 끝나면 해당 환경변수를 unset 하라.",
            file=sys.stderr,
        )
        return "allow", "LSKUN_ALLOW_WORKER_CHAIN=1 — chain enforcement bypass"

    # 3. OMC bypass (ADR-0016 결정 5).
    if os.environ.get(ENV_ALLOW_OMC, "").strip() == "1":
        print(
            "lskun-kit: WARNING — LSKUN_ALLOW_OMC_FALLBACK=1 활성. "
            "OMC fallback 차단이 우회되고 있다 (ADR-0016). 세션 단위로만 사용하라. "
            ".zshrc/.bashrc 영구 export 는 가드를 무력화한다.",
            file=sys.stderr,
        )
        return "allow", "LSKUN_ALLOW_OMC_FALLBACK=1 — OMC enforcement bypass"

    # 4. 활성 회사 marker 검출 (ADR-0016 결정 2).
    company_root = _detect_company_root()
    if company_root is None:
        # plugin 비활성 환경 — 두 가드 모두 skip.
        return "allow", ""

    # 5. chain 차단 (ADR-0004 §8) — OMC 차단보다 우선 (ADR-0016 결정 7).
    from lskun_kit import session  # 지연 import — hooks 의존성 격리

    sess = session.read(company_root)
    if sess is not None:
        return (
            "deny",
            (
                f"LSKunCompanyKit: 워커 '{sess.active_worker}' 세션 중 Task tool 호출 차단 "
                f"(ADR-0004 §8 — 워커 → 워커 chain 금지). 결재 / 추가 dispatch 가 필요하면 "
                f"세션을 종료하고 메인 세션 = CPO 에게 요청하라. 디버깅 시 "
                f"LSKUN_ALLOW_WORKER_CHAIN=1 로 bypass 가능."
            ),
        )

    # 6. OMC fallback 차단 (ADR-0016 결정 1).
    subagent_type = _extract_subagent_type(data)
    if subagent_type and _is_blocked(subagent_type):
        return (
            "deny",
            (
                f"LSKunCompanyKit: subagent_type='{subagent_type}' 차단 (ADR-0016). "
                f"활성 회사 컨텍스트 ({company_root.name}) 에서 LSKun 워커 dispatch 는 "
                f"반드시 Skill 경유: Skill(skill=\"LSKunCompanyKit:work\", "
                f"args=\"<worker> \\\"<task>\\\"\"). 일반 작업 (워커 dispatch 아님) 이면 "
                f"Explore/Plan 등 read-only agent 사용 가능. 디버깅 시 "
                f"LSKUN_ALLOW_OMC_FALLBACK=1 로 bypass 가능 (세션 단위 권장)."
            ),
        )

    # 7. fallthrough.
    return "allow", ""


def _detect_company_root() -> Path | None:
    """활성 회사 root 검출 (ADR-0016 결정 2).

    1순위: ``LSKUN_SSOT_ROOT`` env var (O(1)).
    2순위: cwd 상위 CLAUDE.md marker 직접 검출 (session_start 재사용).
    """

    env_root = os.environ.get(ENV_SSOT_ROOT, "").strip()
    if env_root:
        path = Path(env_root)
        return path if path.exists() else None

    # session_start 의 marker 검출 재사용. import 실패 시 (테스트 환경 등) None.
    try:
        from lskun_kit.hooks.session_start import _find_active_company_root  # type: ignore[attr-defined]
    except ImportError:
        return None
    return _find_active_company_root()


def _extract_subagent_type(data: object) -> str:
    """payload 에서 ``subagent_type`` 추출. 실측 전 추정 키 위치.

    ADR-0016 결정 3 — 실측으로 정확한 키 위치 확정 필요. 현재 가설:
        - ``tool_input.subagent_type``: 1순위 (Task tool 의 일반적 input schema)
        - ``tool_input.subagentType``: camelCase fallback
        - ``data.subagent_type``: top-level fallback

    실측 후 본 함수의 키 경로를 확정한다. 부재 / 비문자열은 빈 문자열 반환.
    """

    if not isinstance(data, dict):
        return ""

    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("subagent_type", "subagentType"):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                return val

    # top-level fallback (Claude Code 가 별도 위치로 전달할 가능성).
    val = data.get("subagent_type")
    return val if isinstance(val, str) else ""


def _is_blocked(subagent_type: str) -> bool:
    """차단 목록 매칭 (ADR-0016 결정 1)."""

    if subagent_type in _OMC_BLOCK_EXACT:
        return True
    return any(subagent_type.startswith(pref) for pref in _OMC_BLOCK_PREFIXES)


def _parse_payload(stdin_text: str) -> dict | str:
    """stdin payload 파싱. 실패 시 빈 dict."""

    if not stdin_text.strip():
        return {}
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _dump_payload(stdin_text: str) -> None:
    """ADR-0016 결정 3 — 실측 모드. payload 전체 stderr dump.

    구현 phase 첫 작업 후 ``LSKUN_HOOK_DEBUG_DUMP`` 를 unset 하여 dump 제거.
    실측 결과는 ADR-0016 ``## 실측 결과 (P95)`` 섹션에 추가 박제.
    """

    print("=" * 60, file=sys.stderr)
    print("lskun-kit DEBUG DUMP (LSKUN_HOOK_DEBUG_DUMP=1, ADR-0016 결정 3):", file=sys.stderr)
    try:
        parsed = json.loads(stdin_text) if stdin_text.strip() else None
        print(json.dumps(parsed, ensure_ascii=False, indent=2), file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[parse error: {e!r}] raw stdin:", file=sys.stderr)
        print(stdin_text, file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
