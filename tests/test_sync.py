"""lskun_kit.sync 단위 테스트 — ADR-0015 결정 5.

테스트 격리: ``Path.home()`` 를 tempdir 로 mock + ``today_stamp`` 인자로
timestamp 결정론적 주입. 사용자 실제 홈 / vault 오염 0.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import sync  # noqa: E402
from lskun_kit.errors import ConfirmRequired  # noqa: E402
from lskun_kit.paths import backup_root, company_root  # noqa: E402


def _patched_home(fake_home: str):
    return mock.patch("lskun_kit.paths.Path.home",
                      return_value=Path(fake_home))


def _make_company_files(root: Path) -> None:
    """가상 회사 자원 박제 — company.md + hired/cpo.md + .audit/ 1줄."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "company.md").write_text(
        "---\nname: LSKun\nfounded: 2026-05-22\n---\n# LSKun\n",
        encoding="utf-8",
    )
    (root / "hired").mkdir()
    (root / "hired" / "cpo.md").write_text("# cpo body\n", encoding="utf-8")
    (root / ".audit").mkdir()
    (root / ".audit" / "decisions.jsonl").write_text(
        '{"request_id": "1", "verdict": "approved"}\n', encoding="utf-8"
    )


class SyncInRequiresConfirmTests(unittest.TestCase):
    def test_raises_confirm_required_when_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                src = Path(vault) / "LSKun"
                _make_company_files(src)
                # target 기존 박제
                _make_company_files(company_root("LSKun"))

                with self.assertRaises(ConfirmRequired) as ctx:
                    sync.sync_in("LSKun", src)
                err = ctx.exception
                self.assertEqual(err.kind, "sync_overwrite")
                self.assertEqual(err.context.get("direction"), "in")
                self.assertEqual(err.context.get("company_name"), "LSKun")
                self.assertTrue(err.context.get("target_exists"))
                self.assertIn("덮어쓰여집니다", err.prompt)

    def test_raises_confirm_required_when_target_absent(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                src = Path(vault) / "LSKun"
                _make_company_files(src)
                # target 부재
                with self.assertRaises(ConfirmRequired) as ctx:
                    sync.sync_in("LSKun", src)
                err = ctx.exception
                self.assertFalse(err.context.get("target_exists"))
                self.assertIn("신규 생성", err.prompt)


class SyncInWritesAndBackupsTests(unittest.TestCase):
    def test_creates_new_target_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                src = Path(vault) / "LSKun"
                _make_company_files(src)

                result = sync.sync_in(
                    "LSKun", src, confirmed=True,
                    today_stamp="20260522-100000",
                )
                self.assertEqual(result.direction, "in")
                self.assertEqual(result.company_name, "LSKun")
                self.assertIsNone(result.backup_path)
                self.assertGreater(result.files_copied, 0)

                # target 의 company.md 가 source 와 동일
                target_co = company_root("LSKun") / "company.md"
                self.assertTrue(target_co.exists())
                self.assertIn("LSKun", target_co.read_text(encoding="utf-8"))

    def test_backs_up_and_overwrites_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                src = Path(vault) / "LSKun"
                _make_company_files(src)
                # target 기존 — distinguishable marker 박제
                co_root = company_root("LSKun")
                _make_company_files(co_root)
                (co_root / "OLD-MARKER").write_text("old", encoding="utf-8")

                result = sync.sync_in(
                    "LSKun", src, confirmed=True,
                    today_stamp="20260522-100000",
                )
                self.assertIsNotNone(result.backup_path)
                # 백업이 ~/.lskun-companies/.backups/<name>/<ts>/ 하위
                expected_bk = backup_root("LSKun") / "20260522-100000"
                self.assertEqual(result.backup_path, expected_bk)
                self.assertTrue((expected_bk / "OLD-MARKER").exists())
                # 새 target 에는 OLD-MARKER 가 없고 source 의 파일만
                self.assertFalse((co_root / "OLD-MARKER").exists())
                self.assertTrue((co_root / "company.md").exists())


class SyncInValidationTests(unittest.TestCase):
    def test_rejects_invalid_company_name(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            with _patched_home(fake_home):
                with self.assertRaises(ValueError):
                    sync.sync_in("..", "/tmp/x", confirmed=True)

    def test_rejects_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            with _patched_home(fake_home):
                with self.assertRaises(ValueError) as ctx:
                    sync.sync_in("LSKun", "/nonexistent/path",
                                 confirmed=True)
                self.assertIn("does not exist", str(ctx.exception))


class SyncOutRequiresConfirmTests(unittest.TestCase):
    def test_raises_confirm_required(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                _make_company_files(company_root("LSKun"))
                tgt = Path(vault) / "LSKun-mirror"
                _make_company_files(tgt)
                with self.assertRaises(ConfirmRequired) as ctx:
                    sync.sync_out("LSKun", tgt)
                err = ctx.exception
                self.assertEqual(err.kind, "sync_overwrite")
                self.assertEqual(err.context.get("direction"), "out")
                self.assertTrue(err.context.get("target_exists"))


class SyncOutWritesAndBackupsTests(unittest.TestCase):
    def test_creates_new_target_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                _make_company_files(company_root("LSKun"))
                tgt = Path(vault) / "LSKun-mirror"
                result = sync.sync_out(
                    "LSKun", tgt, confirmed=True,
                    today_stamp="20260522-100000",
                )
                self.assertEqual(result.direction, "out")
                self.assertIsNone(result.backup_path)
                self.assertGreater(result.files_copied, 0)
                self.assertTrue((tgt / "company.md").exists())

    def test_backs_up_existing_target_to_sibling(self) -> None:
        """결정 5-B — target 백업은 target 측 sibling 에."""
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                _make_company_files(company_root("LSKun"))
                tgt = (Path(vault) / "LSKun-mirror").resolve()
                _make_company_files(tgt)
                (tgt / "OLD-MARKER").write_text("old", encoding="utf-8")

                result = sync.sync_out(
                    "LSKun", tgt, confirmed=True,
                    today_stamp="20260522-100000",
                )
                self.assertIsNotNone(result.backup_path)
                # 백업은 target 의 sibling (양쪽 모두 resolve 된 절대경로)
                self.assertEqual(result.backup_path.parent, tgt.parent)
                self.assertIn("lskun-backup-20260522-100000",
                              result.backup_path.name)
                self.assertTrue((result.backup_path / "OLD-MARKER").exists())
                # 새 target 에 OLD-MARKER 없음
                self.assertFalse((tgt / "OLD-MARKER").exists())


class SyncOutValidationTests(unittest.TestCase):
    def test_rejects_missing_local_ssot(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault:
            with _patched_home(fake_home):
                # local SSOT 부재
                with self.assertRaises(ValueError) as ctx:
                    sync.sync_out("LSKun", Path(vault) / "out",
                                  confirmed=True)
                self.assertIn("does not exist", str(ctx.exception))
                self.assertIn("/lskun-kit:init", str(ctx.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
