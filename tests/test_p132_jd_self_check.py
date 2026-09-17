"""P132 — HR Lead JD 자가 점검 회귀 가드 (ADR-0024 보강).

점검은 persona 판단이다. plugin core 가 JD 를 검증하는 코드는 ADR-0011 이 금지한다.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HR_TEMPLATE = ROOT / "src" / "lskun_kit" / "templates" / "hr-lead.md"
SRC = ROOT / "src" / "lskun_kit"


class JdSelfCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.body = HR_TEMPLATE.read_text(encoding="utf-8")

    def test_five_questions_present(self) -> None:
        self.assertIn("JD 자가 점검 (P132)", self.body)
        for item in ("도메인 특정성", "함정의 구체성", "한계 명시", "keywords 정합", "정적 서술"):
            self.assertIn(f"**{item}**", self.body)

    def test_states_core_does_not_validate_jd(self) -> None:
        self.assertIn("plugin core 는 JD 를 검증하지 않는다", self.body)

    def test_no_jd_lint_module_in_core(self) -> None:
        """ADR-0011 — JD schema · 검증 · 측정 코드 금지."""
        names = {p.stem for p in SRC.rglob("*.py")}
        for banned in ("jd_lint", "jd_diagnostics", "jd_quality", "jd_metrics"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
