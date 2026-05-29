"""Stop hook — 외주 setup turn 종료 차단 테스트 (ADR-0022, P121 Task 3).

평가 순서 (spec §5.2):
    1. stop_hook_active=true → exit 0 + auto-unlink (무한 lockup 방지 invariant)
    2. LSKUN_ALLOW_EXTERNAL_HALT=1 → exit 0 + stderr warn (escape hatch)
    3. 활성 회사 root 부재 → exit 0
    4. marker 부재/malformed/stale/exhausted → exit 0 (read 가 unlink 처리)
    5. block + reason ("이어서 수행" — CPO 결재권 보존 문구)

mocking 패턴은 실증된 test_hooks_post_tool_use_external.py 와 일치
(``mock.patch.object(Path, "home")`` + ``LSKUN_SSOT_ROOT`` env).
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as ess  # noqa: E402
from lskun_kit.hooks import stop_external as hook  # noqa: E402


def _run(stdin_text: str, env: dict[str, str]) -> tuple[dict | None, str, int]:
    """hook main 을 단발성 실행. (parsed_stdout|None, stderr, rc) 반환."""
    with patch.dict(os.environ, env, clear=True), \
         patch("sys.stdin", io.StringIO(stdin_text)), \
         patch("sys.stdout", io.StringIO()) as out, \
         patch("sys.stderr", io.StringIO()) as err:
        rc = hook.main([])
    s = out.getvalue().strip()
    parsed = json.loads(s) if s else None
    return parsed, err.getvalue(), rc


def _payload(stop_hook_active: bool = False) -> str:
    return json.dumps({
        "session_id": "test",
        "stop_hook_active": stop_hook_active,
        "transcript_path": "/tmp/x",
    })


class _HomeTmp(unittest.TestCase):
    """tmp home + Path.home patch 공통 fixture (Task 2 패턴 일치)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.patcher = mock.patch.object(Path, "home", return_value=self.home)
        self.patcher.start()
        self.company_root = self.home / ".lskun-companies" / "acme"
        self.company_root.mkdir(parents=True)

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.cleanup()

    @property
    def env(self) -> dict[str, str]:
        return {"LSKUN_SSOT_ROOT": str(self.company_root)}


class StopHookActiveTest(_HomeTmp):
    """무한 lockup 방지의 단일 invariant — architect MAJOR."""

    def test_stop_hook_active_passes_immediately(self) -> None:
        ess.start("acme", "proj")  # marker 살아있음
        parsed, _, rc = _run(_payload(stop_hook_active=True), self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)  # 출력 없음 = allow
        self.assertFalse(ess.marker_path("acme").exists())  # auto-unlink


class EscapeHatchTest(_HomeTmp):
    def test_env_skip_passes(self) -> None:
        ess.start("acme", "proj")
        env = dict(self.env)
        env["LSKUN_ALLOW_EXTERNAL_HALT"] = "1"
        parsed, err, rc = _run(_payload(), env)
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)
        self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", err)


class MarkerAbsentTest(_HomeTmp):
    def test_no_marker_no_block(self) -> None:
        parsed, _, rc = _run(_payload(), self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)


class MarkerPresentBlockTest(_HomeTmp):
    def test_marker_present_blocks(self) -> None:
        ess.start("acme", "proj")
        parsed, _, rc = _run(_payload(), self.env)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["decision"], "block")
        self.assertIn("external setup", parsed["reason"])
        self.assertIn("project=proj", parsed["reason"])
        # CPO 결재권 보존 — reason 문구가 "강제" 가 아니라 "이어서 수행"
        self.assertIn("이어서", parsed["reason"])
        # escape hatch 안내
        self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", parsed["reason"])

    def test_exhausted_marker_no_block(self) -> None:
        """exhausted marker → read() 가 unlink + None → block 안 함."""
        ess.start("acme", "proj")
        path = ess.marker_path("acme")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["step_count_so_far"] = data["max_step_count"] + 1
        path.write_text(json.dumps(data), encoding="utf-8")

        parsed, _, rc = _run(_payload(), self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)
        self.assertFalse(path.exists())  # auto-unlinked


class HookSafetyTest(unittest.TestCase):
    def test_malformed_stdin_no_block(self) -> None:
        parsed, _, rc = _run("{ bad", {})
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)

    def test_empty_stdin_no_block(self) -> None:
        parsed, _, rc = _run("", {})
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)

    def test_nonexistent_ssot_root_no_block(self) -> None:
        """company_root 가 invalid 경로일 때도 block 안 함."""
        parsed, _, rc = _run(_payload(), {"LSKUN_SSOT_ROOT": "/nonexistent/xyz"})
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
