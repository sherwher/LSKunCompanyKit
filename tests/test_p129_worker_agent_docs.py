"""ADR-0026 (P129) — persona·command 문서의 dispatch 타입 안내 회귀 가드.

hook 이 옛 ``claude`` 타입을 deny 하므로, 문서가 옛 타입을 안내하면 모든
dispatch 가 한 번씩 거부된 뒤에야 성공한다.
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

DOCS = (
    ROOT / "src" / "lskun_kit" / "templates" / "cpo.md",
    ROOT / "src" / "lskun_kit" / "templates" / "hr-lead.md",
    ROOT / "commands" / "work.md",
    ROOT / "commands" / "external.md",
)


class DispatchTypeGuidanceTests(unittest.TestCase):
    def test_no_doc_instructs_legacy_claude_type(self) -> None:
        for path in DOCS:
            body = path.read_text(encoding="utf-8")
            self.assertNotIn('subagent_type="claude"', body, path.name)

    def test_cpo_and_work_name_both_agents(self) -> None:
        for path in DOCS[0], DOCS[2]:
            body = path.read_text(encoding="utf-8")
            self.assertIn("LSKunCompanyKit:worker", body, path.name)
            self.assertIn("LSKunCompanyKit:hr-lead", body, path.name)

    def test_routing_context_names_both_agents(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            adapter = _init_local(Path(td))
            ctx = build_cpo_routing_context(adapter, user_request="테스트 요청")
        self.assertIn("LSKunCompanyKit:worker", ctx)
        self.assertIn("LSKunCompanyKit:hr-lead", ctx)


if __name__ == "__main__":
    unittest.main()
