"""P63 — ADR-0010 §4 조직도 view 검증.

원칙:
- read-only (파일 쓰기 0)
- schema 위반 파일은 silent skip
- CPO → HR → Worker 정렬
- history 카운트 (## Project History 의 first-pass 라인 수)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter, org  # noqa: E402


def _worker_md(name: str, role: str, display: str, domain: str = "meta",
               history_lines: int = 0,
               persona_synced_from: str | None = None,
               persona_synced_at: str | None = None) -> str:
    lines = [
        "---",
        f"name: {name}",
        f"role: {role}",
        f"domain: {domain}",
        "hired_at: 2026-01-01",
        "storage_backend: local",
        f"display_name: {display}",
    ]
    if persona_synced_from:
        lines.append(f"persona_synced_from: {persona_synced_from}")
    if persona_synced_at:
        lines.append(f"persona_synced_at: {persona_synced_at}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    lines.append("")
    lines.append("## Project History")
    lines.append("")
    for i in range(history_lines):
        lines.append(f"- 2026-0{(i%9)+1}-0{(i%9)+1} / proj / topic / pat / first-pass 80%")
    return "\n".join(lines) + "\n"


class OrgBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        (self.root / "company.md").write_text(
            "---\nname: Acme\ndomain: payments\n---\n# Acme\n", encoding="utf-8"
        )
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _put(self, name: str, **kw) -> None:
        (self.root / "hired" / f"{name}.md").write_text(
            _worker_md(name, **kw), encoding="utf-8"
        )

    def test_empty_hired_returns_no_entries(self) -> None:
        r = org.build(self.adapter)
        self.assertEqual(len(r.entries), 0)
        self.assertEqual(r.company_name, "Acme")
        self.assertEqual(r.company_domain, "payments")
        self.assertIn("hired 워커 0명", r.render())

    def test_cpo_hr_worker_sorted(self) -> None:
        self._put("alpha", role="frontend-engineer", display="A", domain="web")
        self._put("zulu", role="backend-engineer", display="Z", domain="web")
        self._put("cpo", role="chief-product-officer", display="자비스")
        self._put("hr-lead", role="hr-lead", display="요니찡")
        r = org.build(self.adapter)
        # CPO → HR → Worker(alphabetical)
        names = [e.name for e in sorted(
            r.entries,
            key=lambda e: ({"CPO": 0, "HR": 1, "Worker": 2}[e.category], e.name)
        )]
        self.assertEqual(names, ["cpo", "hr-lead", "alpha", "zulu"])

    # test_history_count_counts_first_pass_lines — ADR-0014 reflection 폐기로 삭제

    def test_invalid_schema_silently_skipped(self) -> None:
        # 필수 필드 누락
        (self.root / "hired" / "broken.md").write_text(
            "---\nname: broken\n---\n# broken\n", encoding="utf-8"
        )
        self._put("alice", role="r", display="A", domain="web")
        r = org.build(self.adapter)
        names = {e.name for e in r.entries}
        self.assertIn("alice", names)
        self.assertNotIn("broken", names)

    def test_backup_files_are_ignored(self) -> None:
        self._put("cpo", role="chief-product-officer", display="자비스")
        # 백업 파일이 있어도 무시
        (self.root / "hired" / "cpo.md.lskun-pre-sync.bak").write_text(
            "garbage", encoding="utf-8"
        )
        r = org.build(self.adapter)
        self.assertEqual(len(r.entries), 1)

    def test_provenance_displayed_for_meta_workers(self) -> None:
        self._put("cpo", role="chief-product-officer", display="자비스",
                  persona_synced_from="lskun-kit@0.8.0",
                  persona_synced_at="2026-05-19")
        self._put("alice", role="r", display="A", domain="web",
                  persona_synced_from="lskun-kit@0.8.0",  # 무시됨 (메타 아님)
                  persona_synced_at="2026-05-19")
        r = org.build(self.adapter)
        text = r.render()
        # 메타 워커만 Persona sync 라인에 등장
        self.assertIn("cpo=lskun-kit@0.8.0", text)
        self.assertNotIn("alice=lskun-kit", text)

    def test_render_includes_summary(self) -> None:
        self._put("cpo", role="chief-product-officer", display="자비스")
        self._put("hr-lead", role="hr-lead", display="요니찡")
        self._put("a", role="frontend-engineer", display="A", domain="web")
        self._put("b", role="backend-engineer", display="B", domain="web")
        text = org.build(self.adapter).render()
        self.assertIn("총: 4명", text)
        self.assertIn("CPO 1", text)
        self.assertIn("HR 1", text)
        self.assertIn("Worker 2", text)
        self.assertIn("web 2", text)
        self.assertIn("meta 2", text)

    def test_render_uses_stable_markdown_table(self) -> None:
        """ADR-0013 + ADR-0014 — markdown table format 박제 강제.

        ADR-0014: History 컬럼 → Hired 컬럼 (hired_at 표시).
        호출마다 형식이 흔들리는 동적 padding 회귀를 방지한다.
        """
        self._put("cpo", role="chief-product-officer", display="자비스")
        self._put("hr-lead", role="hr-lead", display="요니찡")
        self._put("alice", role="backend-engineer", display="앨리스 Kim",
                  domain="web")
        text = org.build(self.adapter).render()
        # 고정 header / separator (ADR-0014 — Hired 컬럼)
        self.assertIn(
            "| Cat    | Name | Display | Role | Domain | Model | Hired |",
            text,
        )
        self.assertIn(
            "|--------|------|---------|------|--------|-------|-------|",
            text,
        )
        # 한글 display name 이 폭 보정 없이 그대로 박힘
        self.assertIn("| 자비스 |", text)
        self.assertIn("| 앨리스 Kim |", text)
        # Cat 컬럼은 6폭 고정 (이건 의도된 유일한 padding)
        self.assertIn("| CPO    |", text)
        self.assertIn("| HR     |", text)
        self.assertIn("| Worker |", text)
        # ADR-0014 — history=N 형식 회귀 방지 + hired_at 박힘
        self.assertNotIn("history=", text)
        self.assertNotIn("h=", text)

    def test_render_is_stable_across_dataset_changes(self) -> None:
        """ADR-0013 — 워커 추가/제거 시 기존 줄의 형식이 흔들리지 않는다."""
        self._put("cpo", role="chief-product-officer", display="자비스")
        self._put("alice", role="backend-engineer", display="A", domain="web")
        text1 = org.build(self.adapter).render()
        alice_line_1 = [ln for ln in text1.splitlines()
                        if "| alice |" in ln][0]
        # 매우 긴 display name 을 가진 워커 추가
        self._put("verylongworkernameforpaddingtest",
                  role="frontend-engineer",
                  display="이름이 매우매우매우 긴 워커",
                  domain="ai")
        text2 = org.build(self.adapter).render()
        alice_line_2 = [ln for ln in text2.splitlines()
                        if "| alice |" in ln][0]
        # 기존 alice 줄이 새 워커의 폭에 영향받지 않고 동일하게 유지
        self.assertEqual(alice_line_1, alice_line_2)


class OrgArchivedTests(unittest.TestCase):
    def test_include_archived_renders_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".company"
            (root / "hired").mkdir(parents=True)
            (root / "archived").mkdir()
            (root / "company.md").write_text(
                "---\nname: Acme\ndomain: web\n---\n# Acme\n", encoding="utf-8"
            )
            (root / "hired" / "alice.md").write_text(
                _worker_md("alice", role="r", display="A", domain="web"),
                encoding="utf-8",
            )
            (root / "archived" / "bob.md").write_text(
                _worker_md("bob", role="r", display="B", domain="web"),
                encoding="utf-8",
            )
            adapter = LocalAdapter(root)
            r = org.build(adapter, include_archived=True)
            self.assertEqual(len(r.entries), 1)
            self.assertEqual(len(r.archived_entries), 1)
            text = r.render(include_archived=True)
            self.assertIn("--- archived ---", text)
            self.assertIn("bob", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
