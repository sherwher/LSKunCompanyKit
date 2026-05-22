"""P61 — ADR-0010 persona sync 검증.

원칙:
- 메타 워커 (cpo / hr-lead) 만 sync 대상
- frontmatter / Project History 절대 보존
- 백업 강제
- idempotent
- body 동일 + provenance 부재 케이스도 provenance 만 박제
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
from lskun_kit import persona_sync as ps  # noqa: E402
from lskun_kit.persona_sync import PROV_FROM, PROV_AT  # noqa: E402
from lskun_kit.templates import _read_template  # type: ignore  # noqa: E402


def _company_skeleton(tmp: Path, with_cpo_body: str = "", with_hr_body: str = "") -> LocalAdapter:
    root = tmp / ".company"
    (root / "hired").mkdir(parents=True)
    (root / "company.md").write_text(
        "---\nname: Acme\ndomain: payments\n---\n# Acme\n", encoding="utf-8"
    )
    cpo_text = dedent(
        """\
        ---
        name: cpo
        role: chief-product-officer
        domain: meta
        hired_at: 2026-01-01
        storage_backend: local
        display_name: 자비스
        ---

        # cpo

        STALE BODY PLACEHOLDER

        ## Project History

        - 2026-01-15 / payment / idempotency / stripe-key / first-pass 90%
        """
    )
    hr_text = dedent(
        """\
        ---
        name: hr-lead
        role: hr-lead
        domain: meta
        hired_at: 2026-01-01
        storage_backend: local
        display_name: 요니찡
        ---

        # hr-lead

        STALE BODY PLACEHOLDER

        ## Project History

        - 2026-01-20 / hire / spec / canonical / first-pass 88%
        """
    )
    (root / "hired" / "cpo.md").write_text(cpo_text, encoding="utf-8")
    (root / "hired" / "hr-lead.md").write_text(hr_text, encoding="utf-8")
    return LocalAdapter(root)


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.adapter = _company_skeleton(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_plan_detects_stale_body(self) -> None:
        p = ps.plan(self.adapter, "0.8.0")
        self.assertEqual(len(p.deltas), 2)
        for d in p.deltas:
            self.assertFalse(d.body_in_sync)
            self.assertFalse(d.provenance_in_sync)
            self.assertTrue(d.needs_action)
        self.assertFalse(p.is_no_op)

    def test_plan_specific_worker_only(self) -> None:
        p = ps.plan(self.adapter, "0.8.0", worker_names=["cpo"])
        self.assertEqual(len(p.deltas), 1)
        self.assertEqual(p.deltas[0].name, "cpo")

    def test_plan_rejects_non_meta_worker_with_warning(self) -> None:
        p = ps.plan(self.adapter, "0.8.0", worker_names=["frontend-engineer"])
        self.assertEqual(len(p.deltas), 0)
        self.assertTrue(any("메타 워커가 아니" in n for n in p.notes))


class ExecuteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.adapter = _company_skeleton(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sync_replaces_body_preserves_history_and_frontmatter(self) -> None:
        p = ps.plan(self.adapter, "0.8.0")
        result = ps.execute(self.adapter, p)
        self.assertEqual(len(result.per_worker), 2)
        # body 가 STALE 에서 실제 template 본문으로 교체
        cpo_text = (self.adapter.root / "hired" / "cpo.md").read_text(encoding="utf-8")
        self.assertNotIn("STALE BODY PLACEHOLDER", cpo_text)
        # frontmatter 보존 (display_name 그대로)
        cpo = self.adapter.read_worker("cpo")
        self.assertEqual(cpo.display_name, "자비스")
        self.assertEqual(cpo.domain, "meta")
        # provenance 박제
        self.assertEqual(cpo.persona_synced_from, "lskun-kit@0.8.0")
        self.assertIsNotNone(cpo.persona_synced_at)
        # history 절대 보존
        self.assertIn("stripe-key", cpo_text)
        self.assertIn("first-pass 90%", cpo_text)
        # 백업 존재
        bak = self.adapter.root / "hired" / "cpo.md.lskun-pre-sync.bak"
        self.assertTrue(bak.exists())

    def test_idempotent_second_run_is_noop(self) -> None:
        p1 = ps.plan(self.adapter, "0.8.0")
        ps.execute(self.adapter, p1)
        # 두 번째 plan 은 모두 in_sync
        p2 = ps.plan(self.adapter, "0.8.0")
        for d in p2.deltas:
            self.assertTrue(d.body_in_sync)
            self.assertTrue(d.provenance_in_sync)
            self.assertFalse(d.needs_action)
        self.assertTrue(p2.is_no_op)
        # execute 도 no-op (백업 추가 안 됨)
        result2 = ps.execute(self.adapter, p2)
        self.assertEqual(len(result2.per_worker), 0)

    def test_body_synced_but_provenance_missing_only_writes_frontmatter(self) -> None:
        """LSKun 의 1회성 수동 sync 시나리오 — body 는 OK, provenance 만 부재."""
        # 먼저 정상 sync 1회
        p1 = ps.plan(self.adapter, "0.8.0")
        ps.execute(self.adapter, p1)
        # provenance 만 제거 (수동 편집 시뮬레이션)
        from lskun_kit.adapters import frontmatter as fm
        cpo_path = self.adapter.root / "hired" / "cpo.md"
        parsed = fm.parse(cpo_path.read_text(encoding="utf-8"))
        new_fm = {k: v for k, v in parsed.frontmatter.items()
                  if k not in (PROV_FROM, PROV_AT)}
        cpo_path.write_text(fm.dump(new_fm, parsed.body), encoding="utf-8")
        # plan — body OK, provenance missing
        p2 = ps.plan(self.adapter, "0.8.0")
        cpo_delta = next(d for d in p2.deltas if d.name == "cpo")
        self.assertTrue(cpo_delta.body_in_sync)
        self.assertFalse(cpo_delta.provenance_in_sync)
        # execute — provenance 만 박제, body 변경 X
        result = ps.execute(self.adapter, p2)
        cpo_result = next(r for r in result.per_worker if r.name == "cpo")
        self.assertFalse(cpo_result.body_updated)
        self.assertTrue(cpo_result.provenance_updated)
        # 그래도 백업은 함 (변경이 발생했으므로)
        self.assertIsNotNone(cpo_result.backup_path)

    def test_diff_text_for_shows_stale_lines(self) -> None:
        p = ps.plan(self.adapter, "0.8.0")
        diff = ps.diff_text_for(p, "cpo")
        self.assertIn("STALE BODY PLACEHOLDER", diff)


class TemplateBodyTests(unittest.TestCase):
    """templates 의 body 가 plugin 에 실제로 존재하는지 확인."""

    def test_cpo_template_exists(self) -> None:
        # _read_template 은 templates/<filename> 을 읽음
        # ADR-0014 — Project History 섹션 폐기. 핵심 책임 / 결재 절차만 검증.
        body = _read_template("cpo.md")
        self.assertIn("CPO", body)
        self.assertIn("결재", body)

    def test_hr_lead_template_exists(self) -> None:
        body = _read_template("hr-lead.md")
        self.assertIn("HR Lead", body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
