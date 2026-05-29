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

    # --- ADR-0022 (P121) — 자동 시퀀스 본문 강화 ---

    def test_one_turn_completion_directive(self):
        # 한 turn 완수 + 사용자 응답 대기로 turn 종료 금지 명시.
        self.assertIn("한 turn", self.text)
        self.assertIn("사용자 응답을 기다", self.text)

    def test_clear_session_guidance(self):
        # critic B1 — /clear 강제 break 안내 (슬래시 포함).
        self.assertIn("/clear", self.text)

    def test_cancel_subcommand_documented(self):
        self.assertIn("cancel", self.text)
        self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", self.text)

    def test_adr_0022_referenced(self):
        self.assertIn("ADR-0022", self.text)

    def test_start_is_mandatory_first_action(self):
        # critic M1 — marker start() 가 첫 행동으로 강하게 박제 (누락 시 보호 0).
        self.assertIn("external_setup_state.start", self.text)
        self.assertIn("첫 행동", self.text)


if __name__ == "__main__":
    unittest.main()
