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


class RedteamConstitutionEmphasisTest(unittest.TestCase):
    """destructive 금지가 blockquote + 볼드로 강조되는지."""
    def setUp(self):
        self.text = (ROOT / "templates" / "redteam.md").read_text(encoding="utf-8")

    def test_destructive_in_blockquote(self):
        bq_lines = [l for l in self.text.split("\n") if l.lstrip().startswith(">")]
        bq = "\n".join(bq_lines)
        self.assertTrue(any(kw in bq for kw in ("삭제", "수정", "실행")),
                        "destructive 금지가 blockquote 에 들어있어야 합니다")

    def test_destructive_bolded(self):
        self.assertIn("**", self.text)
        bolds = []
        idx = 0
        while True:
            s = self.text.find("**", idx)
            if s < 0: break
            e = self.text.find("**", s + 2)
            if e < 0: break
            bolds.append(self.text[s+2:e])
            idx = e + 2
        joined = " ".join(bolds)
        self.assertTrue(any(kw in joined for kw in ("삭제", "수정", "실행", "파괴")),
                        "destructive 키워드가 볼드 블록 안에 있어야 합니다")


class CustomerStatisticalGuardTest(unittest.TestCase):
    """간접 통계 표현까지 금지 범위 확장."""
    def setUp(self):
        self.text = (ROOT / "templates" / "customer.md").read_text(encoding="utf-8")

    def test_extended_statistical_terms_listed(self):
        for kw in ("대부분", "일반적으로", "N명 중"):
            self.assertIn(kw, self.text,
                          f"간접 통계 표현 '{kw}' 가 금지 목록에 명시되어야 합니다")


if __name__ == "__main__":
    unittest.main()
