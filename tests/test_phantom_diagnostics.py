"""유령참조 진단 테스트 (P122, ADR-0023). stdlib unittest 만 사용."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit.phantom_diagnostics import diagnose_phantom  # noqa: E402


def _worker_md(name: str, *, fm_name: str | None = None,
               domain: str = "medical", skills: str | None = None) -> str:
    # fm_name 으로 frontmatter name 을 stem 과 다르게 만들 수 있다 (불일치 fixture).
    actual = fm_name if fm_name is not None else name
    fm = dedent(
        f"""\
        ---
        name: {actual}
        role: {name}
        domain: {domain}
        hired_at: 2026-06-25
        storage_backend: local
        display_name: Test {name}
        """
    )
    if skills is not None:
        fm += f"skills: {skills}\n"
    fm += "---\nJD body\n"
    return fm


class PhantomDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_worker(self, filename_stem: str, **kw) -> None:
        (self.root / "hired" / f"{filename_stem}.md").write_text(
            _worker_md(filename_stem, **kw), encoding="utf-8"
        )

    def test_detects_name_stem_mismatch(self) -> None:
        # 파일명 harin.md 인데 frontmatter name=harlin → 불일치 (치명적).
        self._write_worker("harin", fm_name="harlin")
        result = diagnose_phantom(self.adapter)
        self.assertIn(("harin", "harlin"), result.name_mismatch)
        self.assertTrue(result.has_critical())

    def test_clean_company_no_mismatch(self) -> None:
        self._write_worker("alice")
        result = diagnose_phantom(self.adapter)
        self.assertEqual(result.name_mismatch, [])
        self.assertFalse(result.has_critical())

    def test_detects_orphan_audit(self) -> None:
        # audit 에 hire 기록은 있으나 hired/ 파일 부재 → 고아 audit (경고).
        from lskun_kit import hire_audit
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="ghost",
            role="engineer", domain="medical",
        )
        # ghost.md 는 만들지 않음.
        result = diagnose_phantom(self.adapter)
        self.assertIn("ghost", result.orphan_audit)
        self.assertTrue(result.has_warning())

    def test_file_only_is_info_not_warning(self) -> None:
        # 파일은 있으나 audit 없음 → 정상 (사용자 직접 hire). 경고 아님.
        self._write_worker("alice")
        result = diagnose_phantom(self.adapter)
        self.assertIn("alice", result.file_only)
        self.assertNotIn("alice", result.orphan_audit)

    def test_detects_dangling_skill(self) -> None:
        # skills 선언 토큰이 가리키는 skills/<name>.md 부재 → dangling (경고).
        self._write_worker("alice", skills="hipaa-x")
        # skills/hipaa-x.md 는 만들지 않음.
        result = diagnose_phantom(self.adapter)
        self.assertIn(("alice", "hipaa-x"), result.dangling_skills)
        self.assertTrue(result.has_warning())


if __name__ == "__main__":
    unittest.main()
