"""P76 — audit ↔ reflection cross-check 진단 테스트."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lskun_kit import audit_diagnostics, reflection
from lskun_kit.adapters.local import LocalAdapter
from lskun_kit.audit import VERDICT_APPROVED


def _seed_company(root: Path):
    root.mkdir(parents=True)
    (root / "company.md").write_text(
        "---\nname: T\ndomain: t\n---\n", encoding="utf-8"
    )
    (root / "hired").mkdir()
    (root / "hired" / "w1.md").write_text(
        "---\nname: w1\nrole: dev\ndomain: t\nhired_at: 2026-05-21\n"
        "storage_backend: local\ndisplay_name: W\n---\n\n## Project History\n",
        encoding="utf-8",
    )
    (root / ".audit").mkdir()


def _write_audit(root: Path, request_ids: list[str]):
    lines = []
    for rid in request_ids:
        lines.append(json.dumps({
            "request_id": rid,
            "company": "T", "worker": "w1", "domain": "t", "model": "sonnet",
            "first_pass_score": 80, "rounds": 1,
            "verdict": VERDICT_APPROVED,
            "reason": "ok", "auto_hired": False, "ts": "2026-05-21T00:00:00Z",
        }))
    (root / ".audit" / "decisions.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


_REPORT = """\
## 작업 결과
ok

## first-pass 자가 점수
80%

## reflection 후보
- topic: x
- pattern: y
- 다음에 같은 패턴이 또 발생하면 인용할만한 한 줄: z
"""


class CrossCheckTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        _seed_company(self.root)
        self.adapter = LocalAdapter(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_audit_no_history_is_healthy(self):
        r = audit_diagnostics.build(self.adapter)
        self.assertEqual(r.audit_approved_count, 0)
        self.assertEqual(r.missing_request_ids, ())
        self.assertTrue(r.is_healthy())

    def test_audit_only_marks_all_missing(self):
        _write_audit(self.root, ["aaaaaaaa11111111", "bbbbbbbb22222222"])
        r = audit_diagnostics.build(self.adapter)
        self.assertEqual(r.audit_approved_count, 2)
        self.assertEqual(len(r.missing_request_ids), 2)
        self.assertEqual(r.coverage_pct, 0.0)
        self.assertFalse(r.is_healthy())

    def test_matched_pair_is_healthy(self):
        rid = "deadbeef0000111122223333"
        reflection.record_from_report(
            self.adapter, "w1", project="T", report_md=_REPORT,
            request_id=rid,
        )
        _write_audit(self.root, [rid])
        r = audit_diagnostics.build(self.adapter)
        self.assertEqual(r.audit_approved_count, 1)
        self.assertEqual(r.missing_request_ids, ())
        self.assertEqual(r.reflection_entries_with_req, 1)
        self.assertEqual(r.coverage_pct, 100.0)
        self.assertTrue(r.is_healthy())

    def test_legacy_entry_counted_separately(self):
        # request_id 없는 옛 entry
        reflection.record(
            self.adapter, "w1", project="T", topic="a", pattern="b",
            first_pass_score=80,
        )
        r = audit_diagnostics.build(self.adapter)
        self.assertEqual(r.reflection_entries_legacy, 1)
        self.assertEqual(r.reflection_entries_with_req, 0)

    def test_render_contains_status_icon(self):
        _write_audit(self.root, ["xx"])
        r = audit_diagnostics.build(self.adapter)
        out = audit_diagnostics.render(r)
        self.assertIn("⚠️", out)
        self.assertIn("audit", out)


if __name__ == "__main__":
    unittest.main()
