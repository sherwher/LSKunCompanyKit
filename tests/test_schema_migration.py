"""P50 — ADR-0005 schema 마이그레이션 검증.

원칙:
- history 절대 보존
- frontmatter 기존 키 덮어쓰기 금지
- 백업 강제
- v0.2 → v0.4, v0.3 → v0.4, 이미 v0.4 (no-op) 시나리오
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit import schema_migration as sm  # noqa: E402


COMPANY_V0_2 = dedent(
    """\
    ---
    name: Acme
    founded: 2026-01-01
    ---

    # Acme

    (회사 소개)
    """
)

COMPANY_V0_3 = dedent(
    """\
    ---
    name: Acme
    founded: 2026-01-01
    domain: payments
    ---

    # Acme
    """
)

WORKER_V0_2 = dedent(
    """\
    ---
    name: alice
    role: backend-engineer
    hired_at: 2026-01-15
    storage_backend: local
    ---

    # alice

    ## Project History

    - 2026-01-20 / payment-svc / idempotency / stripe-key / first-pass 88%
    """
)

WORKER_V0_3 = dedent(
    """\
    ---
    name: bob
    role: frontend-engineer
    domain: payments
    hired_at: 2026-02-01
    storage_backend: local
    ---

    # bob

    ## Project History

    - 2026-02-10 / checkout / form / debounce-onChange / first-pass 92%
    """
)

WORKER_V0_4 = dedent(
    """\
    ---
    name: carol
    role: designer
    domain: meta
    hired_at: 2026-03-01
    storage_backend: local
    display_name: Carol Kim
    ---

    # carol

    ## Project History

    - 2026-03-05 / brand / palette / hsl-derive / first-pass 80%
    """
)


class DetectionTests(unittest.TestCase):
    def test_worker_v0_2_detection(self) -> None:
        s, missing = sm.detect_worker_schema({
            "name": "alice", "role": "r", "hired_at": "2026-01-01",
            "storage_backend": "local",
        })
        self.assertEqual(s, "v0.2")
        self.assertIn("domain", missing)
        self.assertIn("display_name", missing)

    def test_worker_v0_3_detection(self) -> None:
        s, missing = sm.detect_worker_schema({
            "name": "alice", "role": "r", "domain": "d",
            "hired_at": "2026-01-01", "storage_backend": "local",
        })
        self.assertEqual(s, "v0.3")
        self.assertEqual(missing, ("display_name",))

    def test_worker_v0_4_detection(self) -> None:
        s, missing = sm.detect_worker_schema({
            "name": "alice", "role": "r", "domain": "d",
            "hired_at": "2026-01-01", "storage_backend": "local",
            "display_name": "Alice",
        })
        self.assertEqual(s, "v0.4")
        self.assertEqual(missing, ())

    def test_company_schema_detection(self) -> None:
        s2, m2 = sm.detect_company_schema({"name": "Acme"})
        self.assertEqual(s2, "v0.2")
        self.assertIn("domain", m2)
        s3, m3 = sm.detect_company_schema({"name": "Acme", "domain": "payments"})
        self.assertEqual(s3, "v0.3+")
        self.assertEqual(m3, ())


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _setup(self, company_text: str, workers: dict[str, str]) -> LocalAdapter:
        (self.root / "company.md").write_text(company_text, encoding="utf-8")
        for name, text in workers.items():
            (self.root / "hired" / f"{name}.md").write_text(text, encoding="utf-8")
        return LocalAdapter(self.root)

    def test_v0_2_company_with_v0_2_workers_full_gap(self) -> None:
        adapter = self._setup(COMPANY_V0_2, {"alice": WORKER_V0_2})
        p = sm.plan(adapter, self.root, backend="local")
        self.assertIn("domain", p.company_missing_fields)
        self.assertEqual(len(p.worker_gaps), 1)
        self.assertEqual(p.worker_gaps[0].name, "alice")
        self.assertIn("domain", p.worker_gaps[0].missing_fields)
        self.assertIn("display_name", p.worker_gaps[0].missing_fields)
        self.assertFalse(p.is_no_op)

    def test_v0_3_company_with_v0_3_workers_only_display_name_gap(self) -> None:
        adapter = self._setup(COMPANY_V0_3, {"bob": WORKER_V0_3})
        p = sm.plan(adapter, self.root, backend="local")
        self.assertEqual(p.company_missing_fields, ())
        self.assertEqual(len(p.worker_gaps), 1)
        self.assertEqual(p.worker_gaps[0].missing_fields, ("display_name",))

    def test_v0_4_no_op(self) -> None:
        """ADR-0014 — `## Project History` 가 있으면 더 이상 no-op 아님 (archived 로 rename 필요).

        legacy heading 이 없는 fixture 로 진짜 no-op 검증.
        """
        # WORKER_V0_4 본문에서 ## Project History 섹션 전체 제거
        worker_no_history = WORKER_V0_4.split("## Project History", 1)[0].rstrip() + "\n"
        adapter = self._setup(COMPANY_V0_3, {"carol": worker_no_history})
        p = sm.plan(adapter, self.root, backend="local")
        self.assertTrue(p.is_no_op)

    def test_v0_4_with_legacy_history_is_not_no_op(self) -> None:
        """ADR-0014 — legacy `## Project History` heading 이 있으면 rename 대상."""
        adapter = self._setup(COMPANY_V0_3, {"carol": WORKER_V0_4})
        p = sm.plan(adapter, self.root, backend="local")
        self.assertFalse(p.is_no_op)
        self.assertEqual(p.legacy_history_workers, ["carol"])


class ExecuteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        (self.root / "company.md").write_text(COMPANY_V0_2, encoding="utf-8")
        (self.root / "hired" / "alice.md").write_text(WORKER_V0_2, encoding="utf-8")
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_v0_2_to_v0_4_full_migration(self) -> None:
        before_history = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        p = sm.plan(self.adapter, self.root, backend="local")
        answers = sm.MigrationAnswers(
            company_domain="payments",
            worker_display_names={"alice": "Alice Park"},
            worker_domains={"alice": "payments"},
        )
        result = sm.execute(self.adapter, p, answers)

        # company.md 보강
        c_text = (self.root / "company.md").read_text(encoding="utf-8")
        self.assertIn("domain: payments", c_text)
        self.assertTrue(result.company_md_updated)

        # 워커 frontmatter 6 필드 모두 있음
        worker = self.adapter.read_worker("alice")
        self.assertEqual(worker.domain, "payments")
        self.assertEqual(worker.display_name, "Alice Park")

        # history entry 절대 보존 (ADR-0014 — heading 만 archived 로 rename)
        a_text = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        self.assertIn("stripe-key", a_text)
        self.assertIn("first-pass 88%", a_text)
        # heading 은 ADR-0014 에 따라 rename 됨
        self.assertIn("## Archived History (pre-0.18)", a_text)
        self.assertNotIn("\n## Project History\n", a_text)
        # entry 본문은 보존
        before_hist = before_history.split("## Project History", 1)[1]
        after_hist = a_text.split("## Archived History (pre-0.18)", 1)[1]
        self.assertEqual(before_hist, after_hist)

        # 백업 파일 존재
        bak = self.root / "company.md.lskun-pre-migrate.bak"
        self.assertTrue(bak.exists())
        bak_w = self.root / "hired" / "alice.md.lskun-pre-migrate.bak"
        self.assertTrue(bak_w.exists())

    def test_cpo_hr_get_meta_domain_automatically(self) -> None:
        (self.root / "hired" / "cpo.md").write_text(
            WORKER_V0_2.replace("name: alice", "name: cpo")
                       .replace("role: backend-engineer", "role: chief-product-officer"),
            encoding="utf-8",
        )
        (self.root / "hired" / "hr-lead.md").write_text(
            WORKER_V0_2.replace("name: alice", "name: hr-lead")
                       .replace("role: backend-engineer", "role: hr-lead"),
            encoding="utf-8",
        )
        # 사용자가 cpo/hr 의 domain 을 안 줘도 자동 meta 부여
        p = sm.plan(self.adapter, self.root, backend="local")
        answers = sm.MigrationAnswers(
            company_domain="payments",
            worker_display_names={
                "alice": "Alice", "cpo": "이세근", "hr-lead": "김지혜",
            },
            worker_domains={"alice": "payments"},  # cpo/hr-lead 누락 의도
        )
        sm.execute(self.adapter, p, answers)
        self.assertEqual(self.adapter.read_worker("cpo").domain, "meta")
        self.assertEqual(self.adapter.read_worker("hr-lead").domain, "meta")

    def test_existing_frontmatter_keys_are_never_overwritten(self) -> None:
        # 일부러 storage_backend 를 "vault" 로 박혀있게 — backend 인자(local)는 무시되어야
        custom = WORKER_V0_2.replace("storage_backend: local", "storage_backend: vault")
        (self.root / "hired" / "alice.md").write_text(custom, encoding="utf-8")
        p = sm.plan(self.adapter, self.root, backend="local")
        answers = sm.MigrationAnswers(
            company_domain="payments",
            worker_display_names={"alice": "A"},
            worker_domains={"alice": "payments"},
        )
        sm.execute(self.adapter, p, answers)
        # 덮어쓰이지 않고 vault 그대로
        self.assertEqual(self.adapter.read_worker("alice").storage_backend, "vault")

    def test_missing_display_name_answer_raises(self) -> None:
        p = sm.plan(self.adapter, self.root, backend="local")
        answers = sm.MigrationAnswers(
            company_domain="payments",
            worker_display_names={},  # alice 미포함
            worker_domains={"alice": "payments"},
        )
        with self.assertRaises(sm.SchemaMigrationError):
            sm.execute(self.adapter, p, answers)

    def test_v0_4_execute_is_no_op(self) -> None:
        """ADR-0014 — legacy history heading 이 없는 v0.4 fixture 로 no-op 검증."""
        # WORKER_V0_4 본문에서 ## Project History 섹션 전체 제거 + name 변경
        worker_no_history = (
            WORKER_V0_4.split("## Project History", 1)[0].rstrip() + "\n"
        ).replace("name: carol", "name: alice")
        (self.root / "hired" / "alice.md").write_text(worker_no_history, encoding="utf-8")
        (self.root / "company.md").write_text(COMPANY_V0_3, encoding="utf-8")
        adapter = LocalAdapter(self.root)
        p = sm.plan(adapter, self.root, backend="local")
        result = sm.execute(adapter, p, sm.MigrationAnswers())
        self.assertFalse(result.company_md_updated)
        self.assertEqual(result.workers_updated, [])
        self.assertEqual(result.backups_created, [])

    def test_legacy_history_rename_only(self) -> None:
        """ADR-0014 — v0.4 schema 통과 + legacy history heading 만 rename 필요한 케이스."""
        worker_v0_4_with_history = WORKER_V0_4.replace("name: carol", "name: alice")
        (self.root / "hired" / "alice.md").write_text(
            worker_v0_4_with_history, encoding="utf-8"
        )
        (self.root / "company.md").write_text(COMPANY_V0_3, encoding="utf-8")
        adapter = LocalAdapter(self.root)
        p = sm.plan(adapter, self.root, backend="local")
        self.assertFalse(p.is_no_op)
        self.assertEqual(p.legacy_history_workers, ["alice"])
        result = sm.execute(adapter, p, sm.MigrationAnswers())
        a_text = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        self.assertIn("## Archived History (pre-0.18)", a_text)
        self.assertNotIn("\n## Project History\n", a_text)
        self.assertIn("alice", result.workers_updated)


class ClaudeMdInjectionTests(unittest.TestCase):
    """P50 — plan/execute 가 project_root 받으면 CLAUDE.md marker 박제도 함께."""

    def test_plan_detects_missing_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            root = proj / ".company"
            (root / "hired").mkdir(parents=True)
            (root / "company.md").write_text(COMPANY_V0_3, encoding="utf-8")
            (root / "hired" / "alice.md").write_text(WORKER_V0_3, encoding="utf-8")
            adapter = LocalAdapter(root)
            p = sm.plan(adapter, root, backend="local", project_root=proj)
            self.assertTrue(p.claude_md_marker_missing)

    def test_execute_injects_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            root = proj / ".company"
            (root / "hired").mkdir(parents=True)
            (root / "company.md").write_text(COMPANY_V0_3, encoding="utf-8")
            # CPO 워커가 있어야 inject 시 body 를 가져옴
            cpo_v0_3 = WORKER_V0_3.replace("name: bob", "name: cpo").replace(
                "role: frontend-engineer", "role: chief-product-officer"
            )
            (root / "hired" / "cpo.md").write_text(cpo_v0_3, encoding="utf-8")
            adapter = LocalAdapter(root)
            p = sm.plan(adapter, root, backend="local", project_root=proj)
            answers = sm.MigrationAnswers(
                worker_display_names={"cpo": "이세근"},
            )
            result = sm.execute(adapter, p, answers)
            self.assertIn(result.claude_md_action, ("created", "updated"))
            claude_md = proj / "CLAUDE.md"
            self.assertTrue(claude_md.exists())
            self.assertIn("LSKUN-CPO:START", claude_md.read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
