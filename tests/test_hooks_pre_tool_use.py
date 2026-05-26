"""PreToolUse hook — 워커 chain 차단 + Dispatch allowlist 검증.

ADR-0004 §8 (chain 차단) + ADR-0016 (denylist, deprecated) + ADR-0017 (allowlist).

테스트 케이스 25건:
    - 기존 7건: chain 차단 + bypass + 비활성 환경 (회귀 검증)
    - 갱신 10건: ADR-0016 의 denylist 케이스를 ADR-0017 allowlist 정책으로 반전
    - 신규 8건: ADR-0017 결정 9 의 allowlist 시나리오
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import session  # noqa: E402
from lskun_kit.hooks import pre_tool_use  # noqa: E402


def _run(stdin_text: str, env: dict[str, str]) -> dict:
    with patch.dict(os.environ, env, clear=True), \
         patch("sys.stdin", io.StringIO(stdin_text)), \
         patch("sys.stdout", io.StringIO()) as out, \
         patch("sys.stderr", io.StringIO()):
        rc = pre_tool_use.main([])
    assert rc == 0
    return json.loads(out.getvalue())


def _run_capture_stderr(stdin_text: str, env: dict[str, str]) -> tuple[dict, str]:
    with patch.dict(os.environ, env, clear=True), \
         patch("sys.stdin", io.StringIO(stdin_text)), \
         patch("sys.stdout", io.StringIO()) as out, \
         patch("sys.stderr", io.StringIO()) as err:
        rc = pre_tool_use.main([])
    assert rc == 0
    return json.loads(out.getvalue()), err.getvalue()


def _task_payload(subagent_type: str | None = None) -> str:
    """Task tool payload 직렬화. ``subagent_type`` 이 있으면 ``tool_input`` 에 박제."""

    payload: dict[str, object] = {"tool_name": "Task"}
    if subagent_type is not None:
        payload["tool_input"] = {"subagent_type": subagent_type}
    return json.dumps(payload)


# =========================================================================
# 기존 7건 (chain 차단, ADR-0004 §8) — 회귀 검증
# =========================================================================
class PreToolUseHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_non_task_tool_always_allowed(self) -> None:
        out = _run(json.dumps({"tool_name": "Read"}), {})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_task_without_active_worker_allowed(self) -> None:
        """메인 세션 = CPO 가 워커 dispatch 하는 정상 경로 (subagent_type 미지정)."""
        out = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.root)},
        )
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_task_during_worker_session_denied(self) -> None:
        """워커 세션 중 sub-Task 호출 → deny (ADR-0004 §8)."""
        session.start(self.root, "alice")
        out = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.root)},
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(decision, "deny")
        self.assertIn("alice", reason)
        self.assertIn("ADR-0004", reason)

    def test_bypass_env_var_allows_chain(self) -> None:
        """LSKUN_ALLOW_WORKER_CHAIN=1 escape hatch."""
        session.start(self.root, "alice")
        out = _run(
            _task_payload(),
            {
                "LSKUN_SSOT_ROOT": str(self.root),
                "LSKUN_ALLOW_WORKER_CHAIN": "1",
            },
        )
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_bypass_emits_stderr_warning(self) -> None:
        """bypass 활성 시 사용자에게 stderr 경고로 가시화."""
        session.start(self.root, "alice")
        out, err = _run_capture_stderr(
            _task_payload(),
            {
                "LSKUN_SSOT_ROOT": str(self.root),
                "LSKUN_ALLOW_WORKER_CHAIN": "1",
            },
        )
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertIn("WARNING", err)
        self.assertIn("LSKUN_ALLOW_WORKER_CHAIN", err)

    def test_no_ssot_root_allows(self) -> None:
        """plugin 비활성 환경 — chain 검사 skip."""
        out = _run(_task_payload(), {})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_malformed_stdin_falls_back_to_allow(self) -> None:
        out = _run("not-json", {"LSKUN_SSOT_ROOT": str(self.root)})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")


# =========================================================================
# ADR-0017 갱신 10건 — Allowlist 정책 (ADR-0016 denylist 반전)
# =========================================================================
class DispatchAllowlistTests(unittest.TestCase):
    """ADR-0017 결정 9 — Allowlist 모델 검증.

    ADR-0016 의 10 케이스 중 #4 (Explore), #5 (Plan), #6 (외부 plugin) 은
    allow → deny 로 기대값 반전. #9 의 env var 명도 별칭 유지 확인.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.env_with_marker = {"LSKUN_SSOT_ROOT": str(self.root)}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # 1. marker 있음 + oh-my-claudecode:executor → deny (ADR-0016 차단 계승)
    def test_omc_executor_denied(self) -> None:
        out = _run(
            _task_payload("oh-my-claudecode:executor"),
            self.env_with_marker,
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(decision, "deny")
        self.assertIn("ADR-0017", reason)
        self.assertIn("oh-my-claudecode:executor", reason)
        self.assertIn("claude", reason)

    # 2. marker 있음 + general-purpose → deny (ADR-0016 차단 계승)
    def test_general_purpose_denied(self) -> None:
        out = _run(
            _task_payload("general-purpose"),
            self.env_with_marker,
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(decision, "deny")
        self.assertIn("ADR-0017", reason)
        self.assertIn("general-purpose", reason)

    # 3. 와일드카드 — oh-my-claudecode:analyst 도 차단 (allowlist 외)
    def test_omc_wildcard_analyst_denied(self) -> None:
        out = _run(
            _task_payload("oh-my-claudecode:analyst"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    # 4. Explore → deny (ADR-0017 정책 강화, ADR-0016 의 allow 반전)
    def test_explore_denied(self) -> None:
        out = _run(
            _task_payload("Explore"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    # 5. Plan → deny (ADR-0017 정책 강화)
    def test_plan_denied(self) -> None:
        out = _run(
            _task_payload("Plan"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    # 6. 외부 plugin agent → deny (ADR-0017 정책 강화)
    def test_external_plugin_agent_denied(self) -> None:
        out = _run(
            _task_payload("code-review-graph:review-pr"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    # 7. subagent_type 미지정 → allow (일반 Task)
    def test_no_subagent_type_allowed(self) -> None:
        out = _run(_task_payload(), self.env_with_marker)
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    # 8. marker 없음 + OMC executor → allow (가드 비활성)
    def test_omc_without_marker_allowed(self) -> None:
        out = _run(_task_payload("oh-my-claudecode:executor"), {})
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    # 9. 별칭 bypass — LSKUN_ALLOW_OMC_FALLBACK=1 → allow + stderr
    def test_omc_alias_bypass_allows_with_warning(self) -> None:
        out, err = _run_capture_stderr(
            _task_payload("oh-my-claudecode:executor"),
            {
                "LSKUN_SSOT_ROOT": str(self.root),
                "LSKUN_ALLOW_OMC_FALLBACK": "1",
            },
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn("WARNING", err)
        self.assertIn("LSKUN_ALLOW_OMC_FALLBACK", err)

    # 10. chain + allowlist 동시 — chain 우선 (ADR-0017 결정 7)
    def test_chain_takes_precedence_over_allowlist(self) -> None:
        """워커 세션 active + claude 외 subagent_type → chain deny 우선."""
        session.start(self.root, "alice")
        out = _run(
            _task_payload("oh-my-claudecode:executor"),
            self.env_with_marker,
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(decision, "deny")
        # chain 차단 reason 이 우선 (ADR-0004 §8 메시지).
        self.assertIn("ADR-0004", reason)
        self.assertIn("alice", reason)
        self.assertNotIn("ADR-0017", reason)


# =========================================================================
# ADR-0017 신규 8건 — Allowlist 결정 9 신규 케이스
# =========================================================================
class AllowlistAdr0017NewTests(unittest.TestCase):
    """ADR-0017 결정 9 — 신규 8 케이스."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.env_with_marker = {"LSKUN_SSOT_ROOT": str(self.root)}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # N1. claude 정식 dispatch → allow
    def test_claude_subagent_allowed(self) -> None:
        out = _run(
            _task_payload("claude"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    # N2. subagent_type 미지정 / null → allow (일반 Task)
    def test_null_subagent_allowed(self) -> None:
        # 이미 #7 에서 미지정 케이스 검증. 여기는 명시적으로 None 박제.
        payload = json.dumps({"tool_name": "Task", "tool_input": {"subagent_type": None}})
        out = _run(payload, self.env_with_marker)
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    # N3. vercel:deployment-expert → deny (allowlist 외)
    def test_vercel_subagent_denied(self) -> None:
        out = _run(
            _task_payload("vercel:deployment-expert"),
            self.env_with_marker,
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(decision, "deny")
        self.assertIn("vercel:deployment-expert", reason)
        self.assertIn("LSKUN_ALLOW_NON_CLAUDE_DISPATCH", reason)

    # N4. codex:codex-rescue → deny
    def test_codex_subagent_denied(self) -> None:
        out = _run(
            _task_payload("codex:codex-rescue"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    # N5. Explore → deny (ADR-0017 정책 강화 재확인, 갱신 #4 와 별개로 명시)
    def test_explore_denied_explicit(self) -> None:
        out = _run(
            _task_payload("Explore"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    # N6. 신규 정식 env LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1 → allow + stderr
    def test_non_claude_dispatch_bypass_allows_with_warning(self) -> None:
        out, err = _run_capture_stderr(
            _task_payload("vercel:deployment-expert"),
            {
                "LSKUN_SSOT_ROOT": str(self.root),
                "LSKUN_ALLOW_NON_CLAUDE_DISPATCH": "1",
            },
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn("WARNING", err)
        self.assertIn("LSKUN_ALLOW_NON_CLAUDE_DISPATCH", err)
        self.assertIn("ADR-0017", err)

    # N7. 두 bypass 모두 set 시 신규 정식 var 가 우선 메시지 (priority 순서)
    def test_both_bypass_set_prefers_new_var(self) -> None:
        out, err = _run_capture_stderr(
            _task_payload("vercel:deployment-expert"),
            {
                "LSKUN_SSOT_ROOT": str(self.root),
                "LSKUN_ALLOW_NON_CLAUDE_DISPATCH": "1",
                "LSKUN_ALLOW_OMC_FALLBACK": "1",
            },
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        # 신규 정식 var 가 메시지 + reason 모두에 등장.
        self.assertIn("LSKUN_ALLOW_NON_CLAUDE_DISPATCH", err)
        self.assertIn(
            "LSKUN_ALLOW_NON_CLAUDE_DISPATCH",
            out["hookSpecificOutput"]["permissionDecisionReason"],
        )

    # N8. chain + allowlist 동시 — claude 인 경우에도 chain 우선
    def test_chain_takes_precedence_even_with_claude(self) -> None:
        session.start(self.root, "alice")
        out = _run(
            _task_payload("claude"),
            self.env_with_marker,
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        # claude 는 allowlist 통과지만, chain 검사가 먼저 deny.
        self.assertEqual(decision, "deny")
        self.assertIn("ADR-0004", reason)
        self.assertIn("alice", reason)


if __name__ == "__main__":
    unittest.main()
