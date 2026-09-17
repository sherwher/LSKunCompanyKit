"""ADR-0027 (P130) — 결재 기록 절차 안내 회귀 가드.

persona 가 옛 inline Python 방식을 다시 안내하면 기록 마찰이 되살아나
빙의 건 누락·JSONL 손기록이 재발한다.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit.routing import build_cpo_routing_context  # noqa: E402

from test_delegation_gate import _init_local  # noqa: E402

CPO_TEMPLATE = ROOT / "src" / "lskun_kit" / "templates" / "cpo.md"
WORK_CMD = ROOT / "commands" / "work.md"


class ApprovalLoopGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.body = CPO_TEMPLATE.read_text(encoding="utf-8")

    def test_entrypoint_one_liner_for_both_paths(self) -> None:
        self.assertIn("lskun-audit record --worker", self.body)
        self.assertIn("--embody", self.body)

    def test_inline_python_recipe_removed(self) -> None:
        self.assertNotIn("audit.record(adapter, audit.AuditEntry(", self.body)
        self.assertNotIn("audit.new_request_id()", self.body)

    def test_hand_writing_forbidden(self) -> None:
        self.assertIn("직접 고치지 않는다", self.body)

    def test_work_command_and_routing_context(self) -> None:
        self.assertIn("lskun-audit record", WORK_CMD.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            adapter = _init_local(Path(td))
            ctx = build_cpo_routing_context(adapter, user_request="테스트 요청")
        self.assertIn("lskun-audit record", ctx)
        self.assertIn("--embody", ctx)


if __name__ == "__main__":
    unittest.main()
