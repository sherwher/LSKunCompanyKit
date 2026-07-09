"""CLAUDE.md ↔ ADR 정합성 회귀 가드.

배경: ADR-0014 (Reflection 폐기, 2026-05-22) 이후에도 CLAUDE.md §2.2 다이어그램
("reflection 후보 3섹션") / §9 CPO 책임 ("Reflection 자동 박제 → reflection.record")
잔재가 0.31.0 까지 살아남아 헌법 내부 모순 상태였다 (2026-07-09 발견·정정).

본 테스트는 폐기된 메커니즘의 표현이 CLAUDE.md 에 "현행 지시" 로 재등장하는
회귀를 차단한다. 취소선 (~~...~~) 으로 감싼 역사 언급은 허용.

추가: §1 버전 필드에 이전 버전 서술을 누적하는 패턴 (P124 까지의 비대화 원인,
CLAUDE.md 13.9 KB 도달) 재발 차단 — 버전별 상세의 SSOT 는 CHANGELOG.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _strip_strikethrough(text: str) -> str:
    """취소선 (~~...~~) 구간 제거 — 폐기 역사 언급은 허용 대상."""
    return re.sub(r"~~.+?~~", "", text, flags=re.DOTALL)


class ClaudeMdConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        cls.active = _strip_strikethrough(cls.content)

    def test_no_active_reflection_record(self) -> None:
        """ADR-0014 — reflection.record 는 취소선 밖 (현행 지시) 으로 재등장 금지."""
        self.assertNotIn(
            "reflection.record",
            self.active,
            "CLAUDE.md 가 폐기된 reflection.record 를 현행 지시로 언급. "
            "ADR-0014 위반 — 취소선 역사 언급만 허용.",
        )

    def test_no_active_reflection_candidate_section(self) -> None:
        """ADR-0014 — 워커 보고는 2섹션. 'reflection 후보' 섹션 재등장 금지."""
        self.assertNotIn(
            "reflection 후보",
            self.active,
            "CLAUDE.md 가 폐기된 'reflection 후보' 보고 섹션을 언급. "
            "ADR-0014/ADR-0024 — 보고는 작업 결과 + 자가 평가 2섹션.",
        )

    def test_version_field_no_previous_version_accumulation(self) -> None:
        """§1 버전 필드에 '**이전 (0.X.Y)**' 서술 누적 금지 — CHANGELOG 가 SSOT."""
        self.assertIsNone(
            re.search(r"\*\*이전 \(\d+\.\d+\.\d+\)\*\*", self.content),
            "CLAUDE.md §1 버전 필드에 이전 버전 서술이 누적됨. "
            "버전별 상세는 CHANGELOG 로 — CLAUDE.md 크기 가드 (P109-C 정신).",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
