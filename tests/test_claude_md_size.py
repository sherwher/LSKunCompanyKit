"""P109-C — CLAUDE.md 크기 회귀 가드.

목적: 본 plugin 의 CLAUDE.md 가 미래에 다시 비대해지면 (47 KB 사고 재발)
즉시 fail 하여 docs/internals/ 로 분리하라는 신호.

기준:
- soft target = 8 KB (정보성, 위반해도 OK 단 경고)
- hard cap = 15 KB (위반 시 fail)

실측 (P109-C 직후): 11.8 KB. 추가 압축 여지 있으나 핵심 정체성·메커니즘
보존을 위해 hard cap 15 KB 로 현실화.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


SOFT_TARGET_BYTES = 8 * 1024
HARD_CAP_BYTES = 15 * 1024


class ClaudeMdSizeTests(unittest.TestCase):
    def test_claude_md_under_hard_cap(self) -> None:
        path = ROOT / "CLAUDE.md"
        self.assertTrue(path.exists(), "CLAUDE.md 가 plugin 루트에 있어야 함")
        size = path.stat().st_size
        self.assertLessEqual(
            size,
            HARD_CAP_BYTES,
            (
                f"CLAUDE.md ({size} bytes) 가 hard cap {HARD_CAP_BYTES} bytes "
                f"({HARD_CAP_BYTES // 1024} KB) 초과. docs/internals/ 로 추가 분리 필요. "
                f"P109-C 정신 — 매 세션 컨텍스트 비용 절감."
            ),
        )
        # soft target 위반은 경고만 (stderr 로)
        if size > SOFT_TARGET_BYTES:
            sys.stderr.write(
                f"⚠️ CLAUDE.md soft target 위반: {size} bytes > "
                f"{SOFT_TARGET_BYTES} bytes ({SOFT_TARGET_BYTES // 1024} KB). "
                f"docs/internals/ 추가 분리 권장.\n"
            )

    def test_internal_docs_referenced(self) -> None:
        """CLAUDE.md 가 docs/internals/ 의 분리된 파일들을 1회 이상 참조해야 함."""
        path = ROOT / "CLAUDE.md"
        content = path.read_text(encoding="utf-8")
        required_refs = (
            "docs/internals/adr-index.md",
            "docs/internals/phase-roadmap.md",
            "docs/internals/forbidden-history.md",
            "docs/internals/directory-structure.md",
        )
        for ref in required_refs:
            self.assertIn(
                ref,
                content,
                f"CLAUDE.md 가 {ref} 참조 누락. P109-C 분리 정합성 위반.",
            )

    def test_internal_docs_exist(self) -> None:
        """참조된 internal docs 파일이 실제로 존재해야 함."""
        for ref in (
            "docs/internals/adr-index.md",
            "docs/internals/phase-roadmap.md",
            "docs/internals/forbidden-history.md",
            "docs/internals/directory-structure.md",
        ):
            path = ROOT / ref
            self.assertTrue(path.exists(), f"분리 docs 파일 누락: {ref}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
