"""P76 reflection 입력 방식 재설계 테스트.

- record_from_report(): 워커 보고에서 자동 파싱
- HistoryEntry 의 outcome + request_id + 길이 가드
- post_tool_use hook reminder 동작
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lskun_kit import reflection
from lskun_kit.adapters.local import LocalAdapter
from lskun_kit.models import HISTORY_FIELD_MAX_LEN, HistoryEntry


_REPORT_OK = """\
## 작업 결과
- 변경사항: README 갱신

## first-pass 자가 점수
85%

## reflection 후보
- topic: docs
- pattern: readme-update
- 다음에 같은 패턴이 또 발생하면 인용할만한 한 줄: README 는 plain markdown 유지.
"""


class HistoryEntryFormatTests(unittest.TestCase):

    def test_render_with_request_id_includes_outcome_and_req(self):
        e = HistoryEntry(
            date=date(2026, 5, 21),
            project="LSKun",
            topic="docs",
            pattern="readme-update",
            first_pass_score=85,
            outcome="approved",
            request_id="abcdef0123456789abcdef0123456789",
        )
        line = e.render()
        self.assertIn("[approved]", line)
        self.assertIn("req:abcdef01", line)
        self.assertNotIn("req:abcdef0123", line)  # 8자만

    def test_render_legacy_format_when_no_request_id(self):
        e = HistoryEntry(
            date=date(2026, 5, 21),
            project="LSKun",
            topic="docs",
            pattern="x",
            first_pass_score=85,
        )
        line = e.render()
        self.assertNotIn("req:", line)
        self.assertNotIn("[approved]", line)


class RecordFromReportTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        self.root.mkdir(parents=True)
        (self.root / "company.md").write_text(
            "---\nname: TestCo\ndomain: test\n---\n", encoding="utf-8"
        )
        (self.root / "hired").mkdir()
        (self.root / "hired" / "alice.md").write_text(
            "---\nname: alice\nrole: dev\ndomain: tech\nhired_at: 2026-05-21\n"
            "storage_backend: local\ndisplay_name: Alice\n---\n\n"
            "## Project History\n\n_(empty)_\n",
            encoding="utf-8",
        )
        self.adapter = LocalAdapter(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parses_and_appends(self):
        entry = reflection.record_from_report(
            self.adapter, "alice",
            project="LSKun", report_md=_REPORT_OK,
            request_id="deadbeef00000000",
        )
        self.assertEqual(entry.topic, "docs")
        self.assertEqual(entry.pattern, "readme-update")
        self.assertEqual(entry.first_pass_score, 85)
        self.assertEqual(entry.outcome, "approved")
        body = (self.root / "hired" / "alice.md").read_text()
        self.assertIn("req:deadbeef", body)
        self.assertIn("[approved]", body)

    def test_missing_section_raises(self):
        with self.assertRaises(reflection.ReportParseError):
            reflection.record_from_report(
                self.adapter, "alice",
                project="LSKun", report_md="random text without sections",
                request_id="r0",
            )

    def test_topic_too_long_raises(self):
        report = _REPORT_OK.replace("topic: docs", f"topic: {'x' * 200}")
        with self.assertRaises(ValueError):
            reflection.record_from_report(
                self.adapter, "alice",
                project="LSKun", report_md=report, request_id="r1",
            )

    def test_outcome_invalid_raises(self):
        with self.assertRaises(ValueError):
            reflection.record_from_report(
                self.adapter, "alice",
                project="LSKun", report_md=_REPORT_OK,
                request_id="r2", outcome="totally-wrong",
            )

    def test_missing_request_id_raises(self):
        with self.assertRaises(ValueError):
            reflection.record_from_report(
                self.adapter, "alice",
                project="LSKun", report_md=_REPORT_OK,
                request_id="",
            )


class LegacyRecordValidationTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        self.root.mkdir()
        (self.root / "company.md").write_text(
            "---\nname: TestCo\ndomain: test\n---\n", encoding="utf-8"
        )
        (self.root / "hired").mkdir()
        (self.root / "hired" / "bob.md").write_text(
            "---\nname: bob\nrole: dev\ndomain: tech\nhired_at: 2026-05-21\n"
            "storage_backend: local\ndisplay_name: Bob\n---\n\n## Project History\n",
            encoding="utf-8",
        )
        self.adapter = LocalAdapter(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_long_topic_rejected_even_in_legacy(self):
        with self.assertRaises(ValueError):
            reflection.record(
                self.adapter, "bob",
                project="LSKun",
                topic="x" * (HISTORY_FIELD_MAX_LEN + 1),
                pattern="ok",
                first_pass_score=80,
            )

    def test_newline_rejected(self):
        with self.assertRaises(ValueError):
            reflection.record(
                self.adapter, "bob",
                project="LSKun",
                topic="ok\nbad",
                pattern="ok",
                first_pass_score=80,
            )


class PostToolUseHookTests(unittest.TestCase):
    """post_tool_use hook 의 reminder 출력 검증."""

    HOOK = (
        Path(__file__).resolve().parent.parent
        / "src" / "lskun_kit" / "hooks" / "post_tool_use.py"
    )

    def _run(self, payload: dict, env_extra: dict | None = None) -> tuple[int, str]:
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        proc = subprocess.run(
            [sys.executable, str(self.HOOK)],
            input=json.dumps(payload),
            capture_output=True, text=True, env=env, timeout=10,
        )
        return proc.returncode, proc.stdout

    def test_emits_reminder_for_task_tool(self):
        rc, out = self._run({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "executor", "description": "build foo"},
        })
        self.assertEqual(rc, 0)
        self.assertIn("REFLECTION 박제 필수", out)
        self.assertIn("executor", out)

    def test_ignores_non_task_tool(self):
        rc, out = self._run({"tool_name": "Bash", "tool_input": {}})
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")

    def test_env_disables_reminder(self):
        rc, out = self._run(
            {"tool_name": "Task", "tool_input": {"subagent_type": "x"}},
            env_extra={"LSKUN_SKIP_REFLECTION_REMINDER": "1"},
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")


if __name__ == "__main__":
    unittest.main()
