"""PreToolUse hook — 워커 chain 차단 + OMC fallback 차단 검증.

ADR-0004 §8 (chain 차단) + ADR-0016 (OMC fallback 차단).

테스트 케이스 17건:
    - 기존 7건: chain 차단 + bypass + 비활성 환경 (회귀 검증)
    - 신규 10건: OMC fallback 차단 시나리오 (ADR-0016 결정 9)
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
        """메인 세션 = CPO 가 워커 dispatch 하는 정상 경로."""
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
        """P38 (#18) — bypass 활성 시 사용자에게 stderr 경고로 가시화."""
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
# ADR-0016 신규 10건 — OMC fallback 차단
# =========================================================================
class OmcFallbackBlockTests(unittest.TestCase):
    """ADR-0016 결정 9 의 10 케이스 테이블 검증."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.env_with_marker = {"LSKUN_SSOT_ROOT": str(self.root)}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # 1. marker 있음 + oh-my-claudecode:executor → deny
    def test_omc_executor_denied(self) -> None:
        out = _run(
            _task_payload("oh-my-claudecode:executor"),
            self.env_with_marker,
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(decision, "deny")
        self.assertIn("ADR-0016", reason)
        self.assertIn("oh-my-claudecode:executor", reason)
        self.assertIn("Skill", reason)

    # 2. marker 있음 + general-purpose → deny
    def test_general_purpose_denied(self) -> None:
        out = _run(
            _task_payload("general-purpose"),
            self.env_with_marker,
        )
        decision = out["hookSpecificOutput"]["permissionDecision"]
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(decision, "deny")
        self.assertIn("ADR-0016", reason)
        self.assertIn("general-purpose", reason)

    # 3. 와일드카드 — oh-my-claudecode:analyst 도 차단
    def test_omc_wildcard_analyst_denied(self) -> None:
        out = _run(
            _task_payload("oh-my-claudecode:analyst"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    # 4. Explore allow
    def test_explore_allowed(self) -> None:
        out = _run(
            _task_payload("Explore"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    # 5. Plan allow
    def test_plan_allowed(self) -> None:
        out = _run(
            _task_payload("Plan"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    # 6. 외부 plugin agent allow
    def test_external_plugin_agent_allowed(self) -> None:
        out = _run(
            _task_payload("code-review-graph:review-pr"),
            self.env_with_marker,
        )
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "allow"
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

    # 9. OMC bypass on → allow + stderr 경고
    def test_omc_bypass_allows_with_warning(self) -> None:
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

    # 10. chain + OMC 동시 — chain 우선 (결정 7)
    def test_chain_takes_precedence_over_omc(self) -> None:
        """워커 세션 active + OMC subagent_type 동시 → chain deny 우선."""
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
        self.assertNotIn("ADR-0016", reason)


if __name__ == "__main__":
    unittest.main()
