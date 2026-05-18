"""PreToolUse hook — 워커 → 워커 chain 금지 enforcement 검증.

ADR-0004 §8. 활성 워커 세션 도중 Task tool 호출은 deny, 그 외는 allow.
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
            json.dumps({"tool_name": "Task"}),
            {"LSKUN_SSOT_ROOT": str(self.root)},
        )
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_task_during_worker_session_denied(self) -> None:
        """워커 세션 중 sub-Task 호출 → deny (ADR-0004 §8)."""
        session.start(self.root, "alice")
        out = _run(
            json.dumps({"tool_name": "Task"}),
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
            json.dumps({"tool_name": "Task"}),
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
            json.dumps({"tool_name": "Task"}),
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
        out = _run(json.dumps({"tool_name": "Task"}), {})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_malformed_stdin_falls_back_to_allow(self) -> None:
        out = _run("not-json", {"LSKUN_SSOT_ROOT": str(self.root)})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "allow")


if __name__ == "__main__":
    unittest.main()
