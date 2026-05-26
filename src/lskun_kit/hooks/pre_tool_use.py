"""PreToolUse hook — 워커 → 워커 chain 금지 + Dispatch subagent_type allowlist enforcement.

ADR-0001 §6 + ADR-0002 §6 + ADR-0004 §8 + ADR-0016 + ADR-0017.

두 축 enforcement:
    (1) 활성 워커 세션 도중 Task tool 호출 → deny (chain 차단, ADR-0004 §8)
    (2) 활성 회사 marker 박힌 프로젝트에서 ``subagent_type`` 이 allowlist 외이면
        deny (Dispatch subagent_type Allowlist, ADR-0017 — denylist (ADR-0016) 폐기).

평가 순서 (ADR-0017 결정 7, ADR-0016 결정 7 갱신):
    1. ``tool_name != "Task"`` → allow
    2. ``LSKUN_ALLOW_WORKER_CHAIN=1`` → allow + stderr (chain bypass)
    3. ``LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1`` OR ``LSKUN_ALLOW_OMC_FALLBACK=1`` (별칭)
       → allow + stderr (allowlist bypass, ADR-0017 결정 2)
    4. 활성 회사 marker 부재 → allow (plugin 비활성)
    5. 활성 워커 세션 존재 → **chain deny** (ADR-0004 §8)
    6. ``subagent_type`` 미지정 / null → allow (일반 Task 호출)
    7. ``subagent_type == "claude"`` → allow (정식 dispatch, ADR-0017 결정 1)
    8. fallthrough → **deny** (allowlist 본질, ADR-0017)

Allowlist (ADR-0017 결정 1):
    - ``claude`` (정확 매칭) — 정식 dispatch 경로
    - 미지정 / null — 일반 Task 호출 (subagent 선택 없이 default)

차단 대상 (ADR-0017 결정 1 — claude 외 전부):
    - ``oh-my-claudecode:*`` (ADR-0016 차단 계승)
    - ``general-purpose`` (ADR-0016 차단 계승)
    - ``vercel:*``, ``codex:*``, ``figma:*``, ``posthog:*`` 등 외부 plugin subagent
      → LSKun 회사 작업 중 OMC 외 plugin subagent 도 차단. 회사 외 작업이면 escape hatch.
    - ``Explore``, ``Plan`` 등 read-only agent → 정책 강화로 차단

Escape hatch (ADR-0017 결정 2 — 의도별 분리, 둘 다 동일 효과):
    - ``LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1`` (신규 정식, 의미 명확)
    - ``LSKUN_ALLOW_OMC_FALLBACK=1``       (ADR-0016 별칭, 하위호환)

입력 (stdin):
    Claude Code PreToolUse hook payload (JSON)::

        {"tool_name": "Task", "tool_input": {"subagent_type": "...", ...}}

출력 (stdout):
    Claude Code PreToolUse hook 사양::

        {"hookSpecificOutput":
            {"hookEventName": "PreToolUse",
             "permissionDecision": "allow|deny",
             "permissionDecisionReason": "..."}}

종료 코드: 항상 0 — hook 실패는 세션을 막지 않는다 (decision 만 'allow' fallback).

활성 회사 marker 검출 (ADR-0016 결정 2 계승):
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
ENV_ALLOW_NON_CLAUDE = "LSKUN_ALLOW_NON_CLAUDE_DISPATCH"  # ADR-0017 결정 2 (신규 정식)
ENV_ALLOW_OMC = "LSKUN_ALLOW_OMC_FALLBACK"                # ADR-0017 결정 2 (ADR-0016 별칭)
ENV_DEBUG_DUMP = "LSKUN_HOOK_DEBUG_DUMP"

# ADR-0017 결정 1 — Allowlist.
# subagent_type == "claude" 만 정식 dispatch 로 허용. 그 외 전부 deny.
# subagent_type 미지정 / null 은 별도 평가 (일반 Task 호출로 allow).
_ALLOWED_SUBAGENT = frozenset({"claude"})


def main(argv: list[str] | None = None) -> int:
    stdin_text = sys.stdin.read()

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
    평가 순서는 모듈 docstring 의 8단계 (ADR-0017 결정 7).
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

    # 3. allowlist bypass (ADR-0017 결정 2). 신규 정식 + ADR-0016 별칭 둘 다 수용.
    bypass_var = _detect_allowlist_bypass()
    if bypass_var is not None:
        print(
            f"lskun-kit: WARNING — {bypass_var}=1 활성. "
            "Dispatch subagent_type allowlist 차단이 우회되고 있다 (ADR-0017). "
            "세션 단위로만 사용하라. .zshrc/.bashrc 영구 export 는 가드를 무력화한다 "
            "(doctor [23]).",
            file=sys.stderr,
        )
        return "allow", f"{bypass_var}=1 — allowlist enforcement bypass"

    # 4. 활성 회사 marker 검출.
    company_root = _detect_company_root()
    if company_root is None:
        return "allow", ""

    # 5. chain 차단 (ADR-0004 §8) — allowlist 차단보다 우선 (ADR-0017 결정 7).
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

    # 6/7/8. allowlist 평가 (ADR-0017 결정 1).
    subagent_type = _extract_subagent_type(data)

    # 6. 미지정 / null → 일반 Task 호출로 allow.
    if not subagent_type:
        return "allow", ""

    # 7. "claude" 정식 dispatch → allow.
    if subagent_type in _ALLOWED_SUBAGENT:
        return "allow", ""

    # 8. fallthrough → deny (allowlist 본질).
    return (
        "deny",
        (
            f"LSKunCompanyKit: subagent_type='{subagent_type}' 차단 (ADR-0017 allowlist). "
            f"활성 회사 컨텍스트 ({company_root.name}) 의 정식 dispatch 는 "
            f"subagent_type='claude' 만 허용. "
            f"LSKun 워커 dispatch: Task(subagent_type=\"claude\", prompt=...). "
            f"회사 외 작업 (vercel/codex/figma 등 plugin subagent 의도 사용) 이면: "
            f"export LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1 (세션 단위 권장). "
            f".zshrc/.bashrc 영구 export 는 가드를 무력화한다 (doctor [23])."
        ),
    )


def _detect_allowlist_bypass() -> str | None:
    """ADR-0017 결정 2 — bypass env 둘 중 하나라도 set 이면 var 이름 반환.

    우선순위 (메시지 일관성):
        1. ``LSKUN_ALLOW_NON_CLAUDE_DISPATCH`` (신규 정식)
        2. ``LSKUN_ALLOW_OMC_FALLBACK`` (ADR-0016 별칭, 하위호환)
    """

    if os.environ.get(ENV_ALLOW_NON_CLAUDE, "").strip() == "1":
        return ENV_ALLOW_NON_CLAUDE
    if os.environ.get(ENV_ALLOW_OMC, "").strip() == "1":
        return ENV_ALLOW_OMC
    return None


def _detect_company_root() -> Path | None:
    """활성 회사 root 검출 (ADR-0016 결정 2 계승).

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


def _extract_subagent_type(data: object) -> str:
    """payload 에서 ``subagent_type`` 추출.

    가설 키 위치:
        - ``tool_input.subagent_type``: 1순위
        - ``tool_input.subagentType``: camelCase fallback
        - ``data.subagent_type``: top-level fallback
    """

    if not isinstance(data, dict):
        return ""

    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("subagent_type", "subagentType"):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                return val

    val = data.get("subagent_type")
    return val if isinstance(val, str) else ""


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
    """``LSKUN_HOOK_DEBUG_DUMP=1`` 실측 모드. payload 전체 stderr dump."""

    print("=" * 60, file=sys.stderr)
    print("lskun-kit DEBUG DUMP (LSKUN_HOOK_DEBUG_DUMP=1):", file=sys.stderr)
    try:
        parsed = json.loads(stdin_text) if stdin_text.strip() else None
        print(json.dumps(parsed, ensure_ascii=False, indent=2), file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[parse error: {e!r}] raw stdin:", file=sys.stderr)
        print(stdin_text, file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
