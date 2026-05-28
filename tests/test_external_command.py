"""ADR-0021 — /lskun-kit:external command 구조 검증."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExternalCommandTest(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "commands" / "external.md").read_text(encoding="utf-8")

    def test_has_frontmatter(self):
        self.assertTrue(self.text.startswith("---"))

    def test_dispatch_after_session_clear(self):
        # B1 — 세션 clear 후 dispatch 명시.
        self.assertIn("clear", self.text)

    def test_claude_subagent(self):
        self.assertIn('subagent_type="claude"', self.text)

    def test_max_customers_guard(self):
        self.assertIn("7명", self.text)

    def test_untrusted_isolation(self):
        # security H1 — build_external_context 또는 untrusted fence 언급.
        self.assertTrue(
            "build_external_context" in self.text or "untrusted fence" in self.text
        )

    def test_audit_onboard(self):
        # Task 5 — record_external_onboard 또는 audit 언급.
        self.assertTrue(
            "record_external_onboard" in self.text or "audit" in self.text
        )

    def test_no_majority_vote(self):
        # 다수결 금지 (ADR-0021).
        self.assertIn("다수결", self.text)


if __name__ == "__main__":
    unittest.main()
