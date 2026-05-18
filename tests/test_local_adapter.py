"""LocalAdapter 단위 테스트.

stdlib unittest 만 사용한다. 외부 의존성 없음.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from textwrap import dedent

# repo root/src 를 sys.path 에 추가
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import (  # noqa: E402
    Company,
    HistoryEntry,
    InvalidWorkerSchemaError,
    LocalAdapter,
    SSOTContaminationError,
    Worker,
    WorkerNotFoundError,
)
from lskun_kit.adapters.local import HISTORY_HEADING, _append_history_line  # noqa: E402


WORKER_MD = dedent(
    """\
    ---
    name: alice
    role: backend-engineer
    domain: payments
    hired_at: 2026-05-15
    storage_backend: local
    display_name: Alice Park
    specialty: payments
    ---

    # alice

    ## Project History

    - 2026-05-10 / payment-svc / idempotency / stripe-key-as-idem / first-pass 92%
    """
)


COMPANY_MD = dedent(
    """\
    ---
    name: Acme Corp
    founded: 2026-05-15
    ---

    # Acme Corp

    AI 직원이 자라는 회사.
    """
)


class LocalAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        (self.root / "hired" / "alice.md").write_text(WORKER_MD, encoding="utf-8")
        (self.root / "company.md").write_text(COMPANY_MD, encoding="utf-8")
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # ---- read_worker ----

    def test_read_worker_parses_required_fields(self) -> None:
        worker = self.adapter.read_worker("alice")
        self.assertIsInstance(worker, Worker)
        self.assertEqual(worker.name, "alice")
        self.assertEqual(worker.role, "backend-engineer")
        self.assertEqual(worker.domain, "payments")
        self.assertEqual(worker.hired_at, date(2026, 5, 15))
        self.assertEqual(worker.storage_backend, "local")
        self.assertEqual(worker.display_name, "Alice Park")
        self.assertIsNone(worker.model)  # frontmatter 에 model 키 없으면 None
        self.assertEqual(worker.extra.get("specialty"), "payments")
        self.assertIn("## Project History", worker.body)

    def test_read_worker_missing_raises(self) -> None:
        with self.assertRaises(WorkerNotFoundError):
            self.adapter.read_worker("ghost")

    def test_read_worker_missing_required_field_raises(self) -> None:
        broken = dedent(
            """\
            ---
            name: bob
            role: pm
            ---

            # bob
            """
        )
        (self.root / "hired" / "bob.md").write_text(broken, encoding="utf-8")
        with self.assertRaises(InvalidWorkerSchemaError) as ctx:
            self.adapter.read_worker("bob")
        self.assertIn("domain", str(ctx.exception))
        self.assertIn("hired_at", str(ctx.exception))
        self.assertIn("storage_backend", str(ctx.exception))
        self.assertIn("display_name", str(ctx.exception))

    def test_read_worker_rejects_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            self.adapter.read_worker("../escape")

    # ---- append_history ----

    def test_append_history_adds_line_at_end_of_section(self) -> None:
        entry = HistoryEntry(
            date=date(2026, 5, 15),
            project="music-pay",
            topic="refund-flow",
            pattern="saga",
            first_pass_score=88,
        )
        self.adapter.append_history("alice", entry)
        text = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        self.assertIn(entry.render(), text)
        # 기존 라인도 유지
        self.assertIn("stripe-key-as-idem", text)
        # 순서 검증: 기존 라인이 새 라인보다 위에 있어야 함
        self.assertLess(
            text.index("stripe-key-as-idem"), text.index("music-pay")
        )

    def test_append_history_creates_section_when_absent(self) -> None:
        skinny = dedent(
            """\
            ---
            name: carol
            role: designer
            domain: meta
            hired_at: 2026-05-15
            storage_backend: local
            display_name: Carol Kim
            ---

            # carol
            """
        )
        (self.root / "hired" / "carol.md").write_text(skinny, encoding="utf-8")
        entry = HistoryEntry(
            date=date(2026, 5, 15),
            project="brand",
            topic="logo",
            pattern="iterative",
            first_pass_score=70,
        )
        self.adapter.append_history("carol", entry)
        text = (self.root / "hired" / "carol.md").read_text(encoding="utf-8")
        self.assertIn(HISTORY_HEADING, text)
        self.assertIn(entry.render(), text)

    def test_append_history_missing_worker_raises(self) -> None:
        entry = HistoryEntry(date(2026, 5, 15), "p", "t", "x", 1)
        with self.assertRaises(WorkerNotFoundError):
            self.adapter.append_history("ghost", entry)

    # ---- list_workers ----

    def test_list_workers_sorted(self) -> None:
        (self.root / "hired" / "bob.md").write_text(
            WORKER_MD.replace("alice", "bob"), encoding="utf-8"
        )
        self.assertEqual(self.adapter.list_workers(), ["alice", "bob"])

    def test_list_workers_empty_when_no_hired_dir(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        try:
            adapter = LocalAdapter(Path(tmp.name) / ".company-empty")
            self.assertEqual(adapter.list_workers(), [])
        finally:
            tmp.cleanup()

    # ---- read_company ----

    def test_read_company_parses_metadata(self) -> None:
        company = self.adapter.read_company()
        self.assertIsInstance(company, Company)
        self.assertEqual(company.name, "Acme Corp")
        self.assertIn("AI 직원이 자라는 회사", company.body)
        self.assertEqual(company.extra.get("founded"), "2026-05-15")

    def test_read_company_missing_returns_blank(self) -> None:
        (self.root / "company.md").unlink()
        company = self.adapter.read_company()
        self.assertEqual(company.name, "")

    # ---- SSOT guard ----

    def test_developer_ssot_path_rejected(self) -> None:
        with self.assertRaises(SSOTContaminationError):
            LocalAdapter("/tmp/obsidian-vault/02_Projects/LSKunCompanyKit/oops")


class WorkerNameValidationTests(unittest.TestCase):
    """P39 (#5) — _worker_path allowlist 가드 검증."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_rejects_path_traversal_variants(self) -> None:
        for bad in ("..", ".", "../escape", "a/b"):
            with self.assertRaises(ValueError, msg=f"{bad!r} should be rejected"):
                self.adapter.read_worker(bad)

    def test_rejects_null_byte_and_unicode_variants(self) -> None:
        for bad in ("alice\x00", r"alice\path", " alice", "alice ", "Alice"):
            with self.assertRaises(ValueError, msg=f"{bad!r} should be rejected"):
                self.adapter.read_worker(bad)

    def test_rejects_overlong_name(self) -> None:
        with self.assertRaises(ValueError):
            self.adapter.read_worker("a" * 100)

    def test_accepts_valid_kebab_case_names(self) -> None:
        """규격 통과 시 ValueError 가 아니라 WorkerNotFoundError 가 나야 한다."""
        for good in ("alice", "backend-engineer", "alice-2", "a_b-c"):
            with self.assertRaises(WorkerNotFoundError):
                self.adapter.read_worker(good)


class CreateWorkerTests(unittest.TestCase):
    """P45 — StorageAdapter.create_worker 동작."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_creates_worker_with_frontmatter(self) -> None:
        self.adapter.create_worker(
            name="alice",
            frontmatter_dict={
                "name": "alice",
                "role": "backend-engineer",
                "domain": "payments",
                "hired_at": "2026-05-18",
                "storage_backend": "local",
                "display_name": "Alice",
            },
            body="# alice\n\n## Project History\n",
        )
        worker = self.adapter.read_worker("alice")
        self.assertEqual(worker.name, "alice")
        self.assertEqual(worker.role, "backend-engineer")

    def test_create_existing_raises(self) -> None:
        self.adapter.create_worker(
            "alice",
            {"name": "alice", "role": "r", "domain": "meta",
             "hired_at": "2026-05-18", "storage_backend": "local",
             "display_name": "A"},
            "# alice\n",
        )
        with self.assertRaises(FileExistsError):
            self.adapter.create_worker(
                "alice",
                {"name": "alice", "role": "r", "domain": "meta",
                 "hired_at": "2026-05-18", "storage_backend": "local",
                 "display_name": "A"},
                "# alice\n",
            )

    def test_create_rejects_invalid_name(self) -> None:
        with self.assertRaises(ValueError):
            self.adapter.create_worker(
                "../escape", {"name": "x", "role": "r", "domain": "meta",
                 "hired_at": "2026-05-18", "storage_backend": "local",
                 "display_name": "A"}, "body",
            )


class ArchiveWorkerTests(unittest.TestCase):
    """P45 — StorageAdapter.archive_worker 동작 (해고)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        (self.root / "hired" / "alice.md").write_text(WORKER_MD, encoding="utf-8")
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_moves_to_archived_directory(self) -> None:
        self.adapter.archive_worker("alice")
        self.assertFalse((self.root / "hired" / "alice.md").exists())
        archived = self.root / "archived" / "alice.md"
        self.assertTrue(archived.exists())
        # history 보존 — 파일 내용 살아있음
        self.assertIn("stripe-key-as-idem", archived.read_text(encoding="utf-8"))

    def test_archive_missing_raises(self) -> None:
        with self.assertRaises(WorkerNotFoundError):
            self.adapter.archive_worker("ghost")

    def test_archive_does_not_delete_existing_archived_duplicate(self) -> None:
        archived_dir = self.root / "archived"
        archived_dir.mkdir()
        (archived_dir / "alice.md").write_text("기존 archive", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.adapter.archive_worker("alice")
        # hired/ 원본은 보존 — 안전 가드
        self.assertTrue((self.root / "hired" / "alice.md").exists())


class AppendHistoryHelperTests(unittest.TestCase):
    """순수 함수 _append_history_line 의 엣지케이스."""

    def test_appends_when_section_at_end_with_no_trailing_newline(self) -> None:
        src = "# x\n\n## Project History\n\n- old"
        result = _append_history_line(src, "- new")
        self.assertTrue(result.endswith("- new\n"))
        self.assertLess(result.index("- old"), result.index("- new"))

    def test_inserts_before_next_section(self) -> None:
        src = dedent(
            """\
            # x

            ## Project History

            - old

            ## Notes

            tail
            """
        )
        result = _append_history_line(src, "- new")
        self.assertLess(result.index("- new"), result.index("## Notes"))
        self.assertIn("tail", result)


if __name__ == "__main__":
    unittest.main()
