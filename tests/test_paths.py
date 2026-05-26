"""lskun_kit.paths 단위 테스트 — ADR-0015 결정 1-A.

본 모듈은 회사 자원의 물리적 위치를 결정하는 유일한 단일 진입점이다.
호출자 (init / hooks / cli_org / sync) 의 hardcode 회귀를 방지하기 위해
강한 invariant 를 검증한다.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import paths  # noqa: E402


class LskunCompaniesRootTests(unittest.TestCase):
    """ADR-0015 결정 1-A — Local SSOT 단일 위치."""

    def test_root_is_under_home(self) -> None:
        root = paths.lskun_companies_root()
        # 절대경로 + 홈 디렉토리 하위
        self.assertTrue(root.is_absolute())
        self.assertEqual(root.parent, Path.home())
        self.assertEqual(root.name, paths.LSKUN_COMPANIES_DIRNAME)

    def test_dirname_constant_locked(self) -> None:
        """ADR-0015 결정 4 의 권한 박제와 결합 — 디렉토리명 변경은 금지."""
        self.assertEqual(paths.LSKUN_COMPANIES_DIRNAME, ".lskun-companies")

    def test_root_does_not_create_directory(self) -> None:
        """호출만으로 디렉토리 생성 금지 (read-only 함수)."""
        with tempfile.TemporaryDirectory() as fake_home:
            with mock.patch("lskun_kit.paths.Path.home",
                            return_value=Path(fake_home)):
                root = paths.lskun_companies_root()
                self.assertFalse(root.exists())


class CompanyRootTests(unittest.TestCase):
    def test_returns_subdir_of_root(self) -> None:
        co = paths.company_root("LSKun")
        self.assertEqual(co.parent, paths.lskun_companies_root())
        self.assertEqual(co.name, "LSKun")

    def test_validates_name(self) -> None:
        for bad in ("", ".", "..", "a/b", ".backups", "lskun ", " LSKun",
                    "../escape", "LSKun\x00", "한글이름"):
            with self.assertRaises(ValueError, msg=f"{bad!r}"):
                paths.company_root(bad)

    def test_accepts_kebab_underscore_dot_digits(self) -> None:
        for good in ("LSKun", "lskun-co", "LSKun_v2", "LSKun.fork",
                     "Acme123", "a", "1company"):
            try:
                paths.company_root(good)
            except ValueError as e:
                self.fail(f"{good!r} should be accepted, got {e}")


class BackupRootTests(unittest.TestCase):
    """결정 5-E — backup 통합 위치."""

    def test_under_dot_backups_subdir(self) -> None:
        bk = paths.backup_root("LSKun")
        self.assertEqual(bk.parent.name, paths.BACKUPS_DIRNAME)
        self.assertEqual(bk.parent.parent, paths.lskun_companies_root())
        self.assertEqual(bk.name, "LSKun")

    def test_backup_root_is_outside_company_root(self) -> None:
        """결정 5-E 의 핵심 — backup 이 회사 SSOT 디렉토리를 오염시키지 않음."""
        co = paths.company_root("LSKun")
        bk = paths.backup_root("LSKun")
        # backup_root 가 company_root 안에 있으면 안 됨
        self.assertNotIn(co, bk.parents)
        self.assertNotEqual(bk.parent, co)


class ValidateCompanyNameTests(unittest.TestCase):
    def test_rejects_backups_reserved(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            paths.validate_company_name(".backups")
        # 예약어 메시지 포함
        self.assertIn("reserved", str(ctx.exception).lower() + "  ")

    def test_rejects_overlong(self) -> None:
        with self.assertRaises(ValueError):
            paths.validate_company_name("a" * 200)


class ListCompaniesTests(unittest.TestCase):
    def test_returns_empty_when_root_missing(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            with mock.patch("lskun_kit.paths.Path.home",
                            return_value=Path(fake_home)):
                self.assertEqual(paths.list_companies(), [])

    def test_lists_subdirectories_sorted_and_excludes_dotprefix(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            with mock.patch("lskun_kit.paths.Path.home",
                            return_value=Path(fake_home)):
                root = paths.lskun_companies_root()
                root.mkdir()
                (root / "LSKun").mkdir()
                (root / "Acme").mkdir()
                (root / ".backups").mkdir()  # 제외
                (root / ".cache").mkdir()    # 제외 (사용자 메타)
                (root / "not-a-dir.txt").write_text("x", encoding="utf-8")
                self.assertEqual(paths.list_companies(), ["Acme", "LSKun"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
