"""lskun_kit.persona_injection 단위 테스트 — ADR-0004 §1.

CPO persona 를 사용자 프로젝트 root 의 CLAUDE.md 에 marker 구간으로 inline 박제.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit.persona_injection import (  # noqa: E402
    CLAUDE_MD_FILENAME,
    PERSONA_MARKER_END,
    PERSONA_MARKER_START,
    detect,
    find_marker_span,
    inject,
    render_persona_block,
)


CPO_BODY_SAMPLE = "# cpo\n\n> CPO persona body.\n\n## Mandate\n\n- 라우팅.\n"


class RenderPersonaBlockTests(unittest.TestCase):
    def test_includes_markers_and_body(self) -> None:
        block = render_persona_block("Acme", "이세근", CPO_BODY_SAMPLE)
        self.assertIn(PERSONA_MARKER_START, block)
        self.assertIn(PERSONA_MARKER_END, block)
        self.assertIn("이세근", block)
        self.assertIn("Acme", block)
        self.assertIn("Mandate", block)

    def test_starts_and_ends_with_newline(self) -> None:
        block = render_persona_block("Acme", "이세근", CPO_BODY_SAMPLE)
        self.assertTrue(block.startswith("\n"))
        self.assertTrue(block.endswith("\n"))


class FindMarkerSpanTests(unittest.TestCase):
    def test_returns_none_when_absent(self) -> None:
        self.assertIsNone(find_marker_span("hello world\n"))

    def test_returns_span_when_present(self) -> None:
        block = render_persona_block("Acme", "X", CPO_BODY_SAMPLE)
        text = f"pre\n{block}post\n"
        span = find_marker_span(text)
        self.assertIsNotNone(span)
        assert span is not None
        start, end = span
        self.assertTrue(text[start:end].startswith(PERSONA_MARKER_START))
        self.assertIn(PERSONA_MARKER_END, text[start:end])

    def test_returns_none_when_only_start_present(self) -> None:
        # marker 손상 — start 만 있고 end 없음
        self.assertIsNone(find_marker_span(f"{PERSONA_MARKER_START}\nbody"))


class InjectTests(unittest.TestCase):
    def test_creates_claude_md_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = inject(tmp, "Acme", "이세근", CPO_BODY_SAMPLE)
            self.assertEqual(result.action, "created")
            self.assertFalse(result.had_existing_marker)
            content = (Path(tmp) / CLAUDE_MD_FILENAME).read_text(encoding="utf-8")
            self.assertIn(PERSONA_MARKER_START, content)
            self.assertIn("이세근", content)

    def test_appends_when_existing_without_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = "# 사용자 본문\n\n사용자가 쓴 텍스트.\n"
            (Path(tmp) / CLAUDE_MD_FILENAME).write_text(existing, encoding="utf-8")
            result = inject(tmp, "Acme", "이세근", CPO_BODY_SAMPLE)
            self.assertEqual(result.action, "updated")
            self.assertFalse(result.had_existing_marker)
            content = (Path(tmp) / CLAUDE_MD_FILENAME).read_text(encoding="utf-8")
            # 사용자 본문은 그대로 보존
            self.assertTrue(content.startswith(existing))
            self.assertIn(PERSONA_MARKER_START, content)

    def test_replaces_existing_marker_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # 1차 박제
            inject(tmp, "Acme", "이세근", "first body\n")
            # 2차 박제 — display_name 변경
            result = inject(tmp, "Acme", "김지혜", "second body\n")
            self.assertEqual(result.action, "updated")
            self.assertTrue(result.had_existing_marker)
            content = (Path(tmp) / CLAUDE_MD_FILENAME).read_text(encoding="utf-8")
            self.assertIn("김지혜", content)
            self.assertNotIn("이세근", content)
            self.assertNotIn("first body", content)
            self.assertIn("second body", content)
            # marker 는 여전히 1쌍만
            self.assertEqual(content.count(PERSONA_MARKER_START), 1)
            self.assertEqual(content.count(PERSONA_MARKER_END), 1)

    def test_preserves_user_content_outside_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # 박제 후 사용자가 marker 바깥에 본문 추가
            inject(tmp, "Acme", "이세근", "v1\n")
            path = Path(tmp) / CLAUDE_MD_FILENAME
            current = path.read_text(encoding="utf-8")
            current = current + "\n## 사용자 추가 섹션\n\n사용자 텍스트.\n"
            path.write_text(current, encoding="utf-8")
            # 재박제 — 사용자 섹션 보존
            inject(tmp, "Acme", "이세근", "v2\n")
            new = path.read_text(encoding="utf-8")
            self.assertIn("사용자 추가 섹션", new)
            self.assertIn("사용자 텍스트.", new)
            self.assertIn("v2", new)

    def test_skips_when_project_root_missing(self) -> None:
        # ADR-0004 §1 의 graceful — 비존재 project_root 에서 박제 skip
        result = inject("/nonexistent-path-for-test", "X", "Y", "body")
        self.assertEqual(result.action, "skipped-no-project-root")


class DetectTests(unittest.TestCase):
    def test_returns_false_when_no_claude_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(detect(tmp))

    def test_returns_true_after_inject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inject(tmp, "Acme", "이세근", CPO_BODY_SAMPLE)
            self.assertTrue(detect(tmp))

    def test_returns_false_when_marker_damaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / CLAUDE_MD_FILENAME).write_text(
                f"{PERSONA_MARKER_START}\nbody without end\n",
                encoding="utf-8",
            )
            self.assertFalse(detect(tmp))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
