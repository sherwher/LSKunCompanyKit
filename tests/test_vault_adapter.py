"""VaultAdapter 단위 테스트.

stdlib unittest 만 사용한다.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import (  # noqa: E402
    SSOTContaminationError,
    VaultAdapter,
    VaultCompanyNotFoundError,
    list_companies,
)


WORKER_MD = dedent(
    """\
    ---
    name: alice
    role: backend-engineer
    domain: payments
    hired_at: 2026-05-15
    storage_backend: vault
    display_name: Alice Park
    ---

    # alice

    ## Project History

    - 2026-05-10 / payment-svc / idempotency / stripe-key-as-idem / first-pass 92%
    """
)

COMPANY_MD = dedent(
    """\
    ---
    name: LSKun
    founded: 2026-05-15
    ---

    # LSKun
    """
)


class VaultAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        # 두 회사를 vault 안에 만들어 둔다
        for company in ("LSKun", "Acme"):
            base = self.vault / "03_Companies" / company / "hired"
            base.mkdir(parents=True)
            (base / "alice.md").write_text(WORKER_MD, encoding="utf-8")
            (self.vault / "03_Companies" / company / "company.md").write_text(
                COMPANY_MD.replace("LSKun", company), encoding="utf-8"
            )
        # vault 가 가질 수 있는 다른 잡 디렉토리
        (self.vault / "02_Projects").mkdir()
        (self.vault / "03_Companies" / ".obsidian").mkdir()
        self.adapter = VaultAdapter(self.vault, "LSKun")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_resolves_company_root(self) -> None:
        self.assertEqual(
            self.adapter.root, self.vault / "03_Companies" / "LSKun"
        )
        self.assertEqual(self.adapter.company, "LSKun")
        self.assertEqual(self.adapter.vault, self.vault)

    def test_read_worker_uses_shared_logic(self) -> None:
        worker = self.adapter.read_worker("alice")
        self.assertEqual(worker.name, "alice")
        self.assertEqual(worker.storage_backend, "vault")

    # test_append_history_writes_under_company — ADR-0014 reflection 폐기로 삭제

    def test_read_company_metadata(self) -> None:
        company = self.adapter.read_company()
        self.assertEqual(company.name, "LSKun")

    def test_missing_company_raises_with_available_list(self) -> None:
        with self.assertRaises(VaultCompanyNotFoundError) as ctx:
            VaultAdapter(self.vault, "Unknown")
        msg = str(ctx.exception)
        self.assertIn("Unknown", msg)
        self.assertIn("LSKun", msg)
        self.assertIn("Acme", msg)

    def test_missing_companies_directory_raises(self) -> None:
        empty = tempfile.TemporaryDirectory()
        try:
            with self.assertRaises(VaultCompanyNotFoundError):
                VaultAdapter(empty.name, "LSKun")
        finally:
            empty.cleanup()

    def test_invalid_company_name_raises(self) -> None:
        for bad in ("", "../escape", ".", ".."):
            with self.assertRaises(ValueError):
                VaultAdapter(self.vault, bad)

    def test_developer_ssot_path_rejected(self) -> None:
        # vault 자체가 LSKunCompanyKit 개발자 SSOT 경로 안에 있는 경우
        dev_path = (
            Path(self.tmp.name)
            / "obsidian-vault"
            / "02_Projects"
            / "LSKunCompanyKit"
        )
        (dev_path / "03_Companies" / "LSKun" / "hired").mkdir(parents=True)
        (dev_path / "03_Companies" / "LSKun" / "company.md").write_text(
            COMPANY_MD, encoding="utf-8"
        )
        with self.assertRaises(SSOTContaminationError):
            VaultAdapter(dev_path, "LSKun")


class ListCompaniesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        for company in ("Zeta", "Alpha", "Beta"):
            (self.vault / "03_Companies" / company).mkdir(parents=True)
        # 점-prefix 는 제외되어야 함
        (self.vault / "03_Companies" / ".obsidian").mkdir()
        # 파일은 회사가 아님
        (self.vault / "03_Companies" / "README.md").write_text("x", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_returns_sorted_visible_directories(self) -> None:
        self.assertEqual(list_companies(self.vault), ["Alpha", "Beta", "Zeta"])

    def test_missing_companies_dir_returns_empty(self) -> None:
        empty = tempfile.TemporaryDirectory()
        try:
            self.assertEqual(list_companies(empty.name), [])
        finally:
            empty.cleanup()


if __name__ == "__main__":
    unittest.main()
