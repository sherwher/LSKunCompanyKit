"""ADR-0021 — 외주 template 헌법 박제 테스트."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class RedteamTemplateTest(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "templates" / "redteam.md").read_text(encoding="utf-8")

    def test_destructive_prohibition_present(self):
        # security H2 — 텍스트 비평만, 파괴 행위 금지 헌법.
        self.assertIn("비평", self.text)
        for kw in ("삭제", "실행", "수정"):
            self.assertIn(kw, self.text)

    def test_opinion_only_not_decision(self):
        self.assertIn("의견", self.text)


class CustomerTemplateTest(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "templates" / "customer.md").read_text(encoding="utf-8")

    def test_no_majority_framing(self):
        # critic M5 — 다수결/퍼센트 금지 헌법.
        self.assertIn("다수결", self.text)

    def test_persona_lens(self):
        self.assertIn("페르소나", self.text)


if __name__ == "__main__":
    unittest.main()
