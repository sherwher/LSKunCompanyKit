"""ADR-0021 — external doctor 진단 테스트."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external, external_diagnostics, paths  # noqa: E402


class DiagnoseExternalTest(unittest.TestCase):
    def _setup(self, tmp):
        return mock.patch.object(paths.Path, "home", return_value=Path(tmp))

    def test_no_external_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp, self._setup(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            findings = external_diagnostics.diagnose_external("Acme")
            self.assertEqual(findings.issues, [])
            self.assertFalse(findings.has_external)

    def test_detects_external_present(self):
        with tempfile.TemporaryDirectory() as tmp, self._setup(tmp):
            d = external.external_root("Acme", "proj") / "redteam"
            d.mkdir(parents=True)
            (d / "critic.md").write_text("---\nkind: redteam\nproject: proj\n---\nbody")
            external.brief_path("Acme", "proj").write_text("# brief")
            findings = external_diagnostics.diagnose_external("Acme")
            self.assertTrue(findings.has_external)
            self.assertEqual(findings.issues, [])

    def test_missing_brief_flagged(self):
        with tempfile.TemporaryDirectory() as tmp, self._setup(tmp):
            d = external.external_root("Acme", "proj") / "redteam"
            d.mkdir(parents=True)
            (d / "critic.md").write_text("---\nkind: redteam\nproject: proj\n---\nx")
            findings = external_diagnostics.diagnose_external("Acme")
            self.assertTrue(any("brief" in i for i in findings.issues))

    def test_cross_project_leak_flagged(self):
        with tempfile.TemporaryDirectory() as tmp, self._setup(tmp):
            d = external.external_root("Acme", "proj") / "redteam"
            d.mkdir(parents=True)
            (d / "critic.md").write_text("---\nkind: redteam\nproject: OTHER\n---\nx")
            external.brief_path("Acme", "proj").write_text("# brief")
            findings = external_diagnostics.diagnose_external("Acme")
            self.assertTrue(any("project" in i.lower() for i in findings.issues))

    def test_unreadable_persona_md_is_graceful(self):
        """파일 read 실패(권한 X 등)는 크래시 없이 graceful 진단."""
        with tempfile.TemporaryDirectory() as tmp, self._setup(tmp):
            d = external.external_root("Acme", "proj") / "redteam"
            d.mkdir(parents=True)
            (d / "critic.md").write_text("---\nproject: proj\n---\nx")
            external.brief_path("Acme", "proj").write_text("# brief")
            with mock.patch.object(Path, "read_text", side_effect=OSError("perm denied")):
                findings = external_diagnostics.diagnose_external("Acme")
            self.assertTrue(findings.has_external)
            # 권한 거부된 파일은 leak 검사를 skip 하므로 issues 에 추가 없음
            # (brief 가 있으므로 brief 누락 issue 도 없음)
            self.assertEqual(findings.issues, [])


if __name__ == "__main__":
    unittest.main()
