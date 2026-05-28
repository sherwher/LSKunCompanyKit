"""PostToolUse:Task hook — 외주 setup 다음 step push 테스트 (ADR-0022, P121 Task 2).

평가 순서 (spec §5.1):
    1. ``tool_name != "Task"`` → exit 0 (no output)
    2. ``LSKUN_ALLOW_EXTERNAL_HALT=1`` → exit 0 + stderr warn
    3. 활성 회사 root 검출 실패 → exit 0
    4. marker 부재 → exit 0
    5. malformed/stale/exhausted → ``read()`` 가 auto-unlink 후 ``None`` → exit 0
    6. ``advance()`` 로 step_count_so_far += 1
    7. ``<system-reminder>`` stdout 주입 + exit 0
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as ess  # noqa: E402
from lskun_kit.hooks import post_tool_use_external  # noqa: E402


def _run(stdin_text: str, env: dict[str, str]) -> tuple[int, str, str]:
    """hook main 을 단발성 실행. (rc, stdout, stderr) 반환."""
    with patch.dict(os.environ, env, clear=True), \
         patch("sys.stdin", io.StringIO(stdin_text)), \
         patch("sys.stdout", io.StringIO()) as out, \
         patch("sys.stderr", io.StringIO()) as err:
        rc = post_tool_use_external.main([])
    return rc, out.getvalue(), err.getvalue()


def _task_payload(tool_name: str = "Task") -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": {"subagent_type": "claude"}})


class NonTaskToolTest(unittest.TestCase):
    """tool_name != Task → exit 0, no output (마커 검사도 안 함)."""

    def test_read_tool_exits_silently(self) -> None:
        rc, out, err = _run(json.dumps({"tool_name": "Read"}), {})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    def test_bash_tool_exits_silently(self) -> None:
        rc, out, err = _run(json.dumps({"tool_name": "Bash"}), {})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")


class EscapeHatchTest(unittest.TestCase):
    """LSKUN_ALLOW_EXTERNAL_HALT=1 → exit 0 + stderr 경고 (system-reminder 미주입)."""

    def test_escape_hatch_suppresses_reminder(self) -> None:
        rc, out, err = _run(
            _task_payload(),
            {"LSKUN_ALLOW_EXTERNAL_HALT": "1"},
        )
        self.assertEqual(rc, 0)
        self.assertNotIn("<system-reminder>", out)
        self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", err)


class MarkerAbsentTest(unittest.TestCase):
    """활성 회사 root 는 검출되었으나 marker 부재 → exit 0, no output."""

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

    def test_no_marker_no_output(self) -> None:
        rc, out, err = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.company_root)},
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_no_company_root_no_output(self) -> None:
        """LSKUN_SSOT_ROOT 부재 + cwd 에 CLAUDE.md 없음 → exit 0."""
        rc, out, err = _run(_task_payload(), {})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")


class MarkerPresentTest(unittest.TestCase):
    """살아있는 marker → advance() + system-reminder stdout 주입."""

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

    def test_advance_and_emit_reminder(self) -> None:
        ess.start("acme", "redteam-q2")
        rc, out, err = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.company_root)},
        )
        self.assertEqual(rc, 0)
        self.assertIn("<system-reminder>", out)
        self.assertIn("</system-reminder>", out)
        self.assertIn("redteam-q2", out)
        # advance 가 호출되어 step_count 가 2 로 증가
        state = ess.read("acme")
        self.assertIsNotNone(state)
        self.assertEqual(state.step_count_so_far, 2)

    def test_reminder_contains_next_action_label(self) -> None:
        ess.start("acme", "redteam-q2")
        rc, out, _ = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.company_root)},
        )
        # start() 직후 marker: current_step=init, next_action=domain_assessment.
        # advance() 는 동일 step/next_action 유지하고 count 만 증가.
        # 따라서 reminder 에는 enum 라벨 둘 다 포함.
        self.assertIn("domain_assessment", out)
        self.assertIn("ADR-0022", out)

    def test_exhausted_marker_unlinked_no_reminder(self) -> None:
        """step_count 가 max 도달하면 read 가 unlink 후 None → reminder 없음."""
        ess.start("acme", "redteam-q2")
        # marker 를 직접 변조하여 exhausted 만들기 (step_count > max).
        path = ess.marker_path("acme")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["step_count_so_far"] = data["max_step_count"] + 1
        path.write_text(json.dumps(data), encoding="utf-8")

        rc, out, _ = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.company_root)},
        )
        self.assertEqual(rc, 0)
        self.assertNotIn("<system-reminder>", out)
        self.assertFalse(path.exists())  # auto-unlinked


class MalformedMarkerTest(unittest.TestCase):
    """malformed marker → read() 가 auto-unlink + None → reminder 없음."""

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

    def test_malformed_json_unlinked(self) -> None:
        path = ess.marker_path("acme")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not valid json {", encoding="utf-8")

        rc, out, _ = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.company_root)},
        )
        self.assertEqual(rc, 0)
        self.assertNotIn("<system-reminder>", out)
        self.assertFalse(path.exists())

    def test_invalid_next_action_unlinked(self) -> None:
        """enum 위반 next_action 박힌 marker → read() 차단 + unlink, raw 미노출."""
        path = ess.marker_path("acme")
        path.parent.mkdir(parents=True, exist_ok=True)
        bad = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "company": "acme",
            "project": "redteam-q2",
            "current_step": "init",
            "next_action": "rm -rf /",  # raw 인젝션 시도
            "step_count_so_far": 1,
            "max_step_count": 10,
        }
        path.write_text(json.dumps(bad), encoding="utf-8")

        rc, out, _ = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.company_root)},
        )
        self.assertEqual(rc, 0)
        self.assertNotIn("<system-reminder>", out)
        self.assertNotIn("rm -rf", out)  # 절대 LLM context 노출 금지
        self.assertFalse(path.exists())  # read() 가 unlink

    def test_invalid_step_unlinked(self) -> None:
        """enum 위반 step 박힌 marker → read() 차단 + unlink."""
        path = ess.marker_path("acme")
        path.parent.mkdir(parents=True, exist_ok=True)
        bad = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "company": "acme",
            "project": "redteam-q2",
            "current_step": "rogue_step",  # enum 위반
            "next_action": "domain_assessment",
            "step_count_so_far": 1,
            "max_step_count": 10,
        }
        path.write_text(json.dumps(bad), encoding="utf-8")

        rc, out, _ = _run(
            _task_payload(),
            {"LSKUN_SSOT_ROOT": str(self.company_root)},
        )
        self.assertEqual(rc, 0)
        self.assertNotIn("<system-reminder>", out)
        self.assertFalse(path.exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
